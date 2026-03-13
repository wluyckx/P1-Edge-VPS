"""
Daily energy endpoint — today's import/export kWh delta.

Computes energy consumed/exported today by taking MAX - MIN of cumulative
P1 meter counters from today's samples. Uses PostgreSQL timezone conversion
for correct Europe/Brussels midnight boundary (handles DST).

CHANGELOG:
- 2026-03-13: Initial creation (fix 0.0 kWh on Hestia home tile)

TODO:
- None
"""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from src.api.deps import CurrentDeviceId, DbSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["daily-energy"])


class DailyEnergyResponse(BaseModel):
    """Schema for today's energy delta response.

    Attributes:
        device_id: Identifier of the P1 meter device.
        date: Today's date (YYYY-MM-DD) in UTC.
        import_today_kwh: Energy imported from grid today (kWh).
        export_today_kwh: Energy exported to grid today (kWh).
        sample_count: Number of samples used for the computation.
    """

    device_id: str
    date: str
    import_today_kwh: float
    export_today_kwh: float
    sample_count: int


_DAILY_ENERGY_QUERY = text("""
    SELECT
        COUNT(*) AS sample_count,
        COALESCE(MAX(energy_import_kwh) - MIN(energy_import_kwh), 0)
            AS import_today_kwh,
        COALESCE(MAX(energy_export_kwh) - MIN(energy_export_kwh), 0)
            AS export_today_kwh
    FROM p1_samples
    WHERE device_id = :device_id
      AND ts >= date_trunc('day', now() AT TIME ZONE 'Europe/Brussels')
               AT TIME ZONE 'Europe/Brussels'
""")


@router.get("/daily-energy", response_model=DailyEnergyResponse)
async def get_daily_energy(
    device_id: str,
    db: DbSession,
    auth_device_id: CurrentDeviceId,
) -> DailyEnergyResponse:
    """Get today's energy import/export in kWh.

    Computes the delta between the maximum and minimum cumulative counter
    values from today's p1_samples. This gives the actual energy
    consumed/exported since midnight (Europe/Brussels timezone).

    Args:
        device_id: Identifier of the P1 meter device.
        db: Async database session.
        auth_device_id: Authenticated device_id from Bearer token.

    Returns:
        DailyEnergyResponse: Today's energy import/export deltas.

    Raises:
        HTTPException: 403 if device_id does not match authenticated device.
        HTTPException: 404 if no samples exist for today.
    """
    if device_id != auth_device_id:
        raise HTTPException(status_code=403, detail="Device ID mismatch")

    result = await db.execute(_DAILY_ENERGY_QUERY, {"device_id": device_id})
    row = result.fetchone()

    if row is None or row._mapping["sample_count"] == 0:
        raise HTTPException(status_code=404, detail="No samples found for today")

    today_str = datetime.now(UTC).strftime("%Y-%m-%d")

    return DailyEnergyResponse(
        device_id=device_id,
        date=today_str,
        import_today_kwh=round(row._mapping["import_today_kwh"], 3),
        export_today_kwh=round(row._mapping["export_today_kwh"], 3),
        sample_count=row._mapping["sample_count"],
    )
