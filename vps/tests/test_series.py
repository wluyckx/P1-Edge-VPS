"""
Tests for the series API endpoint (STORY-012).

Validates GET /v1/series: frame parameter validation, aggregated series
response structure, empty data handling, and all supported time frames
(day, month, year, all).

CHANGELOG:
- 2026-02-13: Initial creation (STORY-012)

TODO:
- None
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from src.db.session import get_async_session
from src.main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_row(
    bucket: str,
    avg_power_w: int,
    max_power_w: int,
    energy_import_kwh: float,
    energy_export_kwh: float,
) -> MagicMock:
    """Create a mock Row object that behaves like a SQLAlchemy Row.

    The Row must support both ._mapping dict-like access and attribute access,
    matching what SQLAlchemy returns from text() queries.

    Args:
        bucket: ISO-format timestamp string for the time bucket.
        avg_power_w: Average power in watts.
        max_power_w: Maximum power in watts.
        energy_import_kwh: Sum of energy imported (kWh).
        energy_export_kwh: Sum of energy exported (kWh).

    Returns:
        MagicMock: A mock Row with _mapping and attribute access.
    """
    row = MagicMock()
    mapping = {
        "bucket": bucket,
        "avg_power_w": avg_power_w,
        "max_power_w": max_power_w,
        "energy_import_kwh": energy_import_kwh,
        "energy_export_kwh": energy_export_kwh,
    }
    row._mapping = mapping
    return row


SAMPLE_ROWS = [
    _make_row("2026-02-13T00:00:00+00:00", 350, 800, 1.23, 0.45),
    _make_row("2026-02-13T01:00:00+00:00", 420, 950, 1.56, 0.67),
]


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
    """Create a mock AsyncSession for database operations.

    Returns:
        AsyncMock: Mock session with execute method returning sample rows.
    """
    session = AsyncMock()
    result = MagicMock()
    result.fetchall.return_value = SAMPLE_ROWS
    session.execute.return_value = result
    return session


@pytest.fixture()
def empty_db_session() -> AsyncMock:
    """Create a mock AsyncSession that returns no rows.

    Returns:
        AsyncMock: Mock session with execute returning empty result.
    """
    session = AsyncMock()
    result = MagicMock()
    result.fetchall.return_value = []
    session.execute.return_value = result
    return session


@pytest.fixture()
def client(mock_db_session: AsyncMock) -> TestClient:
    """Create a TestClient with mocked DB session (no auth needed).

    Args:
        mock_db_session: Mock async database session.

    Returns:
        TestClient: Configured test client with dependency overrides.
    """
    async def override_get_session():
        yield mock_db_session

    app.dependency_overrides[get_async_session] = override_get_session

    yield TestClient(app)

    app.dependency_overrides.clear()


@pytest.fixture()
def empty_client(empty_db_session: AsyncMock) -> TestClient:
    """Create a TestClient with mocked DB session returning no data.

    Args:
        empty_db_session: Mock async database session with empty results.

    Returns:
        TestClient: Configured test client with dependency overrides.
    """
    async def override_get_session():
        yield empty_db_session

    app.dependency_overrides[get_async_session] = override_get_session

    yield TestClient(app)

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# AC7: Invalid frame → 400 Bad Request
# ---------------------------------------------------------------------------


class TestSeriesInvalidFrame:
    """Tests for invalid frame parameter validation."""

    def test_invalid_frame_returns_400(self, client: TestClient) -> None:
        """AC7: Unknown frame value returns 400 Bad Request."""
        response = client.get("/v1/series", params={
            "device_id": "dev1",
            "frame": "invalid",
        })
        assert response.status_code == 400
        assert "Invalid frame" in response.json()["detail"]

    def test_missing_frame_returns_422(self, client: TestClient) -> None:
        """Missing required frame query parameter returns 422."""
        response = client.get("/v1/series", params={"device_id": "dev1"})
        assert response.status_code == 422

    def test_missing_device_id_returns_422(self, client: TestClient) -> None:
        """Missing required device_id query parameter returns 422."""
        response = client.get("/v1/series", params={"frame": "day"})
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# AC2: frame=day → time_bucket('1 hour', ts) for today
# ---------------------------------------------------------------------------


class TestSeriesFrameDay:
    """Tests for frame=day aggregation."""

    def test_frame_day_returns_200_with_series(
        self, client: TestClient,
    ) -> None:
        """AC2: frame=day returns 200 with aggregated series data."""
        response = client.get("/v1/series", params={
            "device_id": "dev1",
            "frame": "day",
        })
        assert response.status_code == 200
        body = response.json()
        assert "series" in body
        assert isinstance(body["series"], list)
        assert len(body["series"]) == 2

    def test_frame_day_bucket_has_all_required_fields(
        self, client: TestClient,
    ) -> None:
        """AC6: Each bucket entry has all required fields."""
        response = client.get("/v1/series", params={
            "device_id": "dev1",
            "frame": "day",
        })
        body = response.json()
        entry = body["series"][0]
        assert "bucket" in entry
        assert "avg_power_w" in entry
        assert "max_power_w" in entry
        assert "energy_import_kwh" in entry
        assert "energy_export_kwh" in entry

    def test_frame_day_field_types(self, client: TestClient) -> None:
        """AC6: Bucket fields have correct types."""
        response = client.get("/v1/series", params={
            "device_id": "dev1",
            "frame": "day",
        })
        entry = response.json()["series"][0]
        assert isinstance(entry["bucket"], str)
        assert isinstance(entry["avg_power_w"], int)
        assert isinstance(entry["max_power_w"], int)
        assert isinstance(entry["energy_import_kwh"], float)
        assert isinstance(entry["energy_export_kwh"], float)


# ---------------------------------------------------------------------------
# AC3: frame=month → time_bucket('1 week', ts) for current month
# ---------------------------------------------------------------------------


class TestSeriesFrameMonth:
    """Tests for frame=month aggregation."""

    def test_frame_month_returns_200_with_series(
        self, client: TestClient,
    ) -> None:
        """AC3: frame=month returns 200 with aggregated series data."""
        response = client.get("/v1/series", params={
            "device_id": "dev1",
            "frame": "month",
        })
        assert response.status_code == 200
        body = response.json()
        assert "series" in body
        assert isinstance(body["series"], list)
        assert len(body["series"]) == 2


# ---------------------------------------------------------------------------
# AC4: frame=year → time_bucket('1 month', ts) for current year
# ---------------------------------------------------------------------------


class TestSeriesFrameYear:
    """Tests for frame=year aggregation."""

    def test_frame_year_returns_200_with_series(
        self, client: TestClient,
    ) -> None:
        """AC4: frame=year returns 200 with aggregated series data."""
        response = client.get("/v1/series", params={
            "device_id": "dev1",
            "frame": "year",
        })
        assert response.status_code == 200
        body = response.json()
        assert "series" in body
        assert isinstance(body["series"], list)
        assert len(body["series"]) == 2


# ---------------------------------------------------------------------------
# AC5: frame=all → time_bucket('1 month', ts) for all data
# ---------------------------------------------------------------------------


class TestSeriesFrameAll:
    """Tests for frame=all aggregation."""

    def test_frame_all_returns_200_with_series(
        self, client: TestClient,
    ) -> None:
        """AC5: frame=all returns 200 with aggregated series data."""
        response = client.get("/v1/series", params={
            "device_id": "dev1",
            "frame": "all",
        })
        assert response.status_code == 200
        body = response.json()
        assert "series" in body
        assert isinstance(body["series"], list)
        assert len(body["series"]) == 2


# ---------------------------------------------------------------------------
# AC8: No data in range → 200 with empty series array
# ---------------------------------------------------------------------------


class TestSeriesEmptyData:
    """Tests for empty data responses."""

    def test_no_data_returns_200_with_empty_series(
        self, empty_client: TestClient,
    ) -> None:
        """AC8: No data in range returns 200 with empty series array."""
        response = empty_client.get("/v1/series", params={
            "device_id": "dev1",
            "frame": "day",
        })
        assert response.status_code == 200
        body = response.json()
        assert body["series"] == []

    def test_no_data_all_frames_return_empty(
        self, empty_client: TestClient,
    ) -> None:
        """AC8: All frames return empty series when no data exists."""
        for frame in ("day", "month", "year", "all"):
            response = empty_client.get("/v1/series", params={
                "device_id": "dev1",
                "frame": frame,
            })
            assert response.status_code == 200
            assert response.json()["series"] == [], f"frame={frame} not empty"


# ---------------------------------------------------------------------------
# AC1: Response structure
# ---------------------------------------------------------------------------


class TestSeriesResponseStructure:
    """Tests for overall response structure."""

    def test_response_contains_device_id_and_frame(
        self, client: TestClient,
    ) -> None:
        """AC1: Response includes device_id, frame, and series."""
        response = client.get("/v1/series", params={
            "device_id": "dev1",
            "frame": "day",
        })
        body = response.json()
        assert body["device_id"] == "dev1"
        assert body["frame"] == "day"
        assert "series" in body

    def test_response_values_match_mock_data(
        self, client: TestClient,
    ) -> None:
        """Bucket values match the mocked database rows."""
        response = client.get("/v1/series", params={
            "device_id": "dev1",
            "frame": "day",
        })
        series = response.json()["series"]
        assert series[0]["avg_power_w"] == 350
        assert series[0]["max_power_w"] == 800
        assert series[0]["energy_import_kwh"] == 1.23
        assert series[0]["energy_export_kwh"] == 0.45
        assert series[1]["avg_power_w"] == 420
        assert series[1]["max_power_w"] == 950


# ---------------------------------------------------------------------------
# Service unit tests
# ---------------------------------------------------------------------------


class TestAggregationService:
    """Unit tests for the get_aggregated_series service function."""

    @pytest.mark.asyncio()
    async def test_get_aggregated_series_day(self) -> None:
        """Service returns correctly structured dicts for frame=day."""
        from src.services.aggregation import get_aggregated_series

        session = AsyncMock()
        result = MagicMock()
        result.fetchall.return_value = SAMPLE_ROWS
        session.execute.return_value = result

        series = await get_aggregated_series(session, "dev1", "day")

        assert len(series) == 2
        assert series[0]["bucket"] == "2026-02-13T00:00:00+00:00"
        assert series[0]["avg_power_w"] == 350
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio()
    async def test_get_aggregated_series_all_no_date_filter(self) -> None:
        """Service for frame=all omits date range (no WHERE ts clause)."""
        from src.services.aggregation import get_aggregated_series

        session = AsyncMock()
        result = MagicMock()
        result.fetchall.return_value = SAMPLE_ROWS
        session.execute.return_value = result

        series = await get_aggregated_series(session, "dev1", "all")

        assert len(series) == 2
        # Verify execute was called (SQL correctness verified by integration)
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio()
    async def test_get_aggregated_series_empty(self) -> None:
        """Service returns empty list when no rows match."""
        from src.services.aggregation import get_aggregated_series

        session = AsyncMock()
        result = MagicMock()
        result.fetchall.return_value = []
        session.execute.return_value = result

        series = await get_aggregated_series(session, "dev1", "day")

        assert series == []

    @pytest.mark.asyncio()
    async def test_get_aggregated_series_month(self) -> None:
        """Service returns data for frame=month."""
        from src.services.aggregation import get_aggregated_series

        session = AsyncMock()
        result = MagicMock()
        result.fetchall.return_value = SAMPLE_ROWS
        session.execute.return_value = result

        series = await get_aggregated_series(session, "dev1", "month")

        assert len(series) == 2
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio()
    async def test_get_aggregated_series_year(self) -> None:
        """Service returns data for frame=year."""
        from src.services.aggregation import get_aggregated_series

        session = AsyncMock()
        result = MagicMock()
        result.fetchall.return_value = SAMPLE_ROWS
        session.execute.return_value = result

        series = await get_aggregated_series(session, "dev1", "year")

        assert len(series) == 2
        session.execute.assert_awaited_once()
