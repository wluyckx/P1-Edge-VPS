"""
Tests for the daily-energy API endpoint.

Validates GET /v1/daily-energy?device_id={id}: successful delta computation,
device_id mismatch (403), no samples today (404), and null energy values.

CHANGELOG:
- 2026-03-13: Initial creation (fix 0.0 kWh on Hestia home tile)

TODO:
- None
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from src.api.deps import get_current_device_id
from src.db.session import get_async_session
from src.main import app

DEVICE_ID = "dev1"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _set_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure required env vars are set for every test."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("DEVICE_TOKENS", "test:dev1")


@pytest.fixture()
def mock_db_session() -> AsyncMock:
    """Create a mock AsyncSession for database operations."""
    return AsyncMock()


@pytest.fixture()
def client(mock_db_session: AsyncMock) -> TestClient:
    """Create a TestClient with mocked DB session and auth dependency."""

    async def override_get_session():
        yield mock_db_session

    async def override_device_id():
        return "dev1"

    app.dependency_overrides[get_async_session] = override_get_session
    app.dependency_overrides[get_current_device_id] = override_device_id

    yield TestClient(app)

    app.dependency_overrides.clear()


@pytest.fixture()
def unauth_client(mock_db_session: AsyncMock) -> TestClient:
    """Create a TestClient with mocked DB but NO auth override."""

    async def override_get_session():
        yield mock_db_session

    app.dependency_overrides[get_async_session] = override_get_session

    yield TestClient(app)

    app.dependency_overrides.clear()


def _make_db_result(sample_count: int, import_kwh: float, export_kwh: float) -> MagicMock:
    """Create a mock DB result row for the daily-energy query."""
    row = MagicMock()
    row._mapping = {
        "sample_count": sample_count,
        "import_today_kwh": import_kwh,
        "export_today_kwh": export_kwh,
    }
    result = MagicMock()
    result.fetchone.return_value = row
    return result


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_daily_energy_success(client: TestClient, mock_db_session: AsyncMock) -> None:
    """Successful response with sample data returns today's energy delta."""
    mock_db_session.execute.return_value = _make_db_result(1440, 8.321, 12.567)

    resp = client.get("/v1/daily-energy", params={"device_id": DEVICE_ID})

    assert resp.status_code == 200
    data = resp.json()
    assert data["device_id"] == DEVICE_ID
    assert data["import_today_kwh"] == 8.321
    assert data["export_today_kwh"] == 12.567
    assert data["sample_count"] == 1440
    assert "date" in data


def test_daily_energy_zero_values(client: TestClient, mock_db_session: AsyncMock) -> None:
    """Zero delta when all samples have the same cumulative value."""
    mock_db_session.execute.return_value = _make_db_result(100, 0.0, 0.0)

    resp = client.get("/v1/daily-energy", params={"device_id": DEVICE_ID})

    assert resp.status_code == 200
    data = resp.json()
    assert data["import_today_kwh"] == 0.0
    assert data["export_today_kwh"] == 0.0


def test_daily_energy_no_samples_404(client: TestClient, mock_db_session: AsyncMock) -> None:
    """404 when no samples exist for today."""
    mock_db_session.execute.return_value = _make_db_result(0, 0.0, 0.0)

    resp = client.get("/v1/daily-energy", params={"device_id": DEVICE_ID})

    assert resp.status_code == 404
    assert "No samples" in resp.json()["detail"]


def test_daily_energy_device_mismatch_403(client: TestClient, mock_db_session: AsyncMock) -> None:
    """403 when query device_id doesn't match authenticated device."""
    resp = client.get("/v1/daily-energy", params={"device_id": "wrong-device"})

    assert resp.status_code == 403
    assert "mismatch" in resp.json()["detail"].lower()


def test_daily_energy_no_auth_401(unauth_client: TestClient, mock_db_session: AsyncMock) -> None:
    """401 when no Bearer token provided."""
    resp = unauth_client.get("/v1/daily-energy", params={"device_id": DEVICE_ID})

    assert resp.status_code == 401


def test_daily_energy_response_schema(client: TestClient, mock_db_session: AsyncMock) -> None:
    """Response contains all required fields with correct types."""
    mock_db_session.execute.return_value = _make_db_result(500, 5.123, 3.456)

    resp = client.get("/v1/daily-energy", params={"device_id": DEVICE_ID})

    assert resp.status_code == 200
    data = resp.json()
    required_fields = {"device_id", "date", "import_today_kwh", "export_today_kwh", "sample_count"}
    assert required_fields.issubset(data.keys())
    assert isinstance(data["import_today_kwh"], float)
    assert isinstance(data["export_today_kwh"], float)
    assert isinstance(data["sample_count"], int)
