"""
Tests for the series API endpoint (STORY-012, STORY-013).

Validates GET /v1/series: frame parameter validation, aggregated series
response structure, empty data handling, and all supported time frames
(day, month, year, all). Verifies that queries target continuous aggregate
views (p1_hourly, p1_daily, p1_monthly) instead of raw p1_samples.

CHANGELOG:
- 2026-02-13: Update tests for continuous aggregate views (STORY-013)
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
# AC7: Invalid frame -> 400 Bad Request
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
# AC2: frame=day -> query p1_hourly view for today
# ---------------------------------------------------------------------------


class TestSeriesFrameDay:
    """Tests for frame=day aggregation using p1_hourly view."""

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
# AC3: frame=month -> re-bucket p1_daily to 1-week intervals
# ---------------------------------------------------------------------------


class TestSeriesFrameMonth:
    """Tests for frame=month aggregation using p1_daily view."""

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
# AC4: frame=year -> query p1_monthly view for current year
# ---------------------------------------------------------------------------


class TestSeriesFrameYear:
    """Tests for frame=year aggregation using p1_monthly view."""

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
# AC5: frame=all -> query p1_monthly view for all data
# ---------------------------------------------------------------------------


class TestSeriesFrameAll:
    """Tests for frame=all aggregation using p1_monthly view."""

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
# AC8: No data in range -> 200 with empty series array
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
            assert response.json()["series"] == [], (
                f"frame={frame} not empty"
            )


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
    async def test_get_aggregated_series_day_queries_p1_hourly(
        self,
    ) -> None:
        """AC5: frame=day queries p1_hourly view directly."""
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

        # Verify SQL targets p1_hourly, not p1_samples.
        executed_sql = str(
            session.execute.call_args[0][0].text,
        )
        assert "p1_hourly" in executed_sql
        assert "p1_samples" not in executed_sql

    @pytest.mark.asyncio()
    async def test_get_aggregated_series_month_queries_p1_daily(
        self,
    ) -> None:
        """AC5: frame=month queries p1_daily with time_bucket rebucket."""
        from src.services.aggregation import get_aggregated_series

        session = AsyncMock()
        result = MagicMock()
        result.fetchall.return_value = SAMPLE_ROWS
        session.execute.return_value = result

        series = await get_aggregated_series(session, "dev1", "month")

        assert len(series) == 2
        session.execute.assert_awaited_once()

        # Verify SQL targets p1_daily with time_bucket re-aggregation.
        executed_sql = str(
            session.execute.call_args[0][0].text,
        )
        assert "p1_daily" in executed_sql
        assert "time_bucket" in executed_sql
        assert "p1_samples" not in executed_sql

    @pytest.mark.asyncio()
    async def test_month_rebucket_uses_weighted_average(self) -> None:
        """Rebucket uses sample_count weighted average, not AVG(avg_power_w)."""
        from src.services.aggregation import get_aggregated_series

        session = AsyncMock()
        result = MagicMock()
        result.fetchall.return_value = []
        session.execute.return_value = result

        await get_aggregated_series(session, "dev1", "month")

        executed_sql = str(
            session.execute.call_args[0][0].text,
        )
        assert "sample_count" in executed_sql
        assert "AVG(avg_power_w)" not in executed_sql

    @pytest.mark.asyncio()
    async def test_get_aggregated_series_year_queries_p1_monthly(
        self,
    ) -> None:
        """AC5: frame=year queries p1_monthly view directly."""
        from src.services.aggregation import get_aggregated_series

        session = AsyncMock()
        result = MagicMock()
        result.fetchall.return_value = SAMPLE_ROWS
        session.execute.return_value = result

        series = await get_aggregated_series(session, "dev1", "year")

        assert len(series) == 2
        session.execute.assert_awaited_once()

        # Verify SQL targets p1_monthly, not p1_samples.
        executed_sql = str(
            session.execute.call_args[0][0].text,
        )
        assert "p1_monthly" in executed_sql
        assert "p1_samples" not in executed_sql

    @pytest.mark.asyncio()
    async def test_get_aggregated_series_all_queries_p1_monthly(
        self,
    ) -> None:
        """AC5: frame=all queries p1_monthly without date filter."""
        from src.services.aggregation import get_aggregated_series

        session = AsyncMock()
        result = MagicMock()
        result.fetchall.return_value = SAMPLE_ROWS
        session.execute.return_value = result

        series = await get_aggregated_series(session, "dev1", "all")

        assert len(series) == 2
        session.execute.assert_awaited_once()

        # Verify SQL targets p1_monthly and has no date filter.
        executed_sql = str(
            session.execute.call_args[0][0].text,
        )
        assert "p1_monthly" in executed_sql
        assert "p1_samples" not in executed_sql
        assert ":start" not in executed_sql
        assert ":end" not in executed_sql

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
    async def test_day_frame_includes_date_filter(self) -> None:
        """frame=day includes bucket >= :start AND bucket < :end."""
        from src.services.aggregation import get_aggregated_series

        session = AsyncMock()
        result = MagicMock()
        result.fetchall.return_value = []
        session.execute.return_value = result

        await get_aggregated_series(session, "dev1", "day")

        executed_sql = str(
            session.execute.call_args[0][0].text,
        )
        assert "bucket >= :start" in executed_sql
        assert "bucket < :end" in executed_sql

    @pytest.mark.asyncio()
    async def test_all_frame_no_date_filter(self) -> None:
        """frame=all omits date range filter on bucket column."""
        from src.services.aggregation import get_aggregated_series

        session = AsyncMock()
        result = MagicMock()
        result.fetchall.return_value = []
        session.execute.return_value = result

        await get_aggregated_series(session, "dev1", "all")

        executed_sql = str(
            session.execute.call_args[0][0].text,
        )
        assert ":start" not in executed_sql
        assert ":end" not in executed_sql

    @pytest.mark.asyncio()
    async def test_month_rebucket_has_group_by(self) -> None:
        """frame=month uses GROUP BY for time_bucket re-aggregation."""
        from src.services.aggregation import get_aggregated_series

        session = AsyncMock()
        result = MagicMock()
        result.fetchall.return_value = []
        session.execute.return_value = result

        await get_aggregated_series(session, "dev1", "month")

        executed_sql = str(
            session.execute.call_args[0][0].text,
        )
        assert "GROUP BY bucket" in executed_sql

    @pytest.mark.asyncio()
    async def test_day_direct_query_no_group_by(self) -> None:
        """frame=day reads p1_hourly directly without GROUP BY."""
        from src.services.aggregation import get_aggregated_series

        session = AsyncMock()
        result = MagicMock()
        result.fetchall.return_value = []
        session.execute.return_value = result

        await get_aggregated_series(session, "dev1", "day")

        executed_sql = str(
            session.execute.call_args[0][0].text,
        )
        assert "GROUP BY" not in executed_sql


# ---------------------------------------------------------------------------
# FRAME_CONFIG structure tests
# ---------------------------------------------------------------------------


class TestFrameConfig:
    """Tests for FRAME_CONFIG structure after STORY-013 changes."""

    def test_frame_config_has_all_frames(self) -> None:
        """FRAME_CONFIG contains all four frame types."""
        from src.services.aggregation import FRAME_CONFIG

        assert set(FRAME_CONFIG.keys()) == {"day", "month", "year", "all"}

    def test_day_frame_uses_p1_hourly(self) -> None:
        """AC5: day frame queries p1_hourly continuous aggregate."""
        from src.services.aggregation import FRAME_CONFIG

        assert FRAME_CONFIG["day"]["view"] == "p1_hourly"
        assert FRAME_CONFIG["day"]["rebucket"] is None

    def test_month_frame_uses_p1_daily(self) -> None:
        """AC5: month frame queries p1_daily with 1-week rebucket."""
        from src.services.aggregation import FRAME_CONFIG

        assert FRAME_CONFIG["month"]["view"] == "p1_daily"
        assert FRAME_CONFIG["month"]["rebucket"] == "1 week"

    def test_year_frame_uses_p1_monthly(self) -> None:
        """AC5: year frame queries p1_monthly continuous aggregate."""
        from src.services.aggregation import FRAME_CONFIG

        assert FRAME_CONFIG["year"]["view"] == "p1_monthly"
        assert FRAME_CONFIG["year"]["rebucket"] is None

    def test_all_frame_uses_p1_monthly(self) -> None:
        """AC5: all frame queries p1_monthly continuous aggregate."""
        from src.services.aggregation import FRAME_CONFIG

        assert FRAME_CONFIG["all"]["view"] == "p1_monthly"
        assert FRAME_CONFIG["all"]["rebucket"] is None
        assert FRAME_CONFIG["all"]["range"] is None
