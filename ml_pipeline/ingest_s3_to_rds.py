from io import StringIO
import math
import os
from pathlib import Path, PurePosixPath

import boto3
import pandas as pd
from psycopg2 import sql
from sqlalchemy import create_engine, inspect

from backend.secrets import get_database_url, get_organizer_s3_config


# Designed for a fast hackathon load on the current Worker/RDS sizing.
# Customers stay complete so every authenticated customer can still be resolved.
# Large tables are reduced before they are written to PostgreSQL.
read_chunk_size = 50000

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

# Hard safety caps for the one-time RDS load.
# Override any value with an environment variable if a larger sample is needed.
row_limits = {
    "customers": int(os.getenv("INGEST_CUSTOMERS_MAX_ROWS", "150000")),
    "products": int(os.getenv("INGEST_PRODUCTS_MAX_ROWS", "50000")),
    "transactions": int(os.getenv("INGEST_TRANSACTIONS_MAX_ROWS", "500000")),
    "call_center_interactions": int(
        os.getenv("INGEST_INTERACTIONS_MAX_ROWS", "80000")
    ),
    "call_transcripts": int(os.getenv("INGEST_TRANSCRIPTS_MAX_ROWS", "20000")),
    "complaints": int(os.getenv("INGEST_COMPLAINTS_MAX_ROWS", "8000")),
}

# Approximate share of source data to inspect for each table. When a fact table
# is date-partitioned, this is applied to partition files before downloading them.
# If a table is a single CSV, deterministic row sampling is used instead.
sample_fractions = {
    "customers": 1.00,
    "products": 0.125,
    "transactions": 0.10,
    "call_center_interactions": 0.10,
    "call_transcripts": 0.10,
    "complaints": 0.10,
}

# Large fact tables documented as date-partitioned by the organizer.
fact_tables = {
    "transactions",
    "call_center_interactions",
    "call_transcripts",
    "complaints",
}


class PostgresBulkWriter:
    """Fast COPY -> temporary table -> ON CONFLICT DO NOTHING writer."""

    def __init__(self, engine, table_name):
        self.connection = engine.raw_connection()
        self.cursor = self.connection.cursor()
        self.table_name = table_name
        self.stage_name = f"_stage_{table_name}_{os.getpid()}"
        self.columns = None

        # Safe here because the organizer data is reproducible and can be reloaded.
        # This changes durability only for this ingestion session, not globally.
        self.cursor.execute("SET synchronous_commit TO OFF")

    def _initialize(self, columns):
        self.columns = list(columns)
        self.cursor.execute(
            sql.SQL(
                "CREATE TEMP TABLE {} (LIKE {} INCLUDING DEFAULTS) "
                "ON COMMIT PRESERVE ROWS"
            ).format(
                sql.Identifier(self.stage_name),
                sql.Identifier(self.table_name),
            )
        )
        self.connection.commit()

    def write(self, frame):
        if frame.empty:
            return 0

        if self.columns is None:
            self._initialize(frame.columns)

        if list(frame.columns) != self.columns:
            raise RuntimeError(
                f"Column order changed while loading {self.table_name}"
            )

        buffer = StringIO()
        frame.to_csv(
            buffer,
            index=False,
            header=False,
            na_rep="\\N",
            lineterminator="\n",
        )
        buffer.seek(0)

        column_identifiers = sql.SQL(", ").join(
            sql.Identifier(column)
            for column in self.columns
        )

        copy_statement = sql.SQL(
            "COPY {} ({}) FROM STDIN WITH (FORMAT CSV, NULL '\\N')"
        ).format(
            sql.Identifier(self.stage_name),
            column_identifiers,
        )

        insert_statement = sql.SQL(
            "INSERT INTO {} ({}) SELECT {} FROM {} ON CONFLICT DO NOTHING"
        ).format(
            sql.Identifier(self.table_name),
            column_identifiers,
            column_identifiers,
            sql.Identifier(self.stage_name),
        )

        try:
            self.cursor.copy_expert(
                copy_statement.as_string(self.cursor),
                buffer,
            )
            self.cursor.execute(insert_statement)
            inserted_rows = self.cursor.rowcount
            self.cursor.execute(
                sql.SQL("TRUNCATE TABLE {}").format(
                    sql.Identifier(self.stage_name)
                )
            )
            self.connection.commit()
            return inserted_rows
        except Exception:
            self.connection.rollback()
            raise

    def close(self):
        try:
            self.cursor.close()
        finally:
            self.connection.close()


