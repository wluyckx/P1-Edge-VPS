"""
Aggregation service for historical time series data.

Provides time-bucketed aggregation of P1 energy telemetry samples
using TimescaleDB continuous aggregate views. Supports day, month,
year, and all-time frames. Queries pre-computed materialized views
(p1_hourly, p1_daily, p1_monthly) for improved performance.

CHANGELOG:
- 2026-02-13: Fix average-of-averages: use weighted avg in rebucket (quality fix #1)
- 2026-02-13: Query continuous aggregates instead of raw p1_samples (STORY-013)
- 2026-02-13: Initial creation (STORY-012)

TODO:
- None
"""

import calendar
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Frame configuration: maps frame name to source view, optional re-bucket
# interval, and date range type.
# - "view": the continuous aggregate view to query
# - "rebucket": if set, apply time_bucket() on top of the view's bucket column
# - "range": date range filter (None means all data)
FRAME_CONFIG = {
    "day": {
        "view": "p1_hourly",
        "rebucket": None,
        "range": "today",
    },
    "month": {
        "view": "p1_daily",
        "rebucket": "1 week",
        "range": "current_month",
    },
    "year": {
        "view": "p1_monthly",
        "rebucket": None,
        "range": "current_year",
    },
    "all": {
        "view": "p1_monthly",
        "rebucket": None,
        "range": None,
    },
}


def _get_date_range(
    range_type: str | None,
) -> tuple[datetime | None, datetime | None]:
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
        start = now.replace(
            month=1,
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        end = start.replace(year=now.year + 1)
        return start, end

    return None, None


async def get_aggregated_series(
    session: AsyncSession,
    device_id: str,
    frame: str,
) -> list[dict]:
    """Query aggregated series for a device and time frame.

    Reads from pre-computed TimescaleDB continuous aggregate views
    instead of raw p1_samples for improved query performance.

    Frame-to-view mapping:
      - day   -> p1_hourly (already 1h buckets, no re-aggregation)
      - month -> p1_daily  (re-bucketed to 1 week via time_bucket)
      - year  -> p1_monthly (already 1-month buckets)
      - all   -> p1_monthly (already 1-month buckets)

    Args:
        session: Async SQLAlchemy session for database operations.
        device_id: Identifier of the P1 meter device.
        frame: Time frame key (day, month, year, all).

    Returns:
        List of dicts, each containing bucket, avg_power_w, max_power_w,
        energy_import_kwh, and energy_export_kwh.
    """
    config = FRAME_CONFIG[frame]
    view = config["view"]
    rebucket = config["rebucket"]
    start, end = _get_date_range(config["range"])

    params: dict = {"device_id": device_id}

    if rebucket is not None:
        # Re-aggregate the pre-computed view into larger buckets.
        # Use weighted average (by sample_count) to avoid the
        # average-of-averages error where low-sample buckets get
        # disproportionate weight.
        bucket_expr = "time_bucket(:interval, bucket)"
        params["interval"] = rebucket
        base_sql = (
            f"SELECT {bucket_expr} AS bucket, "
            "(SUM(avg_power_w::bigint * sample_count) "
            "/ NULLIF(SUM(sample_count), 0))::integer AS avg_power_w, "
            "MAX(max_power_w) AS max_power_w, "
            "SUM(energy_import_kwh) AS energy_import_kwh, "
            "SUM(energy_export_kwh) AS energy_export_kwh "
            f"FROM {view} "
            "WHERE device_id = :device_id"
        )
    else:
        # Query the view directly; buckets are already at the right size.
        base_sql = (
            "SELECT bucket, "
            "avg_power_w, "
            "max_power_w, "
            "energy_import_kwh, "
            "energy_export_kwh "
            f"FROM {view} "
            "WHERE device_id = :device_id"
        )

    if start is not None and end is not None:
        base_sql += " AND bucket >= :start AND bucket < :end"
        params["start"] = start
        params["end"] = end

    if rebucket is not None:
        base_sql += " GROUP BY bucket ORDER BY bucket"
    else:
        base_sql += " ORDER BY bucket"

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
