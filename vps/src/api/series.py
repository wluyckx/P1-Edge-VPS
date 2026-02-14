"""
Series API endpoint for historical aggregated time series data.

Provides GET /v1/series for querying time-bucketed energy aggregations
across day, month, year, and all-time frames. Requires Bearer token
authentication; callers can only access their own device data.

CHANGELOG:
- 2026-02-14: Add Bearer auth and device_id mismatch validation (STORY-016)
- 2026-02-13: Initial creation (STORY-012)

TODO:
- None
"""

import logging

from fastapi import APIRouter, HTTPException

from src.api.deps import CurrentDeviceId, DbSession
from src.services.aggregation import FRAME_CONFIG, get_aggregated_series

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["series"])


@router.get("/series")
async def get_series(
    device_id: str,
    frame: str,
    db: DbSession,
    auth_device_id: CurrentDeviceId,
) -> dict:
    """Get aggregated time series data for a device.

    Requires Bearer token authentication. The query parameter device_id
    must match the authenticated device_id from the token. Returns
    time-bucketed aggregations of power and energy data for the
    specified device and time frame.

    Args:
        device_id: Identifier of the P1 meter device.
        frame: Time frame for aggregation (day, month, year, all).
        db: Async database session.
        auth_device_id: Authenticated device_id from Bearer token.

    Returns:
        dict: JSON with device_id, frame, and series array of bucket entries.

    Raises:
        HTTPException: 401 if missing/invalid Bearer token.
        HTTPException: 403 if device_id does not match authenticated device.
        HTTPException: 400 if frame is not a valid option.
    """
    # STORY-016 AC4: Verify query device_id matches authenticated device
    if device_id != auth_device_id:
        raise HTTPException(
            status_code=403,
            detail="Device ID mismatch",
        )
    if frame not in FRAME_CONFIG:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid frame: {frame}. Must be one of: {', '.join(FRAME_CONFIG)}",
        )

    series = await get_aggregated_series(db, device_id, frame)

    return {
        "device_id": device_id,
        "frame": frame,
        "series": series,
    }
