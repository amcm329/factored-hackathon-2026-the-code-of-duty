import uuid
from functools import lru_cache

from sqlalchemy import bindparam, create_engine, text

from backend.secrets import get_database_url


@lru_cache(maxsize=1)
def get_engine():
    """Create and cache the private RDS SQLAlchemy engine."""

    return create_engine(
        get_database_url(),
        pool_pre_ping=True,
    )


def get_historical_complaints(complaint_ids, country):
    """Read historical complaint context restricted to one customer country."""

    if not complaint_ids:
        return []

    query = text(
        """
        SELECT
            c.complaint_id,
            c.category,
            c.subcategory,
            c.description,
            c.priority,
            c.status,
            c.resolution
        FROM complaints c
        JOIN customers u
          ON u.customer_id = c.customer_id
        WHERE c.complaint_id IN :complaint_ids
          AND LOWER(u.country) = LOWER(:country)
        """
    ).bindparams(
        bindparam(
            "complaint_ids",
            expanding=True,
        )
    )

    with get_engine().connect() as connection:
        rows = connection.execute(
            query,
            {
                "complaint_ids": complaint_ids,
                "country": country,
            },
        ).mappings().all()

    return [dict(row) for row in rows]


def get_customer_segment(customer_id):
    """Read the existing segment for one authenticated customer."""

    query = text(
        """
        SELECT segment
        FROM customers
        WHERE customer_id = :customer_id
        LIMIT 1
        """
    )

    with get_engine().connect() as connection:
        row = connection.execute(
            query,
            {"customer_id": customer_id},
        ).mappings().first()

    if row is None:
        raise LookupError("Authenticated customer was not found")

    return row["segment"]


def get_customer_transactions(customer_id, limit=20):
    """Read recent transactions needed for explicit customer selection."""

    query = text(
        """
        SELECT
            transaction_id,
            transaction_date,
            product_id,
            transaction_type,
            transaction_category,
            amount,
            currency,
            channel,
            merchant_name,
            merchant_category,
            transaction_country,
            transaction_city
        FROM transactions
        WHERE customer_id = :customer_id
        ORDER BY transaction_date DESC
        LIMIT :limit
        """
    )

    with get_engine().connect() as connection:
        rows = connection.execute(
            query,
            {
                "customer_id": customer_id,
                "limit": int(limit),
            },
        ).mappings().all()

    return [dict(row) for row in rows]


def get_customer_transaction(customer_id, transaction_id):
    """Read one transaction only when it belongs to the authenticated customer."""

    query = text(
        """
        SELECT
            transaction_id,
            product_id,
            amount,
            currency
        FROM transactions
        WHERE customer_id = :customer_id
          AND transaction_id = :transaction_id
        LIMIT 1
        """
    )

    with get_engine().connect() as connection:
        row = connection.execute(
            query,
            {
                "customer_id": customer_id,
                "transaction_id": transaction_id,
            },
        ).mappings().first()

    return dict(row) if row else None


def _validate_evidence_for_dispute(connection, customer_id, evidence_ids):
    """Validate processed, unattached evidence before linking it to a dispute."""

    evidence_ids = list(dict.fromkeys(str(value).strip() for value in evidence_ids if str(value).strip()))

    if len(evidence_ids) > 3:
        raise ValueError("At most three evidence items can be attached to one dispute")

    if not evidence_ids:
        return []

    query = text(
        """
        SELECT
            evidence_id::text AS evidence_id,
            processing_status,
            dispute_id
        FROM dispute_evidence
        WHERE customer_id = :customer_id
          AND CAST(evidence_id AS TEXT) IN :evidence_ids
        """
    ).bindparams(
        bindparam(
            "evidence_ids",
            expanding=True,
        )
    )
    rows = connection.execute(
        query,
        {
            "customer_id": customer_id,
            "evidence_ids": evidence_ids,
        },
    ).mappings().all()

    if len(rows) != len(evidence_ids):
        raise LookupError("One or more evidence items do not belong to the authenticated customer")

    for row in rows:
        if row["processing_status"] != "processed":
            raise ValueError("All evidence must be processed before dispute creation")

        if row["dispute_id"] is not None:
            raise ValueError("Evidence is already attached to another dispute")

    return evidence_ids


def create_dispute_case(customer_id, transaction_id, reason, escalation_probability, requires_human_review, evidence_ids=None):
    """Create one dispute and atomically attach validated evidence."""

    transaction = get_customer_transaction(
        customer_id=customer_id,
        transaction_id=transaction_id,
    )

    if transaction is None:
        raise LookupError("Transaction does not belong to the authenticated customer")

    dispute_id = str(uuid.uuid4())
    status = "ESCALATED" if requires_human_review else "OPEN"
    insert_query = text(
        """
        INSERT INTO dispute_cases (
            dispute_id,
            customer_id,
            transaction_id,
            product_id,
            status,
            reason,
            claimed_amount,
            currency,
            escalation_probability,
            requires_human_review
        )
        VALUES (
            CAST(:dispute_id AS UUID),
            :customer_id,
            :transaction_id,
            :product_id,
            :status,
            :reason,
            :claimed_amount,
            :currency,
            :escalation_probability,
            :requires_human_review
        )
        RETURNING *
        """
    )
    attach_query = text(
        """
        UPDATE dispute_evidence
        SET dispute_id = CAST(:dispute_id AS UUID)
        WHERE customer_id = :customer_id
          AND CAST(evidence_id AS TEXT) IN :evidence_ids
        """
    ).bindparams(
        bindparam(
            "evidence_ids",
            expanding=True,
        )
    )

    with get_engine().begin() as connection:
        valid_evidence_ids = _validate_evidence_for_dispute(
            connection=connection,
            customer_id=customer_id,
            evidence_ids=evidence_ids or [],
        )
        row = connection.execute(
            insert_query,
            {
                "dispute_id": dispute_id,
                "customer_id": customer_id,
                "transaction_id": transaction_id,
                "product_id": transaction["product_id"],
                "status": status,
                "reason": reason,
                "claimed_amount": transaction["amount"],
                "currency": transaction["currency"],
                "escalation_probability": escalation_probability,
                "requires_human_review": requires_human_review,
            },
        ).mappings().first()

        if row is None:
            raise RuntimeError("Dispute database write was not confirmed")

        if valid_evidence_ids:
            result = connection.execute(
                attach_query,
                {
                    "dispute_id": dispute_id,
                    "customer_id": customer_id,
                    "evidence_ids": valid_evidence_ids,
                },
            )

            if result.rowcount != len(valid_evidence_ids):
                raise RuntimeError("Evidence attachment was not fully confirmed")

    return dict(row)


