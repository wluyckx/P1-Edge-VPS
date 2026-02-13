"""
SQLAlchemy ORM models for the VPS database.

Defines the P1Sample model for storing energy telemetry data
in a TimescaleDB hypertable.

CHANGELOG:
- 2026-02-13: Initial creation (STORY-007)

TODO:
- None
"""

import datetime

from sqlalchemy import DateTime, Double, Integer, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all VPS ORM models."""

    pass


class P1Sample(Base):
    """Energy telemetry sample from a HomeWizard P1 meter.

    Stored in the p1_samples TimescaleDB hypertable with a composite
    primary key on (device_id, ts) for idempotent upserts.

    Attributes:
        device_id: Identifier of the P1 meter device.
        ts: Measurement timestamp in UTC.
        power_w: Current power in watts (negative = export).
        import_power_w: Import power in watts, always >= 0.
        energy_import_kwh: Cumulative energy imported from grid (kWh).
        energy_export_kwh: Cumulative energy exported to grid (kWh).
    """

    __tablename__ = "p1_samples"

    device_id: Mapped[str] = mapped_column(
        Text, primary_key=True, nullable=False,
    )
    ts: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, nullable=False,
    )
    power_w: Mapped[int] = mapped_column(Integer, nullable=False)
    import_power_w: Mapped[int] = mapped_column(Integer, nullable=False)
    energy_import_kwh: Mapped[float | None] = mapped_column(Double, nullable=True)
    energy_export_kwh: Mapped[float | None] = mapped_column(Double, nullable=True)

    def __repr__(self) -> str:
        """Return string representation of the P1Sample."""
        return (
            f"P1Sample(device_id={self.device_id!r}, ts={self.ts!r}, "
            f"power_w={self.power_w!r})"
        )
