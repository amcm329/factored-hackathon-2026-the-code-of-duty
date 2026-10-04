from pathlib import Path, PurePosixPath
import boto3
import pandas as pd
from sqlalchemy import create_engine, inspect
from sqlalchemy.dialects.postgresql import insert
from backend.secrets import get_database_url, get_organizer_s3_config

chunk_size = 50000

organizer_tables = [
    "customers",
    "products",
    "transactions",
    "call_center_interactions",
    "call_transcripts",
    "complaints",
]

table_order = {
    table_name: index
    for index, table_name in enumerate(organizer_tables)
}


def create_organizer_s3_client():
    """
    Create the read-only organizer S3 client.

    Parameters
    ----------
    None.

    Returns
    -------
    boto3.client
        Configured S3 client.
    """
    config = get_organizer_s3_config()

    return boto3.client(
        "s3",
        region_name=config["AWS_REGION"],
        aws_access_key_id=config["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=config["AWS_SECRET_ACCESS_KEY"],
    )


def infer_table_name(key, prefix):
    """
    Infer the target RDS table from an organizer S3 CSV key.

    Parameters
    ----------
    key : str
        Full S3 object key.
    prefix : str
        Organizer dataset prefix.

    Returns
    -------
    str
        Target PostgreSQL table name.
    """
    relative_key = key[len(prefix):].lstrip("/")
    parts = PurePosixPath(relative_key).parts

    if len(parts) == 1:
        return PurePosixPath(parts[0]).stem

    return parts[0]


def run_schema_scripts(engine):
    """
    Create the dispute-workflow RDS tables before ingestion.

    Parameters
    ----------
    engine
        SQLAlchemy PostgreSQL engine.

    Returns
    -------
    None.
    """
    sql_dir = Path(__file__).resolve().parents[1] / "backend" / "sql"
    sql_files = sorted(sql_dir.glob("*.sql"))

    if not sql_files:
        raise RuntimeError(f"No SQL schema files found in {sql_dir}")

    with engine.begin() as connection:
        for sql_file in sql_files:
            sql_text = sql_file.read_text(encoding="utf-8")
            connection.exec_driver_sql(sql_text)
            print(f"Applied schema: {sql_file.name}")


def list_csv_keys(s3, bucket, prefix):
    """
    List only organizer CSV files required by the dispute workflow.

    Parameters
    ----------
    s3
        Configured organizer S3 client.
    bucket : str
        Organizer bucket name.
    prefix : str
        Organizer dataset prefix.

    Returns
    -------
    list
        Ordered S3 object keys for the six dispute-related organizer tables.
    """
    paginator = s3.get_paginator("list_objects_v2")
    keys = []

    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for item in page.get("Contents", []):
            key = item["Key"]

            if not key.lower().endswith(".csv"):
                continue

            table_name = infer_table_name(key, prefix)

            if table_name in table_order:
                keys.append(key)

    return sorted(
        keys,
        key=lambda key: (
            table_order[infer_table_name(key, prefix)],
            key,
        ),
    )


def insert_ignore_conflicts(table, connection, keys, data_iter):
    """
    Insert rows while skipping primary-key or unique-key conflicts.

    Parameters
    ----------
    table
        pandas SQL table wrapper.
    connection
        Active SQLAlchemy connection.
    keys : list
        Column names supplied by pandas.
    data_iter
        Iterator containing row values.

    Returns
    -------
    int
        Number of rows inserted.
    """
    rows = [
        dict(zip(keys, row))
        for row in data_iter
    ]

    if not rows:
        return 0

    statement = insert(table.table).values(rows)
    statement = statement.on_conflict_do_nothing()
    result = connection.execute(statement)

    return result.rowcount


def validate_target_table(engine, table_name, csv_columns):
    """
    Verify the RDS table exists and contains every incoming CSV column.

    Parameters
    ----------
    engine
        SQLAlchemy PostgreSQL engine.
    table_name : str
        Target RDS table.
    csv_columns : iterable
        Columns present in the current CSV chunk.

    Returns
    -------
    None.
    """
    inspector = inspect(engine)

    if not inspector.has_table(table_name):
        raise RuntimeError(f"Target table does not exist: {table_name}")

    database_columns = {
        column["name"]
        for column in inspector.get_columns(table_name)
    }

    missing_columns = set(csv_columns) - database_columns

    if missing_columns:
        raise RuntimeError(
            f"{table_name} contains CSV columns missing from the RDS schema: "
            f"{sorted(missing_columns)}"
        )


def ingest_csv_object(s3, engine, bucket, prefix, key):
    """
    Stream one required organizer CSV directly from S3 into RDS.

    Parameters
    ----------
    s3
        Configured organizer S3 client.
    engine
        SQLAlchemy PostgreSQL engine.
    bucket : str
        Organizer bucket name.
    prefix : str
        Organizer dataset prefix.
    key : str
        S3 CSV object key.

    Returns
    -------
    None.
    """
    table_name = infer_table_name(key, prefix)

    if table_name not in table_order:
        raise RuntimeError(
            f"Unsupported dispute-workflow table: {table_name}"
        )

    print(f"Loading s3://{bucket}/{key} -> {table_name}")

    response = s3.get_object(
        Bucket=bucket,
        Key=key,
    )

    body = response["Body"]
    first_chunk = True

    for chunk in pd.read_csv(
        body,
        chunksize=chunk_size,
        low_memory=False,
    ):
        if first_chunk:
            validate_target_table(
                engine=engine,
                table_name=table_name,
                csv_columns=chunk.columns,
            )
            first_chunk = False

        chunk.to_sql(
            name=table_name,
            con=engine,
            if_exists="append",
            index=False,
            method=insert_ignore_conflicts,
            chunksize=2000,
        )

    print(f"Finished: {table_name}")


def main():
    """
    Create the dispute RDS schema and ingest only required organizer tables.

    Parameters
    ----------
    None.

    Returns
    -------
    None.
    """
    config = get_organizer_s3_config()
    bucket = config["BUCKET_NAME"]
    prefix = config.get("DATA_PREFIX", "data/")

    engine = create_engine(
        get_database_url(),
        pool_pre_ping=True,
    )

    # We create the six organizer tables plus three application tables first.
    run_schema_scripts(engine)

    # We ingest only organizer data required by the dispute workflow.
    s3 = create_organizer_s3_client()

    csv_keys = list_csv_keys(
        s3=s3,
        bucket=bucket,
        prefix=prefix,
    )

    if not csv_keys:
        raise RuntimeError(
            f"No dispute-workflow organizer CSV files found under "
            f"s3://{bucket}/{prefix}"
        )

    for key in csv_keys:
        ingest_csv_object(
            s3=s3,
            engine=engine,
            bucket=bucket,
            prefix=prefix,
            key=key,
        )

    engine.dispose()

    print("Dispute-workflow S3 -> RDS ingestion completed.")


if __name__ == "__main__":
    main()
