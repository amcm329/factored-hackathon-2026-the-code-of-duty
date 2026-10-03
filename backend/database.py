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


def get_historical_complaints(complaint_ids):
    """Read historical complaint context for selected complaint IDs."""

    if not complaint_ids:
        return []

    query = text(
        """
        SELECT
            complaint_id,
            category,
            subcategory,
            description,
            priority,
            status,
            resolution
        FROM complaints
        WHERE complaint_id IN :complaint_ids
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
            {"complaint_ids": complaint_ids},
        ).mappings().all()

    return [dict(row) for row in rows]


def get_customer_transactions(customer_id, limit=20):
    """Read recent transactions belonging to one authenticated customer."""

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
            amount_usd,
            channel,
            merchant_name,
            merchant_category,
            transaction_country,
            transaction_city,
            transaction_status,
            is_fraud,
            fraud_score
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
        SELECT *
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


def create_dispute_case(customer_id, transaction_id, reason, escalation_probability, requires_human_review):
    """Create and persist one finalized dispute case."""

    transaction = get_customer_transaction(
        customer_id=customer_id,
        transaction_id=transaction_id,
    )

    if transaction is None:
        raise LookupError("Transaction does not belong to the authenticated customer")

    dispute_id = str(uuid.uuid4())
    status = "ESCALATED" if requires_human_review else "RESOLVED"
    query = text(
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

    with get_engine().begin() as connection:
        row = connection.execute(
            query,
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

    return dict(row)


def get_dispute_case(customer_id, dispute_id):
    """Read one dispute owned by the authenticated customer."""

    query = text(
        """
        SELECT *
        FROM dispute_cases
        WHERE customer_id = :customer_id
          AND dispute_id = CAST(:dispute_id AS UUID)
        LIMIT 1
        """
    )

    with get_engine().connect() as connection:
        row = connection.execute(
            query,
            {
                "customer_id": customer_id,
                "dispute_id": dispute_id,
            },
        ).mappings().first()

    return dict(row) if row else None


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


def record_interaction_turn(interaction_id, total_tokens):
    """Persist one completed chat turn for metric aggregation."""

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
        RETURNING interaction_id, turn_count, total_tokens, started_at
        """
    )

    with get_engine().begin() as connection:
        row = connection.execute(
            query,
            {
                "interaction_id": interaction_id,
                "total_tokens": int(total_tokens),
            },
        ).mappings().first()

    if row is None:
        raise RuntimeError("Interaction metric write was not confirmed")


def get_interaction_metrics(interaction_id):
    """Read accumulated interaction metrics and current end-to-end latency."""

    query = text(
        """
        SELECT
            interaction_id,
            turn_count,
            total_tokens,
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
