from pathlib import PurePosixPath

import boto3
import pandas as pd
from sqlalchemy import create_engine

from backend.secrets import (
    get_database_url,
    get_organizer_s3_config,
)


chunk_size = 50000


def create_organizer_s3_client():
    """Create a read-only S3 client using organizer credentials from Secrets Manager."""

    config = get_organizer_s3_config()

    return boto3.client(
        "s3",
        region_name=config["AWS_REGION"],
        aws_access_key_id=config["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=config["AWS_SECRET_ACCESS_KEY"],
    )


def infer_table_name(key, prefix):
    """Infer a SQL table name from a root CSV or partitioned S3 path."""

    relative_key = key[len(prefix):].lstrip("/")
    parts = PurePosixPath(relative_key).parts

    if len(parts) == 1:
        return PurePosixPath(parts[0]).stem

    return parts[0]


def list_csv_keys(s3, bucket, prefix):
    """Yield every CSV object under the organizer data prefix."""

    paginator = s3.get_paginator("list_objects_v2")

    for page in paginator.paginate(
        Bucket=bucket,
        Prefix=prefix,
    ):
        for item in page.get("Contents", []):
            key = item["Key"]

            if key.lower().endswith(".csv"):
                yield key


def ingest_csv_object(s3, engine, bucket, prefix, key):
    """Stream one S3 CSV into PostgreSQL without storing the CSV on disk."""

    table_name = infer_table_name(
        key=key,
        prefix=prefix,
    )

    response = s3.get_object(
        Bucket=bucket,
        Key=key,
    )

    body = response["Body"]

    for chunk in pd.read_csv(
        body,
        chunksize=chunk_size,
    ):
        chunk.to_sql(
            name=table_name,
            con=engine,
            if_exists="append",
            index=False,
            method="multi",
            chunksize=2000,
        )


def main():
    """Stream all organizer CSV objects directly from S3 into private RDS."""

    config = get_organizer_s3_config()
    bucket = config["BUCKET_NAME"]
    prefix = config.get("DATA_PREFIX", "data/")

    s3 = create_organizer_s3_client()
    engine = create_engine(
        get_database_url(),
        pool_pre_ping=True,
    )

    for key in list_csv_keys(
        s3=s3,
        bucket=bucket,
        prefix=prefix,
    ):
        ingest_csv_object(
            s3=s3,
            engine=engine,
            bucket=bucket,
            prefix=prefix,
            key=key,
        )


if __name__ == "__main__":
    main()