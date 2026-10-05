from io import StringIO
import math
import os
import re
from pathlib import Path, PurePosixPath

import boto3
import pandas as pd
from psycopg2 import sql
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.sql.sqltypes import Integer

from backend.secrets import get_database_url, get_organizer_s3_config


# Fast hackathon ingestion profile.
# Large fact tables keep one calendar-date partition every N days across the
# complete available history, anchored to the earliest available partition.
read_chunk_size = int(os.getenv("INGEST_READ_CHUNK_SIZE", "50000"))
sample_every_days = int(os.getenv("INGEST_SAMPLE_EVERY_DAYS", "5"))
if sample_every_days <= 0:
    raise ValueError("INGEST_SAMPLE_EVERY_DAYS must be greater than zero")

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

# Dimensions remain sufficiently complete for the application; fact tables are
# intentionally small enough for the complete pipeline to finish quickly.
row_limits = {
    "customers": int(os.getenv("INGEST_CUSTOMERS_MAX_ROWS", "150000")),
    "products": int(os.getenv("INGEST_PRODUCTS_MAX_ROWS", "20000")),
    "transactions": int(os.getenv("INGEST_TRANSACTIONS_MAX_ROWS", "50000")),
    "call_center_interactions": int(
        os.getenv("INGEST_INTERACTIONS_MAX_ROWS", "8000")
    ),
    "call_transcripts": int(os.getenv("INGEST_TRANSCRIPTS_MAX_ROWS", "2000")),
    "complaints": int(os.getenv("INGEST_COMPLAINTS_MAX_ROWS", "800")),
}

fact_tables = {
    "transactions",
    "call_center_interactions",
    "call_transcripts",
    "complaints",
}

date_columns = {
    "transactions": "process_date",
    "call_center_interactions": "process_date",
    "call_transcripts": "process_date",
    "complaints": "process_date",
}

# Current synthetic demo customers. Rows for these customers are retained when
# they occur inside the selected date partitions, even if the ordinary quota for
# that partition has already been reached.
priority_customer_ids = {
    value.strip().upper()
    for value in os.getenv(
        "INGEST_PRIORITY_CUSTOMER_IDS",
        "CLI-G4X2AMVD62NR,CLI-F2DZJYU0POJ9,CLI-8WU28O74XKHS",
    ).split(",")
    if value.strip()
}


