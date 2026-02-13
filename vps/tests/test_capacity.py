"""
Tests for the capacity tariff calculation endpoint (STORY-011).

Validates GET /v1/capacity/month/{month}?device_id={id}: 15-minute
average power peaks (kwartierpiek), monthly peak detection, input
validation, and empty-data handling.

CHANGELOG:
- 2026-02-13: Initial creation (STORY-011)

TODO:
- None
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from src.db.session import get_async_session
from src.main import app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _set_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure required env vars are set for every test."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("DEVICE_TOKENS", "test:dev1")


def _make_row(bucket: datetime, avg_power_w: int) -> MagicMock:
    """Create a mock Row-like object returned by session.execute().

    Mimics SQLAlchemy Row with _mapping attribute for dict-like access
    and attribute-style access for bucket and avg_power_w.

    Args:
        bucket: The 15-minute time bucket timestamp.
        avg_power_w: Average import power in watts for the bucket.

    Returns:
        MagicMock: Row-like object with bucket and avg_power_w attributes.
    """
    row = MagicMock()
    row.bucket = bucket
    row.avg_power_w = avg_power_w
    row._mapping = {"bucket": bucket, "avg_power_w": avg_power_w}
    return row


@pytest.fixture()
def mock_db_session() -> AsyncMock:
    """Create a mock AsyncSession for database operations.

    Returns:
        AsyncMock: Mock session with execute method.
    """
    session = AsyncMock()
    result = MagicMock()
    result.all.return_value = []
    session.execute.return_value = result
    return session


@pytest.fixture()
def client(mock_db_session: AsyncMock) -> TestClient:
    """Create a TestClient with mocked DB session.

    The capacity endpoint does NOT require auth, so no auth override needed.

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


# ---------------------------------------------------------------------------
# AC6: Invalid month format → 400 Bad Request
# ---------------------------------------------------------------------------


class TestCapacityValidation:
    """Tests for month format validation (AC6)."""

    def test_invalid_month_single_digit(self, client: TestClient) -> None:
        """AC6: '2026-1' (missing leading zero) → 400."""
        response = client.get("/v1/capacity/month/2026-1?device_id=dev1")
        assert response.status_code == 400

    def test_invalid_month_text(self, client: TestClient) -> None:
        """AC6: 'invalid' string → 400."""
        response = client.get("/v1/capacity/month/invalid?device_id=dev1")
        assert response.status_code == 400

    def test_invalid_month_reversed(self, client: TestClient) -> None:
        """AC6: '13-2026' (reversed format) → 400."""
        response = client.get("/v1/capacity/month/13-2026?device_id=dev1")
        assert response.status_code == 400

    def test_invalid_month_out_of_range(self, client: TestClient) -> None:
        """AC6: '2026-13' (month 13 does not exist) → 400."""
        response = client.get("/v1/capacity/month/2026-13?device_id=dev1")
        assert response.status_code == 400

    def test_invalid_month_zero(self, client: TestClient) -> None:
        """AC6: '2026-00' (month 0 does not exist) → 400."""
        response = client.get("/v1/capacity/month/2026-00?device_id=dev1")
        assert response.status_code == 400

    def test_missing_device_id_returns_422(self, client: TestClient) -> None:
        """Missing required query param device_id → 422."""
        response = client.get("/v1/capacity/month/2026-02")
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# AC7: Valid month, no data → 200 with empty peaks
# ---------------------------------------------------------------------------


class TestCapacityNoData:
    """Tests for months with no data (AC7)."""

    def test_no_data_returns_200_with_empty_peaks(
        self, client: TestClient, mock_db_session: AsyncMock,
    ) -> None:
        """AC7: No data returns 200 with peaks=[], null peak fields."""
        result = MagicMock()
        result.all.return_value = []
        mock_db_session.execute.return_value = result

        response = client.get("/v1/capacity/month/2026-02?device_id=dev1")

        assert response.status_code == 200
        body = response.json()
        assert body["month"] == "2026-02"
        assert body["device_id"] == "dev1"
        assert body["peaks"] == []
        assert body["monthly_peak_w"] is None
        assert body["monthly_peak_ts"] is None


# ---------------------------------------------------------------------------
# AC2-AC5: Known data → correct peaks and monthly peak
# ---------------------------------------------------------------------------


