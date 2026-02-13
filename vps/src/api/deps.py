"""
FastAPI dependency injection providers.

Provides database sessions, Redis clients, and authentication dependencies
for use with FastAPI's Depends() mechanism.

CHANGELOG:
- 2026-02-13: Initial creation (STORY-006)
- 2026-02-13: Add database session dependency (STORY-007)
- 2026-02-13: Add CurrentDeviceId auth dependency (STORY-008)
- 2026-02-13: Fix: lazy auth init via get_settings() (review finding #1)

TODO:
- Add Redis client dependency (STORY-009)
"""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.bearer import BearerAuth, parse_device_tokens
from src.config import get_settings
from src.db.session import get_async_session

# Type alias for injecting an async DB session via FastAPI Depends().
# Usage in route handlers:
#   async def my_route(db: DbSession):
#       result = await db.execute(...)
DbSession = Annotated[AsyncSession, Depends(get_async_session)]


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session.

    This is a convenience wrapper around get_async_session for cases
    where a plain dependency function is preferred over the Annotated alias.

    Yields:
        AsyncSession: An async SQLAlchemy session.
    """
    async for session in get_async_session():
        yield session


# ---------------------------------------------------------------------------
# Authentication dependency (STORY-008)
# ---------------------------------------------------------------------------

_bearer_auth: BearerAuth | None = None


def _get_bearer_auth() -> BearerAuth:
    """Lazily build BearerAuth from settings on first use.

    Uses get_settings() to load DEVICE_TOKENS, which respects .env files
    and Pydantic BaseSettings loading. Cached after first call.

    Returns:
        BearerAuth: Configured Bearer token authenticator.
    """
    global _bearer_auth  # noqa: PLW0603
    if _bearer_auth is None:
        settings = get_settings()
        token_map = parse_device_tokens(settings.DEVICE_TOKENS)
        _bearer_auth = BearerAuth(token_map)
    return _bearer_auth


async def get_current_device_id(request: Request) -> str:
    """FastAPI dependency that validates Bearer token and returns device_id.

    Lazily initializes the BearerAuth instance on first request.

    Args:
        request: The incoming FastAPI request.

    Returns:
        str: The device_id associated with the valid Bearer token.
    """
    auth = _get_bearer_auth()
    return await auth.verify(request)


# Annotated dependency for use in FastAPI route signatures (AC6):
#   async def my_endpoint(device_id: CurrentDeviceId): ...
CurrentDeviceId = Annotated[str, Depends(get_current_device_id)]
