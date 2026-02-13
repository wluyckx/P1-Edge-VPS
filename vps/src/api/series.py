"""
Series API endpoint for historical aggregated time series data.

Provides GET /v1/series for querying time-bucketed energy aggregations
across day, month, year, and all-time frames. This is a public endpoint
that does not require authentication.

CHANGELOG:
- 2026-02-13: Initial creation (STORY-012)

TODO:
- None
"""

import logging

from fastapi import APIRouter, HTTPException

from src.api.deps import DbSession
from src.services.aggregation import FRAME_CONFIG, get_aggregated_series

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["series"])


@router.get("/series")
async def get_series(device_id: str, frame: str, db: DbSession) -> dict:
    """Get aggregated time series data for a device.

    Returns time-bucketed aggregations of power and energy data for the
    specified device and time frame. No authentication required.

    Args:
        device_id: Identifier of the P1 meter device.
        frame: Time frame for aggregation (day, month, year, all).
        db: Async database session.

    Returns:
        dict: JSON with device_id, frame, and series array of bucket entries.

    Raises:
        HTTPException: 400 if frame is not a valid option.
    """
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
