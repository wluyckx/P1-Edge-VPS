"""
FastAPI dependency injection providers.

Provides database sessions, Redis clients, and authentication dependencies
for use with FastAPI's Depends() mechanism.

CHANGELOG:
- 2026-02-14: Use Security(HTTPBearer) for OpenAPI security metadata (STORY-016 AC5)
- 2026-02-13: Initial creation (STORY-006)
- 2026-02-13: Add database session dependency (STORY-007)
- 2026-02-13: Add CurrentDeviceId auth dependency (STORY-008)
- 2026-02-13: Fix: lazy auth init via get_settings() (review finding #1)

TODO:
- None
"""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.bearer import (
    BearerAuth,
    parse_device_tokens,
    verify_bearer_token,
)
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
# Authentication dependency (STORY-008, STORY-016)
# ---------------------------------------------------------------------------

_bearer_auth: BearerAuth | None = None

# Module-level HTTPBearer scheme so FastAPI registers it in OpenAPI
# securitySchemes (AC5). auto_error=False lets us return 401 ourselves
# instead of FastAPI's default 403.
_bearer_scheme = HTTPBearer(auto_error=False)


def init_bearer_auth() -> BearerAuth:
    """Build BearerAuth from settings.

    Intended to be called at startup (via lifespan) so that token
    configuration is validated eagerly. Also called lazily on first
    request as a safety net.

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


async def get_current_device_id(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer_scheme),
) -> str:
    """FastAPI dependency: validates Bearer token → returns device_id.

    Uses Security(HTTPBearer) so the scheme appears in OpenAPI docs.
    Lazily initializes the token map on first request.

    Args:
        credentials: Extracted by FastAPI from the Authorization header.

    Returns:
        str: The device_id associated with the valid Bearer token.

    Raises:
        HTTPException: 401 if credentials are missing or token invalid.
    """
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Missing authorization credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    auth = init_bearer_auth()
    device_id = verify_bearer_token(credentials.credentials, auth.token_map)
    if device_id is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return device_id


# Annotated dependency for use in FastAPI route signatures:
#   async def my_endpoint(device_id: CurrentDeviceId): ...
CurrentDeviceId = Annotated[str, Depends(get_current_device_id)]
