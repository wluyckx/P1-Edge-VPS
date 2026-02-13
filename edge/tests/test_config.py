"""
Unit tests for edge daemon configuration (EdgeSettings).

Tests verify:
- Config loads from environment variables with correct defaults.
- Config validation rejects missing required variables.
- VPS_INGEST_URL is validated as HTTPS (HC-003).
- Numeric constraints are enforced (poll_interval, batch_size).

CHANGELOG:
- 2026-02-13: Initial creation (STORY-001)

TODO:
- None
"""

import pytest
from edge.src.config import EdgeSettings
from pydantic import ValidationError


class TestEdgeSettingsLoadsFromEnv:
    """Config loads all values from environment variables."""

    def test_loads_all_env_vars(self, env_vars_full: dict[str, str]) -> None:
        """All env vars are read and assigned correctly."""
        settings = EdgeSettings()

        assert settings.hw_p1_host == env_vars_full["HW_P1_HOST"]
        assert settings.hw_p1_token == env_vars_full["HW_P1_TOKEN"]
        assert settings.vps_ingest_url == env_vars_full["VPS_INGEST_URL"]
        assert settings.vps_device_token == env_vars_full["VPS_DEVICE_TOKEN"]
        assert settings.poll_interval_s == int(env_vars_full["POLL_INTERVAL_S"])
        assert settings.batch_size == int(env_vars_full["BATCH_SIZE"])
        assert settings.upload_interval_s == int(env_vars_full["UPLOAD_INTERVAL_S"])
        assert settings.spool_path == env_vars_full["SPOOL_PATH"]

    def test_defaults_applied_when_optional_vars_missing(
        self, env_vars_required_only: dict[str, str]
    ) -> None:
        """Optional variables use default values when not set."""
        settings = EdgeSettings()

        assert settings.hw_p1_host == env_vars_required_only["HW_P1_HOST"]
        assert settings.hw_p1_token == env_vars_required_only["HW_P1_TOKEN"]
        assert settings.vps_ingest_url == env_vars_required_only["VPS_INGEST_URL"]
        assert settings.vps_device_token == env_vars_required_only["VPS_DEVICE_TOKEN"]
        # Defaults
        assert settings.poll_interval_s == 2
        assert settings.batch_size == 30
        assert settings.upload_interval_s == 10
        assert settings.spool_path == "/data/spool.db"