def create_evidence_record(customer_id, evidence_id, s3_key, content_type, file_size_bytes):
    """Create evidence metadata owned by one authenticated customer."""

    query = text(
        """
        INSERT INTO dispute_evidence (
            evidence_id,
            customer_id,
            s3_key,
            content_type,
            file_size_bytes,
            processing_status
        )
        VALUES (
            CAST(:evidence_id AS UUID),
            :customer_id,
            :s3_key,
            :content_type,
            :file_size_bytes,
            'presigned'
        )
        """
    )

    with get_engine().begin() as connection:
        connection.execute(
            query,
            {
                "evidence_id": evidence_id,
                "customer_id": customer_id,
                "s3_key": s3_key,
                "content_type": content_type,
                "file_size_bytes": file_size_bytes,
            },
        )


def get_evidence_record(customer_id, evidence_id):
    """Read evidence metadata only for its authenticated owner."""

    query = text(
        """
        SELECT *
        FROM dispute_evidence
        WHERE customer_id = :customer_id
          AND evidence_id = CAST(:evidence_id AS UUID)
        LIMIT 1
        """
    )

    with get_engine().connect() as connection:
        row = connection.execute(
            query,
            {
                "customer_id": customer_id,
                "evidence_id": evidence_id,
            },
        ).mappings().first()

    return dict(row) if row else None


def update_evidence_status(customer_id, evidence_id, processing_status, file_size_bytes=None):
    """Update processing metadata for customer-owned evidence."""

    query = text(
        """
        UPDATE dispute_evidence
        SET
            processing_status = :processing_status,
            file_size_bytes = COALESCE(:file_size_bytes, file_size_bytes)
        WHERE customer_id = :customer_id
          AND evidence_id = CAST(:evidence_id AS UUID)
        """
    )

    with get_engine().begin() as connection:
        result = connection.execute(
            query,
            {
                "processing_status": processing_status,
                "file_size_bytes": file_size_bytes,
                "customer_id": customer_id,
                "evidence_id": evidence_id,
            },
        )

    if result.rowcount != 1:
        raise LookupError("Evidence does not belong to the authenticated customer")


def start_interaction_metrics(interaction_id):
    """Start the interaction timer before the first chat processing work."""

    query = text(
        """
        INSERT INTO interaction_metrics (
            interaction_id,
            turn_count,
            total_tokens
        )
        VALUES (
            CAST(:interaction_id AS UUID),
            0,
            0
        )
        ON CONFLICT (interaction_id) DO NOTHING
        """
    )

    with get_engine().begin() as connection:
        connection.execute(
            query,
            {"interaction_id": interaction_id},
        )


def record_interaction_turn(interaction_id, total_tokens):
    """Persist one completed OpenAI chat turn for metric aggregation."""

    query = text(
        """
        INSERT INTO interaction_metrics (
            interaction_id,
            turn_count,
            total_tokens
        )
        VALUES (
            CAST(:interaction_id AS UUID),
            1,
            :total_tokens
        )
        ON CONFLICT (interaction_id)
        DO UPDATE SET
            turn_count = interaction_metrics.turn_count + 1,
            total_tokens = interaction_metrics.total_tokens + EXCLUDED.total_tokens
        """
    )

    with get_engine().begin() as connection:
        connection.execute(
            query,
            {
                "interaction_id": interaction_id,
                "total_tokens": int(total_tokens),
            },
        )


def get_interaction_metrics(interaction_id):
    """Read accumulated interaction metrics and current end-to-end latency."""

    query = text(
        """
        SELECT
            interaction_id,
            turn_count,
            total_tokens,
            successful_automated_resolution,
            GREATEST(
                0,
                FLOOR(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - started_at)) * 1000)::BIGINT
            ) AS end_to_end_latency_ms
        FROM interaction_metrics
        WHERE interaction_id = CAST(:interaction_id AS UUID)
        """
    )

    with get_engine().connect() as connection:
        row = connection.execute(
            query,
            {"interaction_id": interaction_id},
        ).mappings().first()

    return dict(row) if row else None


def finalize_interaction_metrics(interaction_id, successful_automated_resolution):
    """Persist the final automated-resolution result and return publishable metrics."""

    start_interaction_metrics(interaction_id)
    query = text(
        """
        UPDATE interaction_metrics
        SET successful_automated_resolution = :successful_automated_resolution
        WHERE interaction_id = CAST(:interaction_id AS UUID)
        """
    )

    with get_engine().begin() as connection:
        result = connection.execute(
            query,
            {
                "interaction_id": interaction_id,
                "successful_automated_resolution": bool(successful_automated_resolution),
            },
        )

    if result.rowcount != 1:
        raise RuntimeError("Interaction metric finalization was not confirmed")

    metrics = get_interaction_metrics(interaction_id)

    if metrics is None:
        raise RuntimeError("Final interaction metrics could not be read")

    return metrics
