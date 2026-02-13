"""
Aggregation service for historical time series data.

Provides time-bucketed aggregation of P1 energy telemetry samples
using TimescaleDB's time_bucket function. Supports day, month, year,
and all-time frames with configurable bucket intervals.

CHANGELOG:
- 2026-02-13: Initial creation (STORY-012)

TODO:
- None
"""

import calendar
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Frame configuration: maps frame name to bucket interval and date range type.
# "range" of None means no date filtering (all data).
FRAME_CONFIG = {
    "day": {"interval": "1 hour", "range": "today"},
    "month": {"interval": "1 week", "range": "current_month"},
    "year": {"interval": "1 month", "range": "current_year"},
    "all": {"interval": "1 month", "range": None},
}


def _get_date_range(range_type: str | None) -> tuple[datetime | None, datetime | None]:
    """Compute the start (inclusive) and end (exclusive) timestamps for a range.

    Args:
        range_type: One of 'today', 'current_month', 'current_year', or None.

    Returns:
        Tuple of (start, end) datetimes in UTC, or (None, None) for no filter.
    """
    if range_type is None:
        return None, None

    now = datetime.now(UTC)

    if range_type == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        return start, end

    if range_type == "current_month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        _, last_day = calendar.monthrange(now.year, now.month)
        end = start.replace(day=last_day) + timedelta(days=1)
        return start, end

    if range_type == "current_year":
        start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        end = start.replace(year=now.year + 1)
        return start, end

    return None, None


async def get_aggregated_series(
    session: AsyncSession, device_id: str, frame: str,
) -> list[dict]:
    """Query aggregated series for a device and time frame.

    Uses TimescaleDB's time_bucket function to group samples into
    time-based buckets and compute aggregate statistics.

    SQL:
        SELECT time_bucket(:interval, ts) AS bucket,
               AVG(power_w)::integer AS avg_power_w,
               MAX(power_w) AS max_power_w,
               SUM(energy_import_kwh) AS energy_import_kwh,
               SUM(energy_export_kwh) AS energy_export_kwh
        FROM p1_samples
        WHERE device_id = :device_id [AND ts >= :start AND ts < :end]
        GROUP BY bucket ORDER BY bucket

    Args:
        session: Async SQLAlchemy session for database operations.
        device_id: Identifier of the P1 meter device.
        frame: Time frame key (day, month, year, all).

    Returns:
        List of dicts, each containing bucket, avg_power_w, max_power_w,
        energy_import_kwh, and energy_export_kwh.
    """
    config = FRAME_CONFIG[frame]
    interval = config["interval"]
    start, end = _get_date_range(config["range"])

    # Build SQL query
    base_sql = (
        "SELECT time_bucket(:interval, ts) AS bucket, "
        "AVG(power_w)::integer AS avg_power_w, "
        "MAX(power_w) AS max_power_w, "
        "SUM(energy_import_kwh) AS energy_import_kwh, "
        "SUM(energy_export_kwh) AS energy_export_kwh "
        "FROM p1_samples "
        "WHERE device_id = :device_id"
    )

    params: dict = {"interval": interval, "device_id": device_id}

    if start is not None and end is not None:
        base_sql += " AND ts >= :start AND ts < :end"
        params["start"] = start
        params["end"] = end

    base_sql += " GROUP BY bucket ORDER BY bucket"

    result = await session.execute(text(base_sql), params)
    rows = result.fetchall()

    return [
        {
            "bucket": str(row._mapping["bucket"]),
            "avg_power_w": row._mapping["avg_power_w"],
            "max_power_w": row._mapping["max_power_w"],
            "energy_import_kwh": row._mapping["energy_import_kwh"],
            "energy_export_kwh": row._mapping["energy_export_kwh"],
        }
        for row in rows
    ]