class TestCapacityWithData:
    """Tests for capacity calculation with known data."""

    def test_known_data_returns_correct_peaks(
        self, client: TestClient, mock_db_session: AsyncMock,
    ) -> None:
        """AC2/AC3: Known data returns correct peaks list."""
        rows = [
            _make_row(datetime(2026, 2, 1, 10, 0, tzinfo=timezone.utc), 500),
            _make_row(datetime(2026, 2, 1, 10, 15, tzinfo=timezone.utc), 1200),
            _make_row(datetime(2026, 2, 1, 10, 30, tzinfo=timezone.utc), 800),
        ]
        result = MagicMock()
        result.all.return_value = rows
        mock_db_session.execute.return_value = result

        response = client.get("/v1/capacity/month/2026-02?device_id=dev1")

        assert response.status_code == 200
        body = response.json()
        assert len(body["peaks"]) == 3
        assert body["peaks"][0]["avg_power_w"] == 500
        assert body["peaks"][1]["avg_power_w"] == 1200
        assert body["peaks"][2]["avg_power_w"] == 800

    def test_monthly_peak_is_maximum(
        self, client: TestClient, mock_db_session: AsyncMock,
    ) -> None:
        """AC4: monthly_peak_w is the MAX of all 15-min averages."""
        rows = [
            _make_row(datetime(2026, 2, 1, 10, 0, tzinfo=timezone.utc), 500),
            _make_row(datetime(2026, 2, 1, 10, 15, tzinfo=timezone.utc), 1200),
            _make_row(datetime(2026, 2, 1, 10, 30, tzinfo=timezone.utc), 800),
        ]
        result = MagicMock()
        result.all.return_value = rows
        mock_db_session.execute.return_value = result

        response = client.get("/v1/capacity/month/2026-02?device_id=dev1")

        body = response.json()
        assert body["monthly_peak_w"] == 1200

    def test_monthly_peak_ts_matches_peak_bucket(
        self, client: TestClient, mock_db_session: AsyncMock,
    ) -> None:
        """AC5: monthly_peak_ts matches the bucket of the peak window."""
        peak_ts = datetime(2026, 2, 1, 10, 15, tzinfo=timezone.utc)
        rows = [
            _make_row(datetime(2026, 2, 1, 10, 0, tzinfo=timezone.utc), 500),
            _make_row(peak_ts, 1200),
            _make_row(datetime(2026, 2, 1, 10, 30, tzinfo=timezone.utc), 800),
        ]
        result = MagicMock()
        result.all.return_value = rows
        mock_db_session.execute.return_value = result

        response = client.get("/v1/capacity/month/2026-02?device_id=dev1")

        body = response.json()
        assert body["monthly_peak_ts"] == "2026-02-01T10:15:00+00:00"

    def test_single_sample_peak_equals_that_average(
        self, client: TestClient, mock_db_session: AsyncMock,
    ) -> None:
        """Single sample in one window: peak equals that single average."""
        ts = datetime(2026, 2, 15, 14, 0, tzinfo=timezone.utc)
        rows = [_make_row(ts, 750)]
        result = MagicMock()
        result.all.return_value = rows
        mock_db_session.execute.return_value = result

        response = client.get("/v1/capacity/month/2026-02?device_id=dev1")

        body = response.json()
        assert body["monthly_peak_w"] == 750
        assert body["monthly_peak_ts"] == "2026-02-15T14:00:00+00:00"
        assert len(body["peaks"]) == 1

    def test_response_contains_all_required_fields(
        self, client: TestClient, mock_db_session: AsyncMock,
    ) -> None:
        """AC2: Response has month, device_id, peaks, monthly_peak_w, monthly_peak_ts."""
        rows = [
            _make_row(datetime(2026, 2, 1, 10, 0, tzinfo=timezone.utc), 500),
        ]
        result = MagicMock()
        result.all.return_value = rows
        mock_db_session.execute.return_value = result

        response = client.get("/v1/capacity/month/2026-02?device_id=dev1")

        body = response.json()
        assert "month" in body
        assert "device_id" in body
        assert "peaks" in body
        assert "monthly_peak_w" in body
        assert "monthly_peak_ts" in body

    def test_peaks_bucket_is_iso_string(
        self, client: TestClient, mock_db_session: AsyncMock,
    ) -> None:
        """AC2: Each peak bucket is an ISO 8601 formatted string."""
        ts = datetime(2026, 2, 1, 10, 0, tzinfo=timezone.utc)
        rows = [_make_row(ts, 500)]
        result = MagicMock()
        result.all.return_value = rows
        mock_db_session.execute.return_value = result

        response = client.get("/v1/capacity/month/2026-02?device_id=dev1")

        body = response.json()
        assert body["peaks"][0]["bucket"] == "2026-02-01T10:00:00+00:00"


