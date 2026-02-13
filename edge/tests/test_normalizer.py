"""
Unit tests for edge measurement normalizer.

Tests verify:
- Valid input produces correct normalized output with all expected keys.
- import_power_w is computed as max(power_w, 0) for negative, zero, and positive values.
- Missing required fields in raw input raise ValueError.
- The provided timestamp is used (no internal datetime.now() calls).
- Optional energy fields default to None when absent from raw input.

CHANGELOG:
- 2026-02-13: Initial creation (STORY-003)

TODO:
- None
"""

from datetime import UTC, datetime

import pytest
from edge.src.normalizer import normalize

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def valid_raw() -> dict:
    """A valid raw HomeWizard measurement dict with all fields present."""
    return {
        "power_w": 450,
        "energy_import_kwh": 12345.678,
        "energy_export_kwh": 1234.567,
    }


@pytest.fixture()
def sample_device_id() -> str:
    """A deterministic device identifier for test assertions."""
    return "hw-p1-001"


@pytest.fixture()
def sample_ts() -> datetime:
    """A deterministic UTC timestamp for test assertions."""
    return datetime(2026, 2, 13, 14, 30, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Test: valid input -> correct normalized output
# ---------------------------------------------------------------------------


class TestNormalizeValidInput:
    """Valid raw input produces a correctly shaped and valued normalized dict."""

    def test_output_contains_all_expected_keys(
        self,
        valid_raw: dict,
        sample_device_id: str,
        sample_ts: datetime,
    ) -> None:
        """Normalized dict has exactly the expected output keys (AC2)."""
        result = normalize(valid_raw, sample_device_id, sample_ts)

        expected_keys = {
            "device_id",
            "ts",
            "power_w",
            "import_power_w",
            "energy_import_kwh",
            "energy_export_kwh",
        }
        assert set(result.keys()) == expected_keys

    def test_device_id_matches_input(
        self,
        valid_raw: dict,
        sample_device_id: str,
        sample_ts: datetime,
    ) -> None:
        """Output device_id equals the supplied device_id parameter."""
        result = normalize(valid_raw, sample_device_id, sample_ts)
        assert result["device_id"] == sample_device_id

    def test_ts_is_iso_8601_utc_string(
        self,
        valid_raw: dict,
        sample_device_id: str,
        sample_ts: datetime,
    ) -> None:
        """Output ts is an ISO 8601 UTC string (AC2)."""
        result = normalize(valid_raw, sample_device_id, sample_ts)
        assert result["ts"] == "2026-02-13T14:30:00+00:00"

    def test_power_w_matches_raw(
        self,
        valid_raw: dict,
        sample_device_id: str,
        sample_ts: datetime,
    ) -> None:
        """Output power_w equals the raw power_w value."""
        result = normalize(valid_raw, sample_device_id, sample_ts)
        assert result["power_w"] == 450

    def test_import_power_w_equals_positive_power(
        self,
        valid_raw: dict,
        sample_device_id: str,
        sample_ts: datetime,
    ) -> None:
        """When power_w is positive, import_power_w equals power_w (AC3)."""
        result = normalize(valid_raw, sample_device_id, sample_ts)
        assert result["import_power_w"] == 450

    def test_energy_import_kwh_matches_raw(
        self,
        valid_raw: dict,
        sample_device_id: str,
        sample_ts: datetime,
    ) -> None:
        """Output energy_import_kwh equals raw value."""
        result = normalize(valid_raw, sample_device_id, sample_ts)
        assert result["energy_import_kwh"] == 12345.678

    def test_energy_export_kwh_matches_raw(
        self,
        valid_raw: dict,
        sample_device_id: str,
        sample_ts: datetime,
    ) -> None:
        """Output energy_export_kwh equals raw value."""
        result = normalize(valid_raw, sample_device_id, sample_ts)
        assert result["energy_export_kwh"] == 1234.567


# ---------------------------------------------------------------------------
# Test: import_power_w clamping logic (AC3)
# ---------------------------------------------------------------------------


class TestImportPowerClamping:
    """import_power_w = max(power_w, 0): never negative."""

    def test_negative_power_w_yields_zero_import(
        self,
        sample_device_id: str,
        sample_ts: datetime,
    ) -> None:
        """Negative power_w (export) results in import_power_w == 0 (AC3)."""
        raw = {
            "power_w": -200,
            "energy_import_kwh": 100.0,
            "energy_export_kwh": 50.0,
        }
        result = normalize(raw, sample_device_id, sample_ts)
        assert result["import_power_w"] == 0

    def test_zero_power_w_yields_zero_import(
        self,
        sample_device_id: str,
        sample_ts: datetime,
    ) -> None:
        """Zero power_w results in import_power_w == 0 (AC3)."""
        raw = {
            "power_w": 0,
            "energy_import_kwh": 100.0,
            "energy_export_kwh": 50.0,
        }
        result = normalize(raw, sample_device_id, sample_ts)
        assert result["import_power_w"] == 0

    def test_positive_power_w_yields_same_import(
        self,
        sample_device_id: str,
        sample_ts: datetime,
    ) -> None:
        """Positive power_w is passed through to import_power_w (AC3)."""
        raw = {
            "power_w": 1500,
            "energy_import_kwh": 100.0,
            "energy_export_kwh": 50.0,
        }
        result = normalize(raw, sample_device_id, sample_ts)
        assert result["import_power_w"] == 1500

    def test_large_negative_power_w_yields_zero(
        self,
        sample_device_id: str,
        sample_ts: datetime,
    ) -> None:
        """Very large negative power_w still yields import_power_w == 0."""
        raw = {
            "power_w": -99999,
            "energy_import_kwh": 0.0,
            "energy_export_kwh": 5000.0,
        }
        result = normalize(raw, sample_device_id, sample_ts)
        assert result["import_power_w"] == 0


# ---------------------------------------------------------------------------
# Test: missing required fields -> ValueError (AC4)
# ---------------------------------------------------------------------------


class TestMissingRequiredFieldsRaiseValueError:
    """Missing required fields in raw input must raise ValueError (AC4)."""

    def test_missing_power_w_raises(
        self,
        sample_device_id: str,
        sample_ts: datetime,
    ) -> None:
        """Raw dict without 'power_w' raises ValueError."""
        raw = {
            "energy_import_kwh": 100.0,
            "energy_export_kwh": 50.0,
        }
        with pytest.raises(ValueError, match="power_w"):
            normalize(raw, sample_device_id, sample_ts)

    def test_missing_energy_import_kwh_raises(
        self,
        sample_device_id: str,
        sample_ts: datetime,
    ) -> None:
        """Raw dict without 'energy_import_kwh' raises ValueError."""
        raw = {
            "power_w": 450,
            "energy_export_kwh": 50.0,
        }
        with pytest.raises(ValueError, match="energy_import_kwh"):
            normalize(raw, sample_device_id, sample_ts)

    def test_missing_energy_export_kwh_raises(
        self,
        sample_device_id: str,
        sample_ts: datetime,
    ) -> None:
        """Raw dict without 'energy_export_kwh' raises ValueError."""
        raw = {
            "power_w": 450,
            "energy_import_kwh": 100.0,
        }
        with pytest.raises(ValueError, match="energy_export_kwh"):
            normalize(raw, sample_device_id, sample_ts)

    def test_empty_raw_dict_raises(
        self,
        sample_device_id: str,
        sample_ts: datetime,
    ) -> None:
        """Completely empty raw dict raises ValueError."""
        with pytest.raises(ValueError):
            normalize({}, sample_device_id, sample_ts)

    def test_missing_multiple_fields_raises(
        self,
        sample_device_id: str,
        sample_ts: datetime,
    ) -> None:
        """Raw dict missing multiple required fields raises ValueError."""
        raw = {"energy_export_kwh": 50.0}
        with pytest.raises(ValueError):
            normalize(raw, sample_device_id, sample_ts)


# ---------------------------------------------------------------------------
# Test: injectable timestamp (AC5)
# ---------------------------------------------------------------------------


class TestInjectableTimestamp:
    """The ts parameter controls the output timestamp (AC5)."""

    def test_output_ts_matches_provided_timestamp(
        self,
        valid_raw: dict,
        sample_device_id: str,
    ) -> None:
        """Output ts comes from the ts parameter, not datetime.now()."""
        specific_ts = datetime(2025, 6, 15, 8, 45, 30, tzinfo=UTC)
        result = normalize(valid_raw, sample_device_id, specific_ts)
        assert result["ts"] == "2025-06-15T08:45:30+00:00"

    def test_different_timestamps_produce_different_output(
        self,
        valid_raw: dict,
        sample_device_id: str,
    ) -> None:
        """Two calls with different ts produce different output timestamps."""
        ts_a = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
        ts_b = datetime(2026, 12, 31, 23, 59, 59, tzinfo=UTC)

        result_a = normalize(valid_raw, sample_device_id, ts_a)
        result_b = normalize(valid_raw, sample_device_id, ts_b)

        assert result_a["ts"] != result_b["ts"]
        assert result_a["ts"] == "2026-01-01T00:00:00+00:00"
        assert result_b["ts"] == "2026-12-31T23:59:59+00:00"

    def test_no_datetime_now_dependency(
        self,
        valid_raw: dict,
        sample_device_id: str,
    ) -> None:
        """Calling normalize twice with the same ts yields identical ts output.

        If datetime.now() were used internally, subsequent calls could differ.
        """
        fixed_ts = datetime(2026, 7, 4, 12, 0, 0, tzinfo=UTC)

        result_1 = normalize(valid_raw, sample_device_id, fixed_ts)
        result_2 = normalize(valid_raw, sample_device_id, fixed_ts)

        assert result_1["ts"] == result_2["ts"]


# ---------------------------------------------------------------------------
# Test: extra fields in raw input are ignored
# ---------------------------------------------------------------------------


class TestExtraFieldsIgnored:
    """Extra fields in raw input are silently ignored."""

    def test_extra_fields_do_not_appear_in_output(
        self,
        sample_device_id: str,
        sample_ts: datetime,
    ) -> None:
        """Raw dict with extra HomeWizard fields produces clean output."""
        raw = {
            "power_w": 300,
            "energy_import_kwh": 100.0,
            "energy_export_kwh": 50.0,
            "total_power_import_kwh": 9999.0,
            "wifi_strength": 80,
        }
        result = normalize(raw, sample_device_id, sample_ts)

        expected_keys = {
            "device_id",
            "ts",
            "power_w",
            "import_power_w",
            "energy_import_kwh",
            "energy_export_kwh",
        }
        assert set(result.keys()) == expected_keys


# -----------------------------------------------------------
# Test: naive (tz-unaware) timestamp is rejected
# -----------------------------------------------------------


class TestNaiveTimestampRejected:
    """Naive timestamps must be rejected to enforce UTC contract."""

    def test_naive_datetime_raises_value_error(
        self,
        valid_raw: dict,
        sample_device_id: str,
    ) -> None:
        """Naive datetime (no tzinfo) raises ValueError."""
        naive_ts = datetime(2026, 2, 13, 14, 30, 0)
        with pytest.raises(ValueError, match="timezone-aware"):
            normalize(valid_raw, sample_device_id, naive_ts)
