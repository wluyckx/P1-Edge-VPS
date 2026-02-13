"""
Health check endpoint that probes DB and Redis connectivity.

Returns a JSON response indicating overall system status and the status
of each dependency (database and Redis). Returns HTTP 200 when all
components are healthy, or HTTP 503 when any component is degraded.

CHANGELOG:
- 2026-02-13: Initial creation (STORY-014)

TODO:
- None
"""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from src.cache.redis_client import get_redis
from src.db.session import get_async_session

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


async def _check_db() -> str:
    """Probe the database with a simple SELECT 1 query.

    Returns:
        "ok" if the query succeeds, "error" otherwise.
    """
    try:
        async for session in get_async_session():
            await session.execute(text("SELECT 1"))
            return "ok"
    except Exception:
        logger.warning("Health check: DB probe failed", exc_info=True)
        return "error"
    return "error"  # pragma: no cover


async def _check_redis() -> str:
    """Probe Redis with a PING command.

    Returns:
        "ok" if the ping succeeds, "error" otherwise.
    """
    try:
        client = await get_redis()
        try:
            await client.ping()
            return "ok"
        finally:
            await client.aclose()
    except Exception:
        logger.warning("Health check: Redis probe failed", exc_info=True)
        return "error"


@router.get("/health")
async def health_check() -> JSONResponse:
    """Rich health check endpoint probing DB and Redis.

    Returns:
        JSONResponse: JSON with status, db, and redis fields.
            HTTP 200 when all components are ok, HTTP 503 when degraded.
    """
    db_status = await _check_db()
    redis_status = await _check_redis()

    all_ok = db_status == "ok" and redis_status == "ok"
    status = "ok" if all_ok else "degraded"
    status_code = 200 if all_ok else 503

    return JSONResponse(
        status_code=status_code,
        content={
            "status": status,
            "db": db_status,
            "redis": redis_status,
        },
    )
