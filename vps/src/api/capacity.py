"""
Capacity tariff API endpoint for 15-minute peak data (STORY-011, STORY-016).

Provides GET /v1/capacity/month/{month}?device_id={id} to retrieve
15-minute average power peaks (kwartierpiek) and the monthly peak
for capacity tariff calculations. Requires Bearer token authentication;
callers can only access their own device data.

CHANGELOG:
- 2026-02-14: Add Bearer auth and device_id mismatch validation (STORY-016)
- 2026-02-13: Initial creation (STORY-011)

TODO:
- None
"""

from fastapi import APIRouter, HTTPException, Query

from src.api.deps import CurrentDeviceId, DbSession
from src.services.capacity import get_monthly_peaks, parse_month_range

router = APIRouter(prefix="/v1", tags=["capacity"])


@router.get("/capacity/month/{month}")
async def get_capacity(
    month: str,
    db: DbSession,
    auth_device_id: CurrentDeviceId,
    device_id: str = Query(..., description="Device identifier"),
) -> dict:
    """Get 15-minute average power peaks for a given month.

    Requires Bearer token authentication. The query parameter device_id
    must match the authenticated device_id from the token. Computes
    kwartierpiek (quarter-hour peak) data using TimescaleDB time_bucket
    aggregation on import_power_w.

    Args:
        month: Month in YYYY-MM format (path parameter).
        db: Async database session (injected).
        auth_device_id: Authenticated device_id from Bearer token.
        device_id: Device identifier (query parameter, required).

    Returns:
        dict: Capacity data with peaks list and monthly peak info.

    Raises:
        HTTPException: 401 if missing/invalid Bearer token.
        HTTPException: 403 if device_id does not match authenticated device.
        HTTPException: 400 if month format is invalid.
    """
    # STORY-016 AC4: Verify query device_id matches authenticated device
    if device_id != auth_device_id:
        raise HTTPException(
            status_code=403,
            detail="Device ID mismatch",
        )
    # AC6: Validate month format
    try:
        parse_month_range(month)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid month format: {month!r}. Expected YYYY-MM.",
        )

    return await get_monthly_peaks(db, device_id, month)
