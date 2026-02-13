"""
Edge daemon configuration loaded from environment variables.

Uses Pydantic BaseSettings for automatic env var loading and validation.
All configuration values come from environment variables or .env files;
no hardcoded IPs, URLs, or credentials.

CHANGELOG:
- 2026-02-13: Initial creation (STORY-001)

TODO:
- None
"""

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings


class EdgeSettings(BaseSettings):
    """Edge daemon configuration.

    All values are loaded from environment variables. Required variables
    must be set; optional variables have sensible defaults.

    Attributes:
        hw_p1_host: HomeWizard P1 meter IP/hostname on local LAN.
        hw_p1_token: HomeWizard Local API v2 bearer token.
        vps_ingest_url: VPS base URL for ingestion (must be HTTPS).
        vps_device_token: Per-device bearer token for VPS auth.
        device_id: Device identifier sent in samples. Must match the
            device_id mapped to vps_device_token on the VPS side.
            Defaults to hw_p1_host if not set.
        poll_interval_s: Seconds between P1 polls.
        batch_size: Max samples per upload batch.
        upload_interval_s: Seconds between upload attempts.
        spool_path: SQLite spool file path for local buffering.
    """

    hw_p1_host: str
    hw_p1_token: str
    vps_ingest_url: str
    vps_device_token: str
    device_id: str = ""
    poll_interval_s: int = 2
    batch_size: int = 30
    upload_interval_s: int = 10
    spool_path: str = "/data/spool.db"

    @model_validator(mode="after")
    def _default_device_id(self) -> "EdgeSettings":
        """Default device_id to hw_p1_host when not explicitly set."""
        if not self.device_id:
            self.device_id = self.hw_p1_host
        return self

    @field_validator("vps_ingest_url")
    @classmethod
    def vps_ingest_url_must_be_https(cls, v: str) -> str:
        """Validate that VPS ingest URL uses HTTPS (HC-003).

        All edge-to-VPS communication must use HTTPS with valid certificates.
        HTTP URLs are rejected at startup to prevent insecure transport.
        """
        if not v.startswith("https://"):
            raise ValueError(
                "VPS_INGEST_URL must use HTTPS (got: "
                f"'{v[:20]}...'). See HC-003: HTTPS Only."
            )
        return v

    @field_validator("poll_interval_s")
    @classmethod
    def poll_interval_must_be_positive(cls, v: int) -> int:
        """Validate poll interval is at least 1 second."""
        if v < 1:
            raise ValueError("POLL_INTERVAL_S must be >= 1")
        return v

    @field_validator("batch_size")
    @classmethod
    def batch_size_must_be_valid(cls, v: int) -> int:
        """Validate batch size is between 1 and 1000."""
        if v < 1 or v > 1000:
            raise ValueError("BATCH_SIZE must be >= 1 and <= 1000")
        return v

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}