class PostgresBulkWriter:
    """COPY into a temporary table, then insert while ignoring conflicts."""

    def __init__(self, engine, table_name):
        self.connection = engine.raw_connection()
        self.cursor = self.connection.cursor()
        self.table_name = table_name
        self.stage_name = f"_stage_{table_name}_{os.getpid()}"
        self.columns = None
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
            inserted_rows = max(self.cursor.rowcount, 0)
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
    """Create the organizer read-only S3 client."""
    config = get_organizer_s3_config()

    return boto3.client(
        "s3",
        region_name=config["AWS_REGION"],
        aws_access_key_id=config["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=config["AWS_SECRET_ACCESS_KEY"],
    )


def infer_table_name(key, prefix):
    """Infer the destination table from a root CSV or partitioned key."""
    relative_key = key[len(prefix):].lstrip("/")
    parts = PurePosixPath(relative_key).parts

    if len(parts) == 1:
        return PurePosixPath(parts[0]).stem

    return parts[0]


def _partition_date_from_key(key):
    """Return the full calendar date encoded in a common partitioned S3 path."""
    patterns = [
        r"(?:^|/)year[=_-]?(\d{4})/month[=_-]?(\d{1,2})/day[=_-]?(\d{1,2})(?:/|$)",
        r"(?:^|/)(20\d{2})/(\d{1,2})/(\d{1,2})(?:/|$)",
        r"(?:^|/)(20\d{2})-(\d{1,2})-(\d{1,2})(?:/|_|\.)",
    ]

    for pattern in patterns:
        match = re.search(pattern, key, flags=re.IGNORECASE)
        if not match:
            continue
        try:
            return pd.Timestamp(
                year=int(match.group(1)),
                month=int(match.group(2)),
                day=int(match.group(3)),
            ).date()
        except ValueError:
            continue

    return None


def run_schema_scripts(engine):
    """Create the six organizer tables plus application tables."""
    sql_dir = Path(__file__).resolve().parents[1] / "backend" / "sql"
    sql_files = sorted(sql_dir.glob("*.sql"))

    if not sql_files:
        raise RuntimeError(f"No SQL schema files found in {sql_dir}")

    with engine.begin() as connection:
        for sql_file in sql_files:
            sql_text = sql_file.read_text(encoding="utf-8")
            connection.exec_driver_sql(sql_text)
            print(f"Applied schema: {sql_file.name}")


def reset_organizer_tables(engine):
    """Optionally clear old organizer data before a reproducible sampled load."""
    if os.getenv("INGEST_RESET_EXISTING", "0").strip() not in {"1", "true", "TRUE"}:
        return

    with engine.begin() as connection:
        for table_name in reversed(organizer_tables):
            connection.execute(text(f'TRUNCATE TABLE "{table_name}"'))
            print(f"Cleared existing table: {table_name}")


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


def _select_keys_for_table(table_name, keys):
    """Keep one partition every configured number of calendar days."""
    if table_name not in fact_tables:
        return list(keys), None

    parsed = [
        (key, _partition_date_from_key(key))
        for key in keys
    ]
    parsed_dates = [partition_date for _, partition_date in parsed if partition_date is not None]

    # Current organizer fact tables expose year/month/day in their S3 paths.
    # If a future source does not, retain the objects and let the row-level
    # process_date filter apply using the first valid date it observes.
    if not parsed_dates:
        return list(keys), None

    anchor_date = min(parsed_dates)
    selected = [
        key
        for key, partition_date in parsed
        if partition_date is not None
        and (partition_date - anchor_date).days % sample_every_days == 0
    ]

    if not selected:
        raise RuntimeError(
            f"No {table_name} partitions matched the every-{sample_every_days}-calendar-day sample "
            f"anchored at {anchor_date.isoformat()}"
        )

    return selected, anchor_date


def validate_target_table(engine, table_name, csv_columns):
    """Verify the target table exists and supports all CSV columns."""
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



def _canonicalize_country_values(frame):
    """Canonicalize known LATAM country labels used across RDS/Cognito/policy logic."""
    if frame.empty:
        return frame

    canonical = {
        "mexico": "Mexico",
        "colombia": "Colombia",
        "argentina": "Argentina",
        "brasil": "Brazil",
        "brazil": "Brazil",
    }

    def normalize_key(value):
        if pd.isna(value):
            return value
        import unicodedata
        normalized = unicodedata.normalize("NFKD", str(value).strip())
        normalized = "".join(
            char for char in normalized
            if not unicodedata.combining(char)
        ).casefold()
        return canonical.get(normalized, str(value).strip())

    result = frame.copy()
    for column_name in ("country", "transaction_country"):
        if column_name in result.columns:
            result[column_name] = result[column_name].map(normalize_key)
    return result

def _normalize_frame_for_postgres(engine, table_name, frame):
    """Validate required values and normalize pandas dtypes before PostgreSQL COPY.

    The organizer data can contain malformed source rows.  PostgreSQL must not be
    weakened to accept them.  Rows with NULL values in columns declared NOT NULL
    in the target table are skipped before quota accounting, and nullable INTEGER
    columns promoted by pandas to float (for example 701 -> 701.0) are converted
    back to nullable integer dtype so COPY serializes them as 701.
    """
    if frame.empty:
        return frame

    inspector = inspect(engine)
    database_columns = inspector.get_columns(table_name)

    required_columns = [
        column["name"]
        for column in database_columns
        if not column.get("nullable", True)
        and column["name"] in frame.columns
    ]

    if required_columns:
        missing_required = frame[required_columns].isna()
        invalid_rows = missing_required.any(axis=1)
        if invalid_rows.any():
            counts = {
                column_name: int(missing_required[column_name].sum())
                for column_name in required_columns
                if missing_required[column_name].any()
            }
            dropped = int(invalid_rows.sum())
            print(
                f"Skipping {dropped:,} invalid {table_name} row(s) with NULL "
                f"in NOT NULL column(s): {counts}"
            )
            frame = frame.loc[~invalid_rows].copy()

    if frame.empty:
        return frame

    integer_columns = [
        column["name"]
        for column in database_columns
        if isinstance(column["type"], Integer)
        and column["name"] in frame.columns
    ]

    for column_name in integer_columns:
        numeric = pd.to_numeric(frame[column_name], errors="coerce")

        original_non_null = frame[column_name].notna()
        invalid_mask = original_non_null & numeric.isna()
        if invalid_mask.any():
            bad_value = frame.loc[invalid_mask, column_name].iloc[0]
            raise ValueError(
                f"{table_name}.{column_name} contains a non-numeric value "
                f"that cannot be loaded into PostgreSQL INTEGER: {bad_value!r}"
            )

        non_integral_mask = numeric.notna() & ((numeric % 1).abs() > 1e-9)
        if non_integral_mask.any():
            bad_value = frame.loc[non_integral_mask, column_name].iloc[0]
            raise ValueError(
                f"{table_name}.{column_name} contains a non-integral value "
                f"that cannot be loaded into PostgreSQL INTEGER: {bad_value!r}"
            )

        frame[column_name] = numeric.round().astype("Int64")

    return frame


def _filter_sampled_dates(frame, table_name, sampling_anchor=None):
    """Keep rows whose process date is on the every-N-calendar-day sampling grid."""
    if table_name not in fact_tables or frame.empty:
        return frame

    date_column = date_columns[table_name]
    if date_column not in frame.columns:
        return frame

    parsed_dates = pd.to_datetime(frame[date_column], errors="coerce")
    valid_dates = parsed_dates.dropna()
    if valid_dates.empty:
        return frame.iloc[0:0]

    anchor = pd.Timestamp(sampling_anchor or valid_dates.min().date())
    day_offsets = (parsed_dates.dt.normalize() - anchor.normalize()).dt.days
    return frame.loc[day_offsets.notna() & (day_offsets.mod(sample_every_days) == 0)]


def _filter_relationships(frame, table_name, allowed_interaction_ids):
    """Ensure transcript rows still join to the sampled interactions."""
    if (
        table_name == "call_transcripts"
        and allowed_interaction_ids is not None
        and "interaction_id" in frame.columns
    ):
        return frame.loc[
            frame["interaction_id"].astype(str).isin(allowed_interaction_ids)
        ]

    return frame


def _split_priority_rows(frame):
    """Separate current demo-customer rows from ordinary quota-controlled rows."""
    if frame.empty or "customer_id" not in frame.columns or not priority_customer_ids:
        return frame.iloc[0:0], frame

    normalized = frame["customer_id"].astype(str).str.upper()
    priority_mask = normalized.isin(priority_customer_ids)
    return frame.loc[priority_mask], frame.loc[~priority_mask]


def ingest_csv_object(
    s3,
    engine,
    writer,
    bucket,
    prefix,
    key,
    table_name,
    ordinary_quota,
    allowed_interaction_ids=None,
    sampling_anchor=None,
):
    """Stream one source object, keeping only the configured reduced sample."""
    print(
        f"Loading s3://{bucket}/{key} -> {table_name} "
        f"(ordinary object quota={ordinary_quota:,})"
    )

    response = s3.get_object(Bucket=bucket, Key=key)
    body = response["Body"]
    first_chunk = True
    ordinary_accepted = 0
    inserted_rows = 0
    priority_seen = set()

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

        chunk = _filter_sampled_dates(
            chunk,
            table_name,
            sampling_anchor=sampling_anchor,
        )
        chunk = _filter_relationships(
            chunk,
            table_name,
            allowed_interaction_ids,
        )

        chunk = _canonicalize_country_values(chunk)

        if chunk.empty:
            continue

        # Normalize and reject malformed source rows BEFORE quota accounting.
        # This prevents a bad row (for example a NULL call_transcripts.duration_seconds)
        # from consuming sample quota or aborting PostgreSQL COPY.
        chunk = _normalize_frame_for_postgres(
            engine=engine,
            table_name=table_name,
            frame=chunk,
        )

        if chunk.empty:
            continue

        priority_rows, ordinary_rows = _split_priority_rows(chunk)

        # Avoid writing the same priority primary-key row twice when source
        # duplicates exist. Database ON CONFLICT remains the final guard.
        primary_key_candidates = {
            "transactions": "transaction_id",
            "call_center_interactions": "interaction_id",
            "call_transcripts": "transcript_id",
            "complaints": "complaint_id",
        }
        priority_pk = primary_key_candidates.get(table_name)
        if priority_pk and priority_pk in priority_rows.columns:
            keep_mask = []
            for value in priority_rows[priority_pk].astype(str):
                if value in priority_seen:
                    keep_mask.append(False)
                else:
                    priority_seen.add(value)
                    keep_mask.append(True)
            priority_rows = priority_rows.loc[keep_mask]

        remaining = max(ordinary_quota - ordinary_accepted, 0)
        ordinary_rows = ordinary_rows.iloc[:remaining]
        ordinary_accepted += len(ordinary_rows)

        output = pd.concat(
            [priority_rows, ordinary_rows],
            ignore_index=True,
        )

        if not output.empty:
            inserted_rows += writer.write(output)

        if ordinary_accepted >= ordinary_quota:
            # Continue only if priority rows could still matter in later chunks.
            # For dimensions we do not use the priority exception.
            if table_name not in fact_tables or not priority_customer_ids:
                break

    print(
        f"Finished object: {table_name}; "
        f"ordinary accepted={ordinary_accepted:,}; inserted={inserted_rows:,}"
    )
    return ordinary_accepted, inserted_rows


def _load_sampled_interaction_ids(engine):
    """Read the small sampled interaction-ID set for transcript filtering."""
    frame = pd.read_sql(
        "SELECT interaction_id FROM call_center_interactions",
        engine,
    )
    return set(frame["interaction_id"].astype(str))


def main():
    """Create schema and ingest the fast date-partitioned sample into RDS."""
    config = get_organizer_s3_config()
    bucket = config["BUCKET_NAME"]
    prefix = config.get("DATA_PREFIX", "data/")

    engine = create_engine(
        get_database_url(),
        pool_pre_ping=True,
    )

    run_schema_scripts(engine)
    reset_organizer_tables(engine)

    s3 = create_organizer_s3_client()
    all_keys = list_csv_keys(s3=s3, bucket=bucket, prefix=prefix)

    if not all_keys:
        raise RuntimeError(
            f"No dispute-workflow organizer CSV files found under "
            f"s3://{bucket}/{prefix}"
        )

    keys_by_table = {
        table_name: [
            key
            for key in all_keys
            if infer_table_name(key, prefix) == table_name
        ]
        for table_name in organizer_tables
    }

    for table_name in organizer_tables:
        source_keys = keys_by_table[table_name]
        if not source_keys:
            raise RuntimeError(f"No organizer CSV found for {table_name}")

        selected_keys, sampling_anchor = _select_keys_for_table(table_name, source_keys)
        table_limit = row_limits[table_name]
        writer = PostgresBulkWriter(engine, table_name)
        accepted_total = 0
        inserted_total = 0

        allowed_interaction_ids = None
        if table_name == "call_transcripts":
            allowed_interaction_ids = _load_sampled_interaction_ids(engine)
            print(
                f"Transcript relationship filter: "
                f"{len(allowed_interaction_ids):,} sampled interaction IDs"
            )

        try:
            for key_index, key in enumerate(selected_keys):
                remaining_total = table_limit - accepted_total
                if remaining_total <= 0:
                    break

                remaining_keys = len(selected_keys) - key_index
                object_quota = max(
                    1,
                    int(math.ceil(remaining_total / remaining_keys)),
                )

                accepted, inserted = ingest_csv_object(
                    s3=s3,
                    engine=engine,
                    writer=writer,
                    bucket=bucket,
                    prefix=prefix,
                    key=key,
                    table_name=table_name,
                    ordinary_quota=object_quota,
                    allowed_interaction_ids=allowed_interaction_ids,
                    sampling_anchor=sampling_anchor,
                )
                accepted_total += accepted
                inserted_total += inserted
        finally:
            writer.close()

        print(
            f"TABLE COMPLETE {table_name}: "
            f"ordinary sample={accepted_total:,}/{table_limit:,}; "
            f"inserted={inserted_total:,}; source objects used={len(selected_keys):,}"
        )

    engine.dispose()
    print(
        "Fast sampled S3 -> RDS ingestion completed. "
        f"Sample interval={sample_every_days} calendar days"
    )


if __name__ == "__main__":
    main()