def create_organizer_s3_client():
    """Create the read-only organizer S3 client."""
    config = get_organizer_s3_config()

    return boto3.client(
        "s3",
        region_name=config["AWS_REGION"],
        aws_access_key_id=config["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=config["AWS_SECRET_ACCESS_KEY"],
    )


def infer_table_name(key, prefix):
    """Infer the target RDS table from an organizer S3 CSV key."""
    relative_key = key[len(prefix):].lstrip("/")
    parts = PurePosixPath(relative_key).parts

    if len(parts) == 1:
        return PurePosixPath(parts[0]).stem

    return parts[0]


def run_schema_scripts(engine):
    """Create the dispute-workflow RDS tables before ingestion."""
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
    """List organizer CSV files required by the dispute workflow."""
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


def _evenly_spaced_keys(keys, fraction):
    """Select partition keys across the full sorted date range."""
    if not keys or fraction >= 1.0 or len(keys) == 1:
        return list(keys)

    target_count = max(1, int(math.ceil(len(keys) * fraction)))

    # Avoid selecting only one point in time when a small number of partitions
    # exists; use beginning/middle/end whenever possible.
    if len(keys) >= 3:
        target_count = max(3, target_count)

    target_count = min(target_count, len(keys))

    if target_count == 1:
        return [keys[len(keys) // 2]]

    indexes = []
    for position in range(target_count):
        index = round(
            position * (len(keys) - 1) / (target_count - 1)
        )
        indexes.append(index)

    return [keys[index] for index in sorted(set(indexes))]


def _deterministic_row_sample(frame, fraction):
    """Sample one single-file table deterministically before RDS insertion."""
    if fraction >= 1.0 or frame.empty:
        return frame

    # customer_id keeps related single-file tables on the same customer cohort.
    if "customer_id" in frame.columns:
        sample_key = frame["customer_id"].astype(str)
    else:
        sample_key = frame.iloc[:, 0].astype(str)

    hashes = pd.util.hash_pandas_object(
        sample_key,
        index=False,
    ).astype("uint64")

    threshold = int(fraction * 1_000_000)
    mask = (hashes % 1_000_000) < threshold
    return frame.loc[mask]


def validate_target_table(engine, table_name, csv_columns):
    """Verify the target table exists and supports all incoming columns."""
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


def ingest_csv_object(
    s3,
    engine,
    writer,
    bucket,
    prefix,
    key,
    max_rows,
    row_sample_fraction,
):
    """Stream a bounded source sample directly from S3 into RDS."""
    table_name = infer_table_name(key, prefix)

    print(
        f"Loading s3://{bucket}/{key} -> {table_name} "
        f"(object cap={max_rows:,})"
    )

    response = s3.get_object(
        Bucket=bucket,
        Key=key,
    )

    body = response["Body"]
    first_chunk = True
    accepted_rows = 0
    inserted_rows = 0

    for chunk in pd.read_csv(
        body,
        chunksize=read_chunk_size,
        low_memory=False,
    ):
        if first_chunk:
            validate_target_table(
                engine=engine,
                table_name=table_name,
                csv_columns=chunk.columns,
            )
            first_chunk = False

        chunk = _deterministic_row_sample(
            chunk,
            row_sample_fraction,
        )

        if chunk.empty:
            continue

        remaining = max_rows - accepted_rows
        if remaining <= 0:
            break

        chunk = chunk.iloc[:remaining]
        accepted_rows += len(chunk)
        inserted_rows += writer.write(chunk)

        if accepted_rows >= max_rows:
            break

    print(
        f"Finished object: {table_name}; "
        f"selected={accepted_rows:,}; inserted={inserted_rows:,}"
    )
    return accepted_rows, inserted_rows


def main():
    """Create schema and ingest a bounded, representative workflow dataset."""
    config = get_organizer_s3_config()
    bucket = config["BUCKET_NAME"]
    prefix = config.get("DATA_PREFIX", "data/")

    engine = create_engine(
        get_database_url(),
        pool_pre_ping=True,
    )

    run_schema_scripts(engine)
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

    keys_by_table = {
        table_name: []
        for table_name in organizer_tables
    }

    for key in csv_keys:
        keys_by_table[infer_table_name(key, prefix)].append(key)

    for table_name in organizer_tables:
        source_keys = keys_by_table[table_name]

        if not source_keys:
            raise RuntimeError(
                f"No organizer CSV objects found for required table: {table_name}"
            )

        fraction = sample_fractions[table_name]

        if table_name in fact_tables and len(source_keys) > 1:
            selected_keys = _evenly_spaced_keys(
                source_keys,
                fraction,
            )
            # Partition selection already reduces the source before download.
            row_sample_fraction = 1.0
        else:
            selected_keys = source_keys
            # Single-file tables are reduced deterministically inside each chunk.
            row_sample_fraction = fraction

        table_limit = row_limits[table_name]
        per_object_limit = int(
            math.ceil(table_limit / len(selected_keys))
        )

        print(
            f"\n{table_name}: source_objects={len(source_keys)}, "
            f"selected_objects={len(selected_keys)}, "
            f"row_cap={table_limit:,}, "
            f"row_sample_fraction={row_sample_fraction:.3f}"
        )

        writer = PostgresBulkWriter(
            engine=engine,
            table_name=table_name,
        )

        total_selected = 0
        total_inserted = 0

        try:
            for key in selected_keys:
                remaining = table_limit - total_selected
                if remaining <= 0:
                    break

                object_cap = min(per_object_limit, remaining)
                selected, inserted = ingest_csv_object(
                    s3=s3,
                    engine=engine,
                    writer=writer,
                    bucket=bucket,
                    prefix=prefix,
                    key=key,
                    max_rows=object_cap,
                    row_sample_fraction=row_sample_fraction,
                )
                total_selected += selected
                total_inserted += inserted
        finally:
            writer.close()

        print(
            f"Completed {table_name}: selected={total_selected:,}; "
            f"inserted={total_inserted:,}; cap={table_limit:,}"
        )

    engine.dispose()
    print("Fast dispute-workflow S3 -> RDS ingestion completed.")


if __name__ == "__main__":
    main()
