"""
Add sample_count to continuous aggregate views for weighted averages.

Drops and recreates p1_hourly, p1_daily, p1_monthly with an additional
COUNT(*) AS sample_count column.  This allows re-bucketing queries to
compute correct weighted averages instead of naive AVG(avg_power_w),
which weights each bucket equally regardless of sample density
(average-of-averages bug).

Revision ID: 003
Revises: 002
Create Date: 2026-02-13

CHANGELOG:
- 2026-02-13: Initial creation (quality review fix #1)

TODO:
- None
"""

from typing import Sequence, Union

from alembic import op

# Revision identifiers used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Recreate continuous aggregate views with sample_count column.

    Steps:
        1. Drop existing views (CASCADE removes refresh policies).
        2. Recreate each view with COUNT(*) AS sample_count.
        3. Re-add auto-refresh policies.
    """
    # Drop in reverse dependency order (monthly, daily, hourly).
    op.execute("DROP MATERIALIZED VIEW IF EXISTS p1_monthly CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS p1_daily CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS p1_hourly CASCADE")

    # Recreate p1_hourly with sample_count.
    op.execute(
        "CREATE MATERIALIZED VIEW p1_hourly "
        "WITH (timescaledb.continuous) AS "
        "SELECT "
        "  time_bucket('1 hour', ts) AS bucket, "
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

    # Recreate p1_daily with sample_count.
    op.execute(
        "CREATE MATERIALIZED VIEW p1_daily "
        "WITH (timescaledb.continuous) AS "
        "SELECT "
        "  time_bucket('1 day', ts) AS bucket, "
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

    # Recreate p1_monthly with sample_count.
    op.execute(
        "CREATE MATERIALIZED VIEW p1_monthly "
        "WITH (timescaledb.continuous) AS "
        "SELECT "
        "  time_bucket('1 month', ts) AS bucket, "
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

    # Re-add refresh policies (same as migration 002).
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


def downgrade() -> None:
    """Revert to views without sample_count (migration 002 state).

    Drops and recreates the views without the sample_count column.
    Policies are automatically removed when the view is dropped.
    """
    op.execute("DROP MATERIALIZED VIEW IF EXISTS p1_monthly CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS p1_daily CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS p1_hourly CASCADE")

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
