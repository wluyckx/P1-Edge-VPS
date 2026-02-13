"""
Async database engine and session factory.

Uses SQLAlchemy 2.x async engine with asyncpg driver for PostgreSQL.
Provides module-level engine and session factory singletons, plus an
async generator for FastAPI dependency injection.

CHANGELOG:
- 2026-02-13: Initial creation (STORY-006)
- 2026-02-13: Add async_engine, async_session_factory, get_async_session (STORY-007)

TODO:
- None
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.config import get_settings

# Module-level singletons, initialized lazily via init_engine().
async_engine: AsyncEngine | None = None
async_session_factory: async_sessionmaker[AsyncSession] | None = None


def create_engine() -> AsyncEngine:
    """Create an async SQLAlchemy engine from configuration.

    Returns:
        AsyncEngine: Configured async engine for PostgreSQL via asyncpg.
    """
    settings = get_settings()
    return create_async_engine(settings.DATABASE_URL, echo=False)


def create_session_factory(engine: AsyncEngine | None = None) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory.

    Args:
        engine: Optional async engine. If not provided, creates one from config.

    Returns:
        async_sessionmaker: Factory for creating AsyncSession instances.
    """
    if engine is None:
        engine = create_engine()
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def init_engine() -> None:
    """Initialize the module-level async engine and session factory.

    Call this at application startup (e.g., in a FastAPI lifespan event).
    Safe to call multiple times; subsequent calls are no-ops.
    """
    global async_engine, async_session_factory  # noqa: PLW0603
    if async_engine is None:
        async_engine = create_engine()
        async_session_factory = create_session_factory(async_engine)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session for FastAPI dependency injection.

    Initializes the engine on first call if not already done.
    The session is automatically closed after the request completes.

    Yields:
        AsyncSession: An async SQLAlchemy session.
    """
    init_engine()
    assert async_session_factory is not None, "Session factory not initialized"
    async with async_session_factory() as session:
        yield session
