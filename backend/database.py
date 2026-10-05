import json
import uuid
from functools import lru_cache

import boto3
from sqlalchemy import bindparam, create_engine, text

from backend.secrets import get_database_url


@lru_cache(maxsize=1)
def get_engine():
    """Create and cache the private RDS SQLAlchemy engine."""

    return create_engine(
        get_database_url(),
        pool_pre_ping=True,
    )


@lru_cache(maxsize=1)
def get_database_country_names():
    """Reads and caches database country names from AWS Secrets Manager."""

    client = boto3.client("secretsmanager", region_name="us-east-1")
    response = client.get_secret_value(SecretId="factored/database-country-names")
    return json.loads(response["SecretString"])


def get_database_country_name(country):
    """Returns the database country name for an incoming country value."""

    normalized_country = str(country or "").strip().lower()
    return get_database_country_names().get(normalized_country, country)


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

    database_country = get_database_country_name(country)

    with get_engine().connect() as connection:
        rows = connection.execute(
            query,
            {
                "complaint_ids": complaint_ids,
                "country": database_country,
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


def get_customer_transactions(customer_id, limit=20, start_date=None, end_date=None):
    """Read customer transactions, optionally restricted to an inclusive date range."""

    where_clauses = ["customer_id = :customer_id"]
    params = {
        "customer_id": customer_id,
        "limit": int(limit),
    }

    if start_date is not None:
        where_clauses.append("transaction_date >= :start_date")
        params["start_date"] = start_date

    if end_date is not None:
        where_clauses.append("transaction_date < (:end_date + INTERVAL '1 day')")
        params["end_date"] = end_date

    query = text(
        f"""
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
            transaction_city,
            transaction_status
        FROM transactions
        WHERE {' AND '.join(where_clauses)}
        ORDER BY transaction_date DESC
        LIMIT :limit
        """
    )

    with get_engine().connect() as connection:
        rows = connection.execute(
            query,
            params,
        ).mappings().all()

    return [dict(row) for row in rows]

def get_customer_case_history(customer_id, limit=20, cutoff_date=None):
    """Read only currently eligible complaint/dispute records for one customer when a cutoff is supplied."""
    query = text(
        """
        SELECT
            case_id,
            case_date,
            source,
            case_type,
            category,
            status,
            claimed_amount,
            currency,
            summary
        FROM (
            SELECT
                complaint_id::text AS case_id,
                creation_date AS case_date,
                'BANK_HISTORY'::text AS source,
                case_type,
                category,
                status,
                claimed_amount,
                currency,
                description AS summary
            FROM complaints
            WHERE customer_id = :customer_id
              AND (
                    :cutoff_date IS NULL
                    OR creation_date >= CAST(:cutoff_date AS DATE)
                  )

            UNION ALL

            SELECT
                d.dispute_id::text AS case_id,
                d.created_at AS case_date,
                'FACTORED_AI'::text AS source,
                'Dispute'::text AS case_type,
                'Transaction dispute'::text AS category,
                d.status,
                d.claimed_amount,
                d.currency,
                d.reason AS summary
            FROM dispute_cases d
            JOIN transactions t
              ON t.transaction_id = d.transaction_id
             AND t.customer_id = d.customer_id
            WHERE d.customer_id = :customer_id
              AND (
                    :cutoff_date IS NULL
                    OR t.transaction_date >= CAST(:cutoff_date AS DATE)
                  )
        ) AS customer_cases
        ORDER BY case_date DESC
        LIMIT :limit
        """
    )
    with get_engine().connect() as connection:
        rows = connection.execute(
            query,
            {
                "customer_id": customer_id,
                "cutoff_date": cutoff_date,
                "limit": int(limit),
            },
        ).mappings().all()
    return [dict(row) for row in rows]


def get_customer_case(customer_id, case_id, cutoff_date=None):
    """Read one owned, currently eligible case and expose a transaction only when linkage is unambiguous."""

    normalized_case_id = str(case_id or "").strip()
    if not normalized_case_id:
        return None

    if normalized_case_id.upper().startswith("CMP-"):
        query = text(
            """
            WITH owned_complaint AS (
                SELECT *
                FROM complaints
                WHERE customer_id = :customer_id
                  AND UPPER(complaint_id) = UPPER(:case_id)
                  AND (
                        :cutoff_date IS NULL
                        OR creation_date >= CAST(:cutoff_date AS DATE)
                      )
                LIMIT 1
            )
            SELECT
                c.complaint_id::text AS case_id,
                c.creation_date AS case_date,
                'BANK_HISTORY'::text AS source,
                c.case_type,
                c.category,
                c.subcategory,
                c.status,
                c.claimed_amount,
                c.currency,
                c.description AS summary,
                c.resolution,
                c.priority,
                c.affected_product_id,
                tx.transaction_id,
                CASE
                    WHEN tx.candidate_count = 1 THEN 'UNAMBIGUOUS_DERIVED_MATCH'
                    ELSE NULL
                END AS transaction_link_type
            FROM owned_complaint c
            LEFT JOIN LATERAL (
                SELECT
                    COUNT(*) AS candidate_count,
                    CASE WHEN COUNT(*) = 1 THEN MAX(t.transaction_id) END AS transaction_id
                FROM transactions t
                WHERE t.customer_id = c.customer_id
                  AND c.affected_product_id IS NOT NULL
                  AND t.product_id = c.affected_product_id
                  AND c.claimed_amount IS NOT NULL
                  AND t.amount = c.claimed_amount
                  AND c.currency IS NOT NULL
                  AND t.currency = c.currency
                  AND t.transaction_date <= c.creation_date
            ) tx ON TRUE
            """
        )
        params = {
            "customer_id": customer_id,
            "case_id": normalized_case_id,
            "cutoff_date": cutoff_date,
        }
    else:
        try:
            normalized_case_id = str(uuid.UUID(normalized_case_id))
        except (ValueError, AttributeError):
            return None

        query = text(
            """
            SELECT
                d.dispute_id::text AS case_id,
                d.created_at AS case_date,
                'FACTORED_AI'::text AS source,
                'Dispute'::text AS case_type,
                'Transaction dispute'::text AS category,
                NULL::text AS subcategory,
                d.status,
                d.claimed_amount,
                d.currency,
                d.reason AS summary,
                NULL::text AS resolution,
                NULL::text AS priority,
                d.product_id AS affected_product_id,
                d.transaction_id,
                'EXACT_DISPUTE_LINK'::text AS transaction_link_type
            FROM dispute_cases d
            JOIN transactions t
              ON t.transaction_id = d.transaction_id
             AND t.customer_id = d.customer_id
            WHERE d.customer_id = :customer_id
              AND d.dispute_id = CAST(:case_id AS UUID)
              AND (
                    :cutoff_date IS NULL
                    OR t.transaction_date >= CAST(:cutoff_date AS DATE)
                  )
            LIMIT 1
            """
        )
        params = {
            "customer_id": customer_id,
            "case_id": normalized_case_id,
            "cutoff_date": cutoff_date,
        }

    with get_engine().connect() as connection:
        row = connection.execute(query, params).mappings().first()

    return dict(row) if row else None

def get_customer_transaction(customer_id, transaction_id):
    """Read one transaction only when it belongs to the authenticated customer."""

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
    """Create one active dispute per transaction and safely reuse/escalate an existing one."""

    transaction = get_customer_transaction(
        customer_id=customer_id,
        transaction_id=transaction_id,
    )

    if transaction is None:
        raise LookupError("Transaction does not belong to the authenticated customer")

    existing_query = text(
        """
        SELECT *
        FROM dispute_cases
        WHERE customer_id = :customer_id
          AND transaction_id = :transaction_id
          AND status IN ('OPEN', 'ESCALATED')
        ORDER BY created_at DESC
        LIMIT 1
        """
    )
    escalate_existing_query = text(
        """
        UPDATE dispute_cases
        SET
            status = 'ESCALATED',
            requires_human_review = TRUE,
            escalation_probability = COALESCE(:escalation_probability, escalation_probability),
            updated_at = CURRENT_TIMESTAMP
        WHERE dispute_id = CAST(:dispute_id AS UUID)
        RETURNING *
        """
    )

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
    ).bindparams(bindparam("evidence_ids", expanding=True))

    with get_engine().begin() as connection:
        existing = connection.execute(
            existing_query,
            {
                "customer_id": customer_id,
                "transaction_id": transaction_id,
            },
        ).mappings().first()

        valid_evidence_ids = _validate_evidence_for_dispute(
            connection=connection,
            customer_id=customer_id,
            evidence_ids=evidence_ids or [],
        )

        if existing is not None:
            row = dict(existing)
            if requires_human_review and row.get("status") != "ESCALATED":
                updated = connection.execute(
                    escalate_existing_query,
                    {
                        "dispute_id": str(row["dispute_id"]),
                        "escalation_probability": escalation_probability,
                    },
                ).mappings().first()
                if updated is None:
                    raise RuntimeError("Existing dispute escalation was not confirmed")
                row = dict(updated)

            if valid_evidence_ids:
                result = connection.execute(
                    attach_query,
                    {
                        "dispute_id": str(row["dispute_id"]),
                        "customer_id": customer_id,
                        "evidence_ids": valid_evidence_ids,
                    },
                )
                if result.rowcount != len(valid_evidence_ids):
                    raise RuntimeError("Evidence attachment was not fully confirmed")
            return row

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
