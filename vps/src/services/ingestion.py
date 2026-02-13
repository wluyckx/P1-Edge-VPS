"""
Ingestion service for P1 energy telemetry samples.

Provides the core database operation for bulk-inserting samples using
PostgreSQL INSERT ... ON CONFLICT DO NOTHING for idempotent ingestion.

CHANGELOG:
- 2026-02-13: Guard against empty sample list (quality fix #2)
- 2026-02-13: Initial creation (STORY-009)

TODO:
- None
"""

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import P1Sample


async def ingest_samples(session: AsyncSession, samples: list[dict]) -> int:
    """Insert energy samples with ON CONFLICT DO NOTHING.

    Uses PostgreSQL dialect INSERT ... ON CONFLICT (device_id, ts) DO NOTHING
    to skip duplicate rows based on the composite primary key. This makes the
    operation idempotent: sending the same batch twice inserts zero new rows
    on the second call.

    Args:
        session: Async SQLAlchemy session for database operations.
        samples: List of sample dictionaries matching P1Sample columns.

    Returns:
        int: Number of newly inserted rows (excludes duplicates).
    """
    if not samples:
        return 0

    stmt = (
        insert(P1Sample)
        .values(samples)
        .on_conflict_do_nothing(
            index_elements=["device_id", "ts"],
        )
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount
