"""
Redis client for cache operations.

Provides helper functions for creating Redis connections and invalidating
device-specific cache entries. Cache invalidation is best-effort: connection
failures are logged but do not propagate exceptions.

CHANGELOG:
- 2026-02-13: Initial creation (STORY-009)

TODO:
- None
"""

import logging

import redis.asyncio as redis

from src.config import get_settings

logger = logging.getLogger(__name__)


async def get_redis() -> redis.Redis:
    """Create and return an async Redis client from application settings.

    Reads REDIS_URL from the environment-based Settings and returns
    a configured redis.asyncio.Redis instance.

    Returns:
        redis.Redis: Async Redis client.
    """
    settings = get_settings()
    return redis.from_url(settings.REDIS_URL)


async def invalidate_device_cache(device_id: str) -> None:
    """Delete the realtime cache key for a device.

    Best-effort operation: if Redis is unavailable or the delete fails,
    the error is logged but not raised. This ensures that ingest operations
    are not blocked by cache infrastructure issues.

    Args:
        device_id: The device identifier whose cache should be cleared.
    """
    try:
        client = await get_redis()
        try:
            await client.delete(f"realtime:{device_id}")
        finally:
            await client.aclose()
    except Exception:
        logger.warning(
            "Failed to invalidate cache for device %s", device_id, exc_info=True,
        )
