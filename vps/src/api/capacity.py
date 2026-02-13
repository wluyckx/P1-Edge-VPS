"""
Capacity tariff API endpoint for 15-minute peak data (STORY-011).

Provides GET /v1/capacity/month/{month}?device_id={id} to retrieve
15-minute average power peaks (kwartierpiek) and the monthly peak
for capacity tariff calculations.

CHANGELOG:
- 2026-02-13: Initial creation (STORY-011)

TODO:
- None
"""

from fastapi import APIRouter, HTTPException, Query

from src.api.deps import DbSession
from src.services.capacity import get_monthly_peaks, parse_month_range

router = APIRouter(prefix="/v1", tags=["capacity"])


@router.get("/capacity/month/{month}")
async def get_capacity(
    month: str,
    db: DbSession,
    device_id: str = Query(..., description="Device identifier"),
) -> dict:
    """Get 15-minute average power peaks for a given month.

    Computes kwartierpiek (quarter-hour peak) data using TimescaleDB
    time_bucket aggregation on import_power_w. No authentication
    required (public read endpoint).

    Args:
        month: Month in YYYY-MM format (path parameter).
        db: Async database session (injected).
        device_id: Device identifier (query parameter, required).

    Returns:
        dict: Capacity data with peaks list and monthly peak info.

    Raises:
        HTTPException: 400 if month format is invalid.
    """
    # AC6: Validate month format
    try:
        parse_month_range(month)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid month format: {month!r}. Expected YYYY-MM.",
        )

    return await get_monthly_peaks(db, device_id, month)
