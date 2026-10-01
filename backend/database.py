from functools import lru_cache
from backend.secrets import get_database_url
from sqlalchemy import bindparam, create_engine, text


@lru_cache(maxsize=1)
def get_engine():
    """Create and cache the private RDS SQLAlchemy engine.

    Returns:
        sqlalchemy.Engine: Reusable connection engine for private PostgreSQL.
    """

    return create_engine(
        get_database_url(),
        pool_pre_ping=True,
    )


def get_historical_complaints(complaint_ids):
    """Read historical complaint context for selected complaint IDs.

    Parameters:
        complaint_ids: Complaint IDs returned by the internal FAISS search.

    Returns:
        list: Complaint records needed to build sanitized historical context.
    """

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
            {
                "complaint_ids": complaint_ids,
            },
        ).mappings().all()

    return [dict(row) for row in rows]