"""
Capacity tariff calculation service (kwartierpiek / STORY-011).

Queries 15-minute average power peaks from TimescaleDB using
time_bucket('15 minutes', ts) and computes the monthly peak.

CHANGELOG:
- 2026-02-13: Initial creation (STORY-011)

TODO:
- None
"""

import re
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Strict YYYY-MM pattern: 4-digit year, dash, 2-digit month (01-12)
_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def parse_month_range(month: str) -> tuple[datetime, datetime]:
    """Parse a YYYY-MM string into UTC start/end datetime boundaries.

    Args:
        month: Month string in YYYY-MM format (e.g. "2026-02").

    Returns:
        Tuple of (start, end) where start is the first day of the month
        at 00:00:00 UTC and end is the first day of the next month at
        00:00:00 UTC.

    Raises:
        ValueError: If the month string does not match YYYY-MM format
            or represents an invalid month.
    """
    if not _MONTH_RE.match(month):
        raise ValueError(f"Invalid month format: {month!r}. Expected YYYY-MM.")

    year, month_num = month.split("-")
    year = int(year)
    month_num = int(month_num)

    start = datetime(year, month_num, 1, tzinfo=timezone.utc)

    # Roll over to next month; handle December -> January of next year
    if month_num == 12:
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(year, month_num + 1, 1, tzinfo=timezone.utc)

    return start, end


async def get_monthly_peaks(
    session: AsyncSession,
    device_id: str,
    month: str,
) -> dict:
    """Query 15-minute average power peaks for a month.

    Uses TimescaleDB's time_bucket function to aggregate import_power_w
    into 15-minute windows, computing the average power for each window.

    Args:
        session: Async SQLAlchemy session.
        device_id: Device identifier to query data for.
        month: Month in YYYY-MM format.

    Returns:
        dict with keys:
            - month: The requested month string.
            - device_id: The requested device ID.
            - peaks: List of dicts with 'bucket' (ISO str) and 'avg_power_w' (int).
            - monthly_peak_w: Maximum avg_power_w across all buckets, or None.
            - monthly_peak_ts: ISO timestamp of the peak bucket, or None.
    """
    start, end = parse_month_range(month)

    query = text(
        "SELECT time_bucket('15 minutes', ts) AS bucket, "
        "       AVG(import_power_w)::integer AS avg_power_w "
        "FROM p1_samples "
        "WHERE device_id = :device_id AND ts >= :start AND ts < :end "
        "GROUP BY bucket ORDER BY bucket"
    )

    result = await session.execute(
        query,
        {"device_id": device_id, "start": start, "end": end},
    )
    rows = result.all()

    if not rows:
        return {
            "month": month,
            "device_id": device_id,
            "peaks": [],
            "monthly_peak_w": None,
            "monthly_peak_ts": None,
        }

    peaks = [
        {
            "bucket": row.bucket.isoformat(),
            "avg_power_w": row.avg_power_w,
        }
        for row in rows
    ]

    # Find the row with the maximum avg_power_w
    peak_row = max(rows, key=lambda r: r.avg_power_w)

    return {
        "month": month,
        "device_id": device_id,
        "peaks": peaks,
        "monthly_peak_w": peak_row.avg_power_w,
        "monthly_peak_ts": peak_row.bucket.isoformat(),
    }