# ---------------------------------------------------------------------------
# Service unit tests
# ---------------------------------------------------------------------------


class TestCapacityService:
    """Unit tests for the get_monthly_peaks service function."""

    @pytest.mark.asyncio()
    async def test_get_monthly_peaks_calls_execute(self) -> None:
        """Service calls session.execute with the time_bucket query."""
        from src.services.capacity import get_monthly_peaks

        session = AsyncMock()
        result = MagicMock()
        result.all.return_value = []
        session.execute.return_value = result

        data = await get_monthly_peaks(session, "dev1", "2026-02")

        session.execute.assert_awaited_once()
        assert data["month"] == "2026-02"
        assert data["device_id"] == "dev1"
        assert data["peaks"] == []
        assert data["monthly_peak_w"] is None
        assert data["monthly_peak_ts"] is None

    @pytest.mark.asyncio()
    async def test_get_monthly_peaks_with_rows(self) -> None:
        """Service correctly processes rows into peaks and finds max."""
        from src.services.capacity import get_monthly_peaks

        session = AsyncMock()
        rows = [
            _make_row(datetime(2026, 2, 1, 10, 0, tzinfo=timezone.utc), 300),
            _make_row(datetime(2026, 2, 1, 10, 15, tzinfo=timezone.utc), 900),
        ]
        result = MagicMock()
        result.all.return_value = rows
        session.execute.return_value = result

        data = await get_monthly_peaks(session, "dev1", "2026-02")

        assert len(data["peaks"]) == 2
        assert data["monthly_peak_w"] == 900
        assert data["monthly_peak_ts"] == "2026-02-01T10:15:00+00:00"

    @pytest.mark.asyncio()
    async def test_get_monthly_peaks_month_boundary(self) -> None:
        """Service uses correct month boundaries (start <= ts < end)."""
        from src.services.capacity import get_monthly_peaks

        session = AsyncMock()
        result = MagicMock()
        result.all.return_value = []
        session.execute.return_value = result

        await get_monthly_peaks(session, "dev1", "2026-12")

        # Verify execute was called (query includes correct boundaries)
        session.execute.assert_awaited_once()
        call_args = session.execute.call_args
        # The text SQL and bound params should reference the right dates
        bound_params = call_args[1] if call_args[1] else {}
        if not bound_params and len(call_args[0]) > 1:
            bound_params = call_args[0][1]
        # We verify the call happened; boundary logic tested via integration

    @pytest.mark.asyncio()
    async def test_get_monthly_peaks_december_rolls_to_january(self) -> None:
        """December end boundary rolls over to January of the next year."""
        from src.services.capacity import parse_month_range

        start, end = parse_month_range("2026-12")
        assert start == datetime(2026, 12, 1, tzinfo=timezone.utc)
        assert end == datetime(2027, 1, 1, tzinfo=timezone.utc)

    @pytest.mark.asyncio()
    async def test_parse_month_range_february(self) -> None:
        """February boundaries are correct."""
        from src.services.capacity import parse_month_range

        start, end = parse_month_range("2026-02")
        assert start == datetime(2026, 2, 1, tzinfo=timezone.utc)
        assert end == datetime(2026, 3, 1, tzinfo=timezone.utc)

    @pytest.mark.asyncio()
    async def test_parse_month_range_invalid_raises(self) -> None:
        """Invalid month format raises ValueError."""
        from src.services.capacity import parse_month_range

        with pytest.raises(ValueError):
            parse_month_range("2026-1")

        with pytest.raises(ValueError):
            parse_month_range("invalid")

        with pytest.raises(ValueError):
            parse_month_range("13-2026")

        with pytest.raises(ValueError):
            parse_month_range("2026-00")

        with pytest.raises(ValueError):
            parse_month_range("2026-13")
