"""
Realtime metrics API endpoint for P1 energy telemetry.

Serves the latest sample for a given device_id via GET /v1/realtime.
Uses Redis as a read-through cache with TTL-based expiry. Cache operations
are best-effort: Redis failures fall through to the database.

CHANGELOG:
- 2026-02-13: Initial creation (STORY-010)

TODO:
- None
"""

import json
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text

from src.api.deps import DbSession
from src.cache.redis_client import get_redis
from src.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["realtime"])


# ---------------------------------------------------------------------------
# Pydantic response schema
# ---------------------------------------------------------------------------


class RealtimeResponse(BaseModel):
    """Schema for the realtime metrics response.

    Attributes:
        device_id: Identifier of the P1 meter device.
        ts: Measurement timestamp (ISO 8601 with timezone).
        power_w: Current power in watts.
        import_power_w: Import power in watts.
        energy_import_kwh: Cumulative energy imported from grid (kWh).
        energy_export_kwh: Cumulative energy exported to grid (kWh).
    """

    device_id: str
    ts: str
    power_w: int
    import_power_w: int
    energy_import_kwh: float | None
    energy_export_kwh: float | None


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


async def _cache_get(device_id: str) -> dict | None:
    """Attempt to read cached realtime data from Redis.

    Best-effort: returns None on any Redis failure so the caller
    falls through to the database.

    Args:
        device_id: The device identifier to look up.

    Returns:
        dict or None: Cached sample dict, or None on miss/failure.
    """
    try:
        client = await get_redis()
        try:
            raw = await client.get(f"realtime:{device_id}")
            if raw is not None:
                return json.loads(raw)
        finally:
            await client.aclose()
    except Exception:
        logger.warning(
            "Redis cache read failed for device %s", device_id, exc_info=True,
        )
    return None


async def _cache_set(device_id: str, data: dict) -> None:
    """Attempt to write realtime data to the Redis cache.

    Best-effort: logs and suppresses any Redis failure.

    Args:
        device_id: The device identifier for the cache key.
        data: Sample dict to cache as JSON.
    """
    try:
        settings = get_settings()
        client = await get_redis()
        try:
            await client.set(
                f"realtime:{device_id}",
                json.dumps(data),
                ex=settings.CACHE_TTL_S,
            )
        finally:
            await client.aclose()
    except Exception:
        logger.warning(
            "Redis cache write failed for device %s", device_id, exc_info=True,
        )


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@router.get("/realtime", response_model=RealtimeResponse)
async def get_realtime(
    db: DbSession,
    device_id: str = Query(..., description="Device identifier"),
) -> RealtimeResponse:
    """Return the latest P1 sample for a device.

    Checks Redis cache first; on miss, queries the database for the most
    recent sample, caches the result, and returns it. Returns 404 if no
    data exists for the given device_id.

    Args:
        db: Async database session (injected).
        device_id: Device identifier from query parameter.

    Returns:
        RealtimeResponse: Latest sample data.

    Raises:
        HTTPException: 404 if no data found for the device_id.
    """
    # AC3: Try cache first
    cached = await _cache_get(device_id)
    if cached is not None:
        return RealtimeResponse(**cached)

    # AC4: Cache miss -> query DB
    result = await db.execute(
        text(
            "SELECT device_id, ts, power_w, import_power_w,"
            " energy_import_kwh, energy_export_kwh"
            " FROM p1_samples"
            " WHERE device_id = :device_id"
            " ORDER BY ts DESC LIMIT 1"
        ),
        {"device_id": device_id},
    )
    row = result.fetchone()

    # AC6: No data -> 404
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"No data found for device_id '{device_id}'",
        )

    # Build response dict
    ts_value = row.ts
    if isinstance(ts_value, datetime):
        ts_str = ts_value.isoformat()
    else:
        ts_str = str(ts_value)

    data = {
        "device_id": row.device_id,
        "ts": ts_str,
        "power_w": row.power_w,
        "import_power_w": row.import_power_w,
        "energy_import_kwh": row.energy_import_kwh,
        "energy_export_kwh": row.energy_export_kwh,
    }

    # AC5: Cache the result
    await _cache_set(device_id, data)

    return RealtimeResponse(**data)
