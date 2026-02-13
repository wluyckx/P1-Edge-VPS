"""
Tests for the P1Sample SQLAlchemy model.

Validates column names, column types, and composite primary key
per STORY-007 acceptance criteria.

CHANGELOG:
- 2026-02-13: Initial creation (STORY-007)

TODO:
- None
"""

import datetime

from sqlalchemy import DateTime, Double, Integer, Text, inspect
from src.db.models import Base, P1Sample


class TestP1SampleColumns:
    """Tests that P1Sample model defines all required columns."""

    def test_has_device_id_column(self) -> None:
        """P1Sample has a device_id column."""
        mapper = inspect(P1Sample)
        column_names = [col.key for col in mapper.column_attrs]
        assert "device_id" in column_names

    def test_has_ts_column(self) -> None:
        """P1Sample has a ts column."""
        mapper = inspect(P1Sample)
        column_names = [col.key for col in mapper.column_attrs]
        assert "ts" in column_names

    def test_has_power_w_column(self) -> None:
        """P1Sample has a power_w column."""
        mapper = inspect(P1Sample)
        column_names = [col.key for col in mapper.column_attrs]
        assert "power_w" in column_names

    def test_has_import_power_w_column(self) -> None:
        """P1Sample has an import_power_w column."""
        mapper = inspect(P1Sample)
        column_names = [col.key for col in mapper.column_attrs]
        assert "import_power_w" in column_names

    def test_has_energy_import_kwh_column(self) -> None:
        """P1Sample has an energy_import_kwh column."""
        mapper = inspect(P1Sample)
        column_names = [col.key for col in mapper.column_attrs]
        assert "energy_import_kwh" in column_names

    def test_has_energy_export_kwh_column(self) -> None:
        """P1Sample has an energy_export_kwh column."""
        mapper = inspect(P1Sample)
        column_names = [col.key for col in mapper.column_attrs]
        assert "energy_export_kwh" in column_names

    def test_total_column_count(self) -> None:
        """P1Sample has exactly 6 columns."""
        mapper = inspect(P1Sample)
        column_names = [col.key for col in mapper.column_attrs]
        assert len(column_names) == 6


class TestP1SampleColumnTypes:
    """Tests that P1Sample columns have correct SQLAlchemy types."""

    def test_device_id_is_text(self) -> None:
        """device_id column is Text type."""
        col = P1Sample.__table__.columns["device_id"]
        assert isinstance(col.type, Text)

    def test_ts_is_timestamptz(self) -> None:
        """ts column is DateTime with timezone=True (TIMESTAMPTZ)."""
        col = P1Sample.__table__.columns["ts"]
        assert isinstance(col.type, DateTime)
        assert col.type.timezone is True

    def test_power_w_is_integer(self) -> None:
        """power_w column is Integer type."""
        col = P1Sample.__table__.columns["power_w"]
        assert isinstance(col.type, Integer)

    def test_import_power_w_is_integer(self) -> None:
        """import_power_w column is Integer type."""
        col = P1Sample.__table__.columns["import_power_w"]
        assert isinstance(col.type, Integer)

    def test_energy_import_kwh_is_double(self) -> None:
        """energy_import_kwh column is Double Precision type."""
        col = P1Sample.__table__.columns["energy_import_kwh"]
        assert isinstance(col.type, Double)

    def test_energy_export_kwh_is_double(self) -> None:
        """energy_export_kwh column is Double Precision type."""
        col = P1Sample.__table__.columns["energy_export_kwh"]
        assert isinstance(col.type, Double)


class TestP1SampleNullability:
    """Tests that P1Sample columns have correct nullable settings."""

    def test_device_id_not_nullable(self) -> None:
        """device_id column is NOT NULL."""
        col = P1Sample.__table__.columns["device_id"]
        assert col.nullable is False

    def test_ts_not_nullable(self) -> None:
        """ts column is NOT NULL."""
        col = P1Sample.__table__.columns["ts"]
        assert col.nullable is False

    def test_power_w_not_nullable(self) -> None:
        """power_w column is NOT NULL."""
        col = P1Sample.__table__.columns["power_w"]
        assert col.nullable is False

    def test_import_power_w_not_nullable(self) -> None:
        """import_power_w column is NOT NULL."""
        col = P1Sample.__table__.columns["import_power_w"]
        assert col.nullable is False

    def test_energy_import_kwh_nullable(self) -> None:
        """energy_import_kwh column is nullable (optional field)."""
        col = P1Sample.__table__.columns["energy_import_kwh"]
        assert col.nullable is True

    def test_energy_export_kwh_nullable(self) -> None:
        """energy_export_kwh column is nullable (optional field)."""
        col = P1Sample.__table__.columns["energy_export_kwh"]
        assert col.nullable is True


class TestP1SamplePrimaryKey:
    """Tests that P1Sample has the correct composite primary key."""

    def test_composite_primary_key_columns(self) -> None:
        """Primary key consists of (device_id, ts)."""
        pk_columns = [col.name for col in P1Sample.__table__.primary_key.columns]
        assert pk_columns == ["device_id", "ts"]

    def test_device_id_is_primary_key(self) -> None:
        """device_id is part of the primary key."""
        col = P1Sample.__table__.columns["device_id"]
        assert col.primary_key is True

    def test_ts_is_primary_key(self) -> None:
        """ts is part of the primary key."""
        col = P1Sample.__table__.columns["ts"]
        assert col.primary_key is True

    def test_power_w_is_not_primary_key(self) -> None:
        """power_w is NOT part of the primary key."""
        col = P1Sample.__table__.columns["power_w"]
        assert col.primary_key is False


class TestP1SampleTableName:
    """Tests that the table name is correct."""

    def test_table_name(self) -> None:
        """Table name is 'p1_samples'."""
        assert P1Sample.__tablename__ == "p1_samples"


class TestP1SampleRepr:
    """Tests the string representation of P1Sample."""

    def test_repr(self) -> None:
        """P1Sample repr includes device_id and ts."""
        sample = P1Sample(
            device_id="hw-p1-001",
            ts=datetime.datetime(2026, 2, 13, 14, 30, 0, tzinfo=datetime.timezone.utc),
            power_w=450,
            import_power_w=450,
        )
        result = repr(sample)
        assert "hw-p1-001" in result
        assert "P1Sample" in result


class TestBaseModel:
    """Tests that Base declarative base is properly defined."""

    def test_base_has_metadata(self) -> None:
        """Base has a metadata attribute for table definitions."""
        assert hasattr(Base, "metadata")

    def test_p1sample_in_base_metadata(self) -> None:
        """P1Sample table is registered in Base metadata."""
        table_names = list(Base.metadata.tables.keys())
        assert "p1_samples" in table_names
