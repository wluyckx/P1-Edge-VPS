"""
Fix continuous aggregates: MAX-MIN instead of SUM for energy kWh.

The energy_import_kwh and energy_export_kwh fields in p1_samples are
cumulative meter readings. SUM() of cumulative readings is meaningless.
The correct aggregation is MAX() - MIN() to get the delta per bucket.

Also adds sample_count to all views (was missing from 002, added ad-hoc in 003).

Revision ID: 004
Revises: 003
Create Date: 2026-03-20

CHANGELOG:
- 2026-03-20: Fix SUM→MAX-MIN for energy fields (BPPA-125)
"""

from typing import Sequence, Union

from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Recreate all continuous aggregates with correct energy delta calculation.

    Steps:
        1. Drop existing aggregates (policies auto-removed).
        2. Recreate with MAX()-MIN() for energy fields.
        3. Re-add refresh policies.
        4. Refresh all historical data.
    """
    # ── Drop existing views ──────────────────────────────────────────
    op.execute("DROP MATERIALIZED VIEW IF EXISTS p1_monthly CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS p1_daily CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS p1_hourly CASCADE")

    # ── Recreate p1_hourly (1-hour buckets) ──────────────────────────
    op.execute(
        "CREATE MATERIALIZED VIEW p1_hourly "
        "WITH (timescaledb.continuous) AS "
        "SELECT "
        "  time_bucket('1 hour', ts) AS bucket, "
        "  device_id, "
        "  AVG(power_w)::integer AS avg_power_w, "
        "  MAX(power_w) AS max_power_w, "
        "  MAX(energy_import_kwh) - MIN(energy_import_kwh) AS energy_import_kwh, "
        "  MAX(energy_export_kwh) - MIN(energy_export_kwh) AS energy_export_kwh, "
        "  COUNT(*) AS sample_count "
        "FROM p1_samples "
        "GROUP BY bucket, device_id "
        "WITH NO DATA"
    )

    # ── Recreate p1_daily (1-day buckets) ────────────────────────────
    op.execute(
        "CREATE MATERIALIZED VIEW p1_daily "
        "WITH (timescaledb.continuous) AS "
        "SELECT "
        "  time_bucket('1 day', ts) AS bucket, "
        "  device_id, "
        "  AVG(power_w)::integer AS avg_power_w, "
        "  MAX(power_w) AS max_power_w, "
        "  MAX(energy_import_kwh) - MIN(energy_import_kwh) AS energy_import_kwh, "
        "  MAX(energy_export_kwh) - MIN(energy_export_kwh) AS energy_export_kwh, "
        "  COUNT(*) AS sample_count "
        "FROM p1_samples "
        "GROUP BY bucket, device_id "
        "WITH NO DATA"
    )

    # ── Recreate p1_monthly (1-month buckets) ────────────────────────
    op.execute(
        "CREATE MATERIALIZED VIEW p1_monthly "
        "WITH (timescaledb.continuous) AS "
        "SELECT "
        "  time_bucket('1 month', ts) AS bucket, "
        "  device_id, "
        "  AVG(power_w)::integer AS avg_power_w, "
        "  MAX(power_w) AS max_power_w, "
        "  MAX(energy_import_kwh) - MIN(energy_import_kwh) AS energy_import_kwh, "
        "  MAX(energy_export_kwh) - MIN(energy_export_kwh) AS energy_export_kwh, "
        "  COUNT(*) AS sample_count "
        "FROM p1_samples "
        "GROUP BY bucket, device_id "
        "WITH NO DATA"
    )

    # ── Re-add refresh policies ──────────────────────────────────────
    op.execute(
        "SELECT add_continuous_aggregate_policy('p1_hourly', "
        "  start_offset => INTERVAL '3 hours', "
        "  end_offset => INTERVAL '1 hour', "
        "  schedule_interval => INTERVAL '1 hour', "
        "  if_not_exists => TRUE)"
    )
    op.execute(
        "SELECT add_continuous_aggregate_policy('p1_daily', "
        "  start_offset => INTERVAL '3 days', "
        "  end_offset => INTERVAL '1 day', "
        "  schedule_interval => INTERVAL '1 day', "
        "  if_not_exists => TRUE)"
    )
    op.execute(
        "SELECT add_continuous_aggregate_policy('p1_monthly', "
        "  start_offset => INTERVAL '3 months', "
        "  end_offset => INTERVAL '1 day', "
        "  schedule_interval => INTERVAL '1 day', "
        "  if_not_exists => TRUE)"
    )

    # ── Backfill all historical data ─────────────────────────────────
    op.execute(
        "CALL refresh_continuous_aggregate('p1_hourly', '2020-01-01', '2030-01-01')"
    )
    op.execute(
        "CALL refresh_continuous_aggregate('p1_daily', '2020-01-01', '2030-01-01')"
    )
    op.execute(
        "CALL refresh_continuous_aggregate('p1_monthly', '2020-01-01', '2030-01-01')"
    )


def downgrade() -> None:
    """Revert to SUM-based aggregates (migration 002+003 behavior)."""
    op.execute("DROP MATERIALIZED VIEW IF EXISTS p1_monthly CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS p1_daily CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS p1_hourly CASCADE")

    # Recreate with old SUM logic
    for view, interval in [("p1_hourly", "1 hour"), ("p1_daily", "1 day"), ("p1_monthly", "1 month")]:
        op.execute(
            f"CREATE MATERIALIZED VIEW {view} "
            "WITH (timescaledb.continuous) AS "
            "SELECT "
            f"  time_bucket('{interval}', ts) AS bucket, "
            "  device_id, "
            "  AVG(power_w)::integer AS avg_power_w, "
            "  MAX(power_w) AS max_power_w, "
            "  SUM(energy_import_kwh) AS energy_import_kwh, "
            "  SUM(energy_export_kwh) AS energy_export_kwh, "
            "  COUNT(*) AS sample_count "
            "FROM p1_samples "
            "GROUP BY bucket, device_id "
            "WITH NO DATA"
        )
