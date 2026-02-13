"""
Async database engine and session factory.

Uses SQLAlchemy 2.x async engine with asyncpg driver for PostgreSQL.

CHANGELOG:
- 2026-02-13: Initial creation (STORY-006)

TODO:
- Wire into FastAPI dependency injection (STORY-007)
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from vps.src.config import get_settings


def create_engine():
    """Create an async SQLAlchemy engine from configuration.

    Returns:
        AsyncEngine: Configured async engine for PostgreSQL via asyncpg.
    """
    settings = get_settings()
    return create_async_engine(settings.DATABASE_URL, echo=False)


def create_session_factory(engine=None):
    """Create an async session factory.

    Args:
        engine: Optional async engine. If not provided, creates one from config.

    Returns:
        async_sessionmaker: Factory for creating AsyncSession instances.
    """
    if engine is None:
        engine = create_engine()
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
