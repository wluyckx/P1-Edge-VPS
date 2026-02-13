"""
FastAPI dependency injection providers.

Provides database sessions, Redis clients, and authentication dependencies
for use with FastAPI's Depends() mechanism.

CHANGELOG:
- 2026-02-13: Initial creation (STORY-006)
- 2026-02-13: Add database session dependency (STORY-007)
- 2026-02-13: Add CurrentDeviceId auth dependency (STORY-008)

TODO:
- Add Redis client dependency (STORY-009)
"""

import os
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.bearer import BearerAuth, parse_device_tokens
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

def _build_bearer_auth() -> BearerAuth:
    """Parse DEVICE_TOKENS from the environment and build a BearerAuth instance.

    Called once at module import time so the token map is built at startup (AC5).

    Returns:
        BearerAuth: Configured Bearer token authenticator.
    """
    raw_tokens = os.environ.get("DEVICE_TOKENS", "")
    token_map = parse_device_tokens(raw_tokens)
    return BearerAuth(token_map)


_bearer_auth = _build_bearer_auth()

# Annotated dependency for use in FastAPI route signatures (AC6):
#   async def my_endpoint(device_id: CurrentDeviceId): ...
CurrentDeviceId = Annotated[str, Depends(_bearer_auth.verify)]
