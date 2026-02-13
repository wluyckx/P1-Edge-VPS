"""
Create TimescaleDB continuous aggregate views for p1_samples.

Creates three materialized views with continuous aggregate policies:
- p1_hourly: 1-hour buckets with auto-refresh
- p1_daily: 1-day buckets with auto-refresh
- p1_monthly: 1-month buckets with auto-refresh

Each view contains: bucket, device_id, avg_power_w, max_power_w,
energy_import_kwh, energy_export_kwh.

Revision ID: 002
Revises: 001
Create Date: 2026-02-13

CHANGELOG:
- 2026-02-13: Initial creation (STORY-013)

TODO:
- None
"""

from typing import Sequence, Union

from alembic import op

# Revision identifiers used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create continuous aggregate views and refresh policies.

    Steps:
        1. Create p1_hourly continuous aggregate (1-hour buckets).
        2. Create p1_daily continuous aggregate (1-day buckets).
        3. Create p1_monthly continuous aggregate (1-month buckets).
        4. Add auto-refresh policies for each view.
    """
    # AC1: Create p1_hourly continuous aggregate view.
    op.execute(
        "CREATE MATERIALIZED VIEW p1_hourly "
        "WITH (timescaledb.continuous) AS "
        "SELECT "
        "  time_bucket('1 hour', ts) AS bucket, "
        "  device_id, "
        "  AVG(power_w)::integer AS avg_power_w, "
        "  MAX(power_w) AS max_power_w, "
        "  SUM(energy_import_kwh) AS energy_import_kwh, "
        "  SUM(energy_export_kwh) AS energy_export_kwh "
        "FROM p1_samples "
        "GROUP BY bucket, device_id "
        "WITH NO DATA"
    )

    # AC2: Create p1_daily continuous aggregate view.
    op.execute(
        "CREATE MATERIALIZED VIEW p1_daily "
        "WITH (timescaledb.continuous) AS "
        "SELECT "
        "  time_bucket('1 day', ts) AS bucket, "
        "  device_id, "
        "  AVG(power_w)::integer AS avg_power_w, "
        "  MAX(power_w) AS max_power_w, "
        "  SUM(energy_import_kwh) AS energy_import_kwh, "
        "  SUM(energy_export_kwh) AS energy_export_kwh "
        "FROM p1_samples "
        "GROUP BY bucket, device_id "
        "WITH NO DATA"
    )

    # AC3: Create p1_monthly continuous aggregate view.
    op.execute(
        "CREATE MATERIALIZED VIEW p1_monthly "
        "WITH (timescaledb.continuous) AS "
        "SELECT "
        "  time_bucket('1 month', ts) AS bucket, "
        "  device_id, "
        "  AVG(power_w)::integer AS avg_power_w, "
        "  MAX(power_w) AS max_power_w, "
        "  SUM(energy_import_kwh) AS energy_import_kwh, "
        "  SUM(energy_export_kwh) AS energy_export_kwh "
        "FROM p1_samples "
        "GROUP BY bucket, device_id "
        "WITH NO DATA"
    )

    # AC4: Add continuous aggregate refresh policies.
    # p1_hourly: refresh data from 3 hours ago to 1 hour ago, every 1 hour.
    op.execute(
        "SELECT add_continuous_aggregate_policy('p1_hourly', "
        "  start_offset => INTERVAL '3 hours', "
        "  end_offset => INTERVAL '1 hour', "
        "  schedule_interval => INTERVAL '1 hour', "
        "  if_not_exists => TRUE)"
    )

    # p1_daily: refresh data from 3 days ago to 1 day ago, every 1 day.
    op.execute(
        "SELECT add_continuous_aggregate_policy('p1_daily', "
        "  start_offset => INTERVAL '3 days', "
        "  end_offset => INTERVAL '1 day', "
        "  schedule_interval => INTERVAL '1 day', "
        "  if_not_exists => TRUE)"
    )

    # p1_monthly: refresh data from 3 months ago to 1 day ago, every 1 day.
    op.execute(
        "SELECT add_continuous_aggregate_policy('p1_monthly', "
        "  start_offset => INTERVAL '3 months', "
        "  end_offset => INTERVAL '1 day', "
        "  schedule_interval => INTERVAL '1 day', "
        "  if_not_exists => TRUE)"
    )


def downgrade() -> None:
    """Drop continuous aggregate views in reverse order.

    Policies are automatically removed when the view is dropped.
    """
    op.execute("DROP MATERIALIZED VIEW IF EXISTS p1_monthly CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS p1_daily CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS p1_hourly CASCADE")
