"""
Shared test fixtures for edge daemon tests.

CHANGELOG:
- 2026-02-13: Initial creation (STORY-001)

TODO:
- None
"""

import pytest

# All EdgeSettings environment variable names, used for cleanup.
_ALL_EDGE_ENV_VARS = (
    "HW_P1_HOST",
    "HW_P1_TOKEN",
    "VPS_INGEST_URL",
    "VPS_DEVICE_TOKEN",
    "POLL_INTERVAL_S",
    "BATCH_SIZE",
    "UPLOAD_INTERVAL_S",
    "SPOOL_PATH",
)


@pytest.fixture(autouse=True)
def _clean_edge_env(monkeypatch: pytest.MonkeyPatch, tmp_path: str) -> None:
    """Remove all edge env vars and isolate from .env files before each test.

    This runs automatically for every test in the edge test suite.
    Individual tests or fixtures then set only the vars they need.
    Changes working directory to tmp_path so no .env file is accidentally
    loaded by Pydantic BaseSettings.
    """
    for var in _ALL_EDGE_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.chdir(tmp_path)


@pytest.fixture()
def env_vars_full(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Set all required and optional environment variables for EdgeSettings.

    Returns the dict of env var names to values for assertion convenience.
    """
    env = {
        "HW_P1_HOST": "192.168.1.100",
        "HW_P1_TOKEN": "test-hw-token",
        "VPS_INGEST_URL": "https://vps.example.com",
        "VPS_DEVICE_TOKEN": "test-device-token",
        "POLL_INTERVAL_S": "2",
        "BATCH_SIZE": "30",
        "UPLOAD_INTERVAL_S": "10",
        "SPOOL_PATH": "/tmp/test-spool.db",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return env


@pytest.fixture()
def env_vars_required_only(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Set only the required environment variables (no optional ones).

    Optional variables should fall back to their defaults.
    """
    env = {
        "HW_P1_HOST": "10.0.0.50",
        "HW_P1_TOKEN": "hw-token-abc",
        "VPS_INGEST_URL": "https://ingest.example.com",
        "VPS_DEVICE_TOKEN": "device-token-xyz",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return env
