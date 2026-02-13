"""
Initial schema: create p1_samples table with TimescaleDB hypertable.

Enables the TimescaleDB extension, creates the p1_samples table with
all required columns and composite primary key, then converts it to
a TimescaleDB hypertable partitioned on the ts column.

Revision ID: 001
Revises: None
Create Date: 2026-02-13

CHANGELOG:
- 2026-02-13: Initial creation (STORY-007)

TODO:
- None
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# Revision identifiers used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create TimescaleDB extension and p1_samples hypertable.

    Steps:
        1. Enable timescaledb extension (idempotent).
        2. Create p1_samples table with composite PK (device_id, ts).
        3. Convert p1_samples to a TimescaleDB hypertable on ts column.
    """
    # AC3: Enable TimescaleDB extension.
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")

    # AC4: Create the p1_samples table.
    op.create_table(
        "p1_samples",
        sa.Column("device_id", sa.Text(), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("power_w", sa.Integer(), nullable=False),
        sa.Column("import_power_w", sa.Integer(), nullable=False),
        sa.Column("energy_import_kwh", sa.Double(), nullable=True),
        sa.Column("energy_export_kwh", sa.Double(), nullable=True),
        sa.PrimaryKeyConstraint("device_id", "ts"),
    )

    # AC5: Convert to TimescaleDB hypertable.
    op.execute("SELECT create_hypertable('p1_samples', 'ts', if_not_exists => TRUE)")


def downgrade() -> None:
    """Drop p1_samples table.

    Note: Does not drop the timescaledb extension as other tables may use it.
    """
    op.drop_table("p1_samples")