class TestEdgeSettingsRequiredVars:
    """Config validation rejects missing required variables."""

    def test_missing_hw_p1_host_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """HW_P1_HOST is required."""
        monkeypatch.setenv("HW_P1_TOKEN", "token")
        monkeypatch.setenv("VPS_INGEST_URL", "https://example.com")
        monkeypatch.setenv("VPS_DEVICE_TOKEN", "device-token")

        with pytest.raises(ValidationError) as exc_info:
            EdgeSettings()
        assert "hw_p1_host" in str(exc_info.value).lower()

    def test_missing_hw_p1_token_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """HW_P1_TOKEN is required."""
        monkeypatch.setenv("HW_P1_HOST", "192.168.1.1")
        monkeypatch.setenv("VPS_INGEST_URL", "https://example.com")
        monkeypatch.setenv("VPS_DEVICE_TOKEN", "device-token")

        with pytest.raises(ValidationError) as exc_info:
            EdgeSettings()
        assert "hw_p1_token" in str(exc_info.value).lower()

    def test_missing_vps_ingest_url_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """VPS_INGEST_URL is required."""
        monkeypatch.setenv("HW_P1_HOST", "192.168.1.1")
        monkeypatch.setenv("HW_P1_TOKEN", "token")
        monkeypatch.setenv("VPS_DEVICE_TOKEN", "device-token")

        with pytest.raises(ValidationError) as exc_info:
            EdgeSettings()
        assert "vps_ingest_url" in str(exc_info.value).lower()

    def test_missing_vps_device_token_raises(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """VPS_DEVICE_TOKEN is required."""
        monkeypatch.setenv("HW_P1_HOST", "192.168.1.1")
        monkeypatch.setenv("HW_P1_TOKEN", "token")
        monkeypatch.setenv("VPS_INGEST_URL", "https://example.com")

        with pytest.raises(ValidationError) as exc_info:
            EdgeSettings()
        assert "vps_device_token" in str(exc_info.value).lower()

    def test_missing_all_required_raises(self) -> None:
        """All four required vars missing causes validation error."""
        with pytest.raises(ValidationError) as exc_info:
            EdgeSettings()
        errors = str(exc_info.value).lower()
        assert "hw_p1_host" in errors
        assert "hw_p1_token" in errors
        assert "vps_ingest_url" in errors
        assert "vps_device_token" in errors


class TestVpsIngestUrlHttpsValidation:
    """VPS_INGEST_URL must be HTTPS per HC-003."""

    def test_http_url_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """HTTP URL is rejected with a clear error message."""
        monkeypatch.setenv("HW_P1_HOST", "192.168.1.1")
        monkeypatch.setenv("HW_P1_TOKEN", "token")
        monkeypatch.setenv("VPS_INGEST_URL", "http://insecure.example.com")
        monkeypatch.setenv("VPS_DEVICE_TOKEN", "device-token")

        with pytest.raises(ValidationError) as exc_info:
            EdgeSettings()
        assert "https" in str(exc_info.value).lower()

    def test_https_url_accepted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """HTTPS URL passes validation."""
        monkeypatch.setenv("HW_P1_HOST", "192.168.1.1")
        monkeypatch.setenv("HW_P1_TOKEN", "token")
        monkeypatch.setenv("VPS_INGEST_URL", "https://secure.example.com")
        monkeypatch.setenv("VPS_DEVICE_TOKEN", "device-token")

        settings = EdgeSettings()
        assert settings.vps_ingest_url == "https://secure.example.com"

    def test_empty_url_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Empty string is not a valid HTTPS URL."""
        monkeypatch.setenv("HW_P1_HOST", "192.168.1.1")
        monkeypatch.setenv("HW_P1_TOKEN", "token")
        monkeypatch.setenv("VPS_INGEST_URL", "")
        monkeypatch.setenv("VPS_DEVICE_TOKEN", "device-token")

        with pytest.raises(ValidationError) as exc_info:
            EdgeSettings()
        assert "https" in str(exc_info.value).lower()

    def test_ftp_url_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Non-HTTP schemes (ftp, etc.) are rejected."""
        monkeypatch.setenv("HW_P1_HOST", "192.168.1.1")
        monkeypatch.setenv("HW_P1_TOKEN", "token")
        monkeypatch.setenv("VPS_INGEST_URL", "ftp://files.example.com")
        monkeypatch.setenv("VPS_DEVICE_TOKEN", "device-token")

        with pytest.raises(ValidationError) as exc_info:
            EdgeSettings()
        assert "https" in str(exc_info.value).lower()


class TestDeviceIdConfig:
    """DEVICE_ID defaults to hw_p1_host but can be overridden."""

    def test_device_id_defaults_to_hw_p1_host(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When DEVICE_ID is not set, it defaults to HW_P1_HOST."""
        monkeypatch.setenv("HW_P1_HOST", "192.168.1.5")
        monkeypatch.setenv("HW_P1_TOKEN", "token")
        monkeypatch.setenv("VPS_INGEST_URL", "https://example.com")
        monkeypatch.setenv("VPS_DEVICE_TOKEN", "device-token")

        settings = EdgeSettings()
        assert settings.device_id == "192.168.1.5"

    def test_device_id_explicit_overrides_host(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Explicit DEVICE_ID overrides the hw_p1_host default."""
        monkeypatch.setenv("HW_P1_HOST", "192.168.1.5")
        monkeypatch.setenv("HW_P1_TOKEN", "token")
        monkeypatch.setenv("VPS_INGEST_URL", "https://example.com")
        monkeypatch.setenv("VPS_DEVICE_TOKEN", "device-token")
        monkeypatch.setenv("DEVICE_ID", "device-1")

        settings = EdgeSettings()
        assert settings.device_id == "device-1"


class TestNumericConstraints:
    """Numeric configuration values must be within valid ranges."""

    def test_poll_interval_zero_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """POLL_INTERVAL_S must be >= 1."""
        monkeypatch.setenv("HW_P1_HOST", "192.168.1.1")
        monkeypatch.setenv("HW_P1_TOKEN", "token")
        monkeypatch.setenv("VPS_INGEST_URL", "https://example.com")
        monkeypatch.setenv("VPS_DEVICE_TOKEN", "device-token")
        monkeypatch.setenv("POLL_INTERVAL_S", "0")

        with pytest.raises(ValidationError) as exc_info:
            EdgeSettings()
        assert "poll_interval_s" in str(exc_info.value).lower()

    def test_poll_interval_negative_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Negative POLL_INTERVAL_S is rejected."""
        monkeypatch.setenv("HW_P1_HOST", "192.168.1.1")
        monkeypatch.setenv("HW_P1_TOKEN", "token")
        monkeypatch.setenv("VPS_INGEST_URL", "https://example.com")
        monkeypatch.setenv("VPS_DEVICE_TOKEN", "device-token")
        monkeypatch.setenv("POLL_INTERVAL_S", "-1")

        with pytest.raises(ValidationError):
            EdgeSettings()

    def test_batch_size_zero_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """BATCH_SIZE must be >= 1."""
        monkeypatch.setenv("HW_P1_HOST", "192.168.1.1")
        monkeypatch.setenv("HW_P1_TOKEN", "token")
        monkeypatch.setenv("VPS_INGEST_URL", "https://example.com")
        monkeypatch.setenv("VPS_DEVICE_TOKEN", "device-token")
        monkeypatch.setenv("BATCH_SIZE", "0")

        with pytest.raises(ValidationError) as exc_info:
            EdgeSettings()
        assert "batch_size" in str(exc_info.value).lower()

    def test_batch_size_over_1000_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """BATCH_SIZE must be <= 1000."""
        monkeypatch.setenv("HW_P1_HOST", "192.168.1.1")
        monkeypatch.setenv("HW_P1_TOKEN", "token")
        monkeypatch.setenv("VPS_INGEST_URL", "https://example.com")
        monkeypatch.setenv("VPS_DEVICE_TOKEN", "device-token")
        monkeypatch.setenv("BATCH_SIZE", "1001")

        with pytest.raises(ValidationError) as exc_info:
            EdgeSettings()
        assert "batch_size" in str(exc_info.value).lower()

    def test_valid_custom_numeric_values(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Custom valid numeric values are accepted."""
        monkeypatch.setenv("HW_P1_HOST", "192.168.1.1")
        monkeypatch.setenv("HW_P1_TOKEN", "token")
        monkeypatch.setenv("VPS_INGEST_URL", "https://example.com")
        monkeypatch.setenv("VPS_DEVICE_TOKEN", "device-token")
        monkeypatch.setenv("POLL_INTERVAL_S", "5")
        monkeypatch.setenv("BATCH_SIZE", "100")
        monkeypatch.setenv("UPLOAD_INTERVAL_S", "30")

        settings = EdgeSettings()
        assert settings.poll_interval_s == 5
        assert settings.batch_size == 100
        assert settings.upload_interval_s == 30
