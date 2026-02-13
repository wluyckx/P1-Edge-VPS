"""
Tests for the realtime API endpoint (STORY-010).

Validates GET /v1/realtime?device_id={id}: Redis cache hit, cache miss with
DB data, cache miss with no data (404), response schema, and graceful Redis
failure handling.

CHANGELOG:
- 2026-02-13: Initial creation (STORY-010)

TODO:
- None
"""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from src.db.session import get_async_session
from src.main import app

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

DEVICE_ID = "dev1"
SAMPLE_TS = "2026-02-13T12:00:00+00:00"
SAMPLE_DICT = {
    "device_id": DEVICE_ID,
    "ts": SAMPLE_TS,
    "power_w": 450,
    "import_power_w": 450,
    "energy_import_kwh": 123.456,
    "energy_export_kwh": 78.9,
}
REQUIRED_FIELDS = {
    "device_id",
    "ts",
    "power_w",
    "import_power_w",
    "energy_import_kwh",
    "energy_export_kwh",
}


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
        AsyncMock: Mock session with execute method.
    """
    session = AsyncMock()
    return session


@pytest.fixture()
def client(mock_db_session: AsyncMock) -> TestClient:
    """Create a TestClient with mocked DB session (no auth needed for realtime).

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


def _make_db_row() -> MagicMock:
    """Create a mock DB row matching the P1Sample columns.

    Returns:
        MagicMock: Mock row with named attributes for all sample fields.
    """
    row = MagicMock()
    row.device_id = DEVICE_ID
    row.ts = datetime(2026, 2, 13, 12, 0, 0, tzinfo=timezone.utc)
    row.power_w = 450
    row.import_power_w = 450
    row.energy_import_kwh = 123.456
    row.energy_export_kwh = 78.9
    return row


# ---------------------------------------------------------------------------
# AC3: Cache hit -> return cached data, no DB query
# ---------------------------------------------------------------------------


class TestCacheHit:
    """Tests for Redis cache hit scenario."""

    def test_cache_hit_returns_cached_json_no_db_call(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
    ) -> None:
        """AC3: Cache hit returns cached JSON without querying the database."""
        cached_json = json.dumps(SAMPLE_DICT)
        mock_redis = AsyncMock()
        mock_redis.get.return_value = cached_json

        with patch(
            "src.api.realtime.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            response = client.get(f"/v1/realtime?device_id={DEVICE_ID}")

        assert response.status_code == 200
        assert response.json() == SAMPLE_DICT
        mock_db_session.execute.assert_not_awaited()

    def test_cache_hit_closes_redis_connection(
        self,
        client: TestClient,
    ) -> None:
        """Cache hit closes the Redis connection after use."""
        cached_json = json.dumps(SAMPLE_DICT)
        mock_redis = AsyncMock()
        mock_redis.get.return_value = cached_json

        with patch(
            "src.api.realtime.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            client.get(f"/v1/realtime?device_id={DEVICE_ID}")

        mock_redis.aclose.assert_awaited_once()


# ---------------------------------------------------------------------------
# AC4/AC5: Cache miss + DB has data -> query DB, cache result, return data
# ---------------------------------------------------------------------------


class TestCacheMissDbHit:
    """Tests for cache miss with data in the database."""

    def test_cache_miss_queries_db_and_returns_data(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
    ) -> None:
        """AC4: Cache miss queries the DB and returns the latest sample."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None  # cache miss

        db_row = _make_db_row()
        result_mock = MagicMock()
        result_mock.fetchone.return_value = db_row
        mock_db_session.execute.return_value = result_mock

        with patch(
            "src.api.realtime.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            response = client.get(f"/v1/realtime?device_id={DEVICE_ID}")

        assert response.status_code == 200
        body = response.json()
        assert body["device_id"] == DEVICE_ID
        assert body["power_w"] == 450
        assert body["import_power_w"] == 450
        assert body["energy_import_kwh"] == 123.456
        assert body["energy_export_kwh"] == 78.9
        mock_db_session.execute.assert_awaited_once()

    def test_cache_miss_caches_result_with_ttl(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
    ) -> None:
        """AC5: Cache miss caches the DB result with CACHE_TTL_S TTL."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None  # cache miss

        db_row = _make_db_row()
        result_mock = MagicMock()
        result_mock.fetchone.return_value = db_row
        mock_db_session.execute.return_value = result_mock

        with patch(
            "src.api.realtime.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            client.get(f"/v1/realtime?device_id={DEVICE_ID}")

        # Verify redis.set was called with the correct key and TTL
        mock_redis.set.assert_awaited_once()
        call_args = mock_redis.set.call_args
        assert call_args[0][0] == f"realtime:{DEVICE_ID}"
        # Verify TTL argument (ex= keyword)
        assert call_args.kwargs.get("ex") == 5  # default CACHE_TTL_S


# ---------------------------------------------------------------------------
# AC6: Cache miss + no DB data -> 404
# ---------------------------------------------------------------------------


class TestCacheMissNoData:
    """Tests for cache miss with no data in the database."""

    def test_no_data_returns_404(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
    ) -> None:
        """AC6: Unknown device_id (no DB data) returns 404 Not Found."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None  # cache miss

        result_mock = MagicMock()
        result_mock.fetchone.return_value = None  # no data
        mock_db_session.execute.return_value = result_mock

        with patch(
            "src.api.realtime.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            response = client.get(
                "/v1/realtime?device_id=unknown-device",
            )

        assert response.status_code == 404
        assert "no data found" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# AC2: Response includes all required fields
# ---------------------------------------------------------------------------


class TestResponseSchema:
    """Tests for response schema completeness."""

    def test_response_includes_all_required_fields(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
    ) -> None:
        """AC2: Response contains all required fields."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None  # cache miss

        db_row = _make_db_row()
        result_mock = MagicMock()
        result_mock.fetchone.return_value = db_row
        mock_db_session.execute.return_value = result_mock

        with patch(
            "src.api.realtime.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            response = client.get(f"/v1/realtime?device_id={DEVICE_ID}")

        assert response.status_code == 200
        body = response.json()
        assert set(body.keys()) == REQUIRED_FIELDS

    def test_response_from_cache_includes_all_required_fields(
        self,
        client: TestClient,
    ) -> None:
        """AC2: Cached response also contains all required fields."""
        cached_json = json.dumps(SAMPLE_DICT)
        mock_redis = AsyncMock()
        mock_redis.get.return_value = cached_json

        with patch(
            "src.api.realtime.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            response = client.get(f"/v1/realtime?device_id={DEVICE_ID}")

        assert response.status_code == 200
        body = response.json()
        assert set(body.keys()) == REQUIRED_FIELDS


# ---------------------------------------------------------------------------
# Graceful degradation: Redis failure doesn't break the endpoint
# ---------------------------------------------------------------------------


class TestRedisFailure:
    """Tests for graceful Redis failure handling."""

    def test_redis_get_failure_falls_through_to_db(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
    ) -> None:
        """Redis get() failure falls through to DB query and returns data."""
        mock_redis = AsyncMock()
        mock_redis.get.side_effect = ConnectionError("Redis unavailable")

        db_row = _make_db_row()
        result_mock = MagicMock()
        result_mock.fetchone.return_value = db_row
        mock_db_session.execute.return_value = result_mock

        with patch(
            "src.api.realtime.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            response = client.get(f"/v1/realtime?device_id={DEVICE_ID}")

        assert response.status_code == 200
        body = response.json()
        assert body["device_id"] == DEVICE_ID
        mock_db_session.execute.assert_awaited_once()

    def test_redis_set_failure_still_returns_data(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
    ) -> None:
        """Redis set() failure still returns data from DB successfully."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None  # cache miss
        mock_redis.set.side_effect = ConnectionError("Redis unavailable")

        db_row = _make_db_row()
        result_mock = MagicMock()
        result_mock.fetchone.return_value = db_row
        mock_db_session.execute.return_value = result_mock

        with patch(
            "src.api.realtime.get_redis",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ):
            response = client.get(f"/v1/realtime?device_id={DEVICE_ID}")

        assert response.status_code == 200
        body = response.json()
        assert body["device_id"] == DEVICE_ID

    def test_redis_connection_failure_falls_through_to_db(
        self,
        client: TestClient,
        mock_db_session: AsyncMock,
    ) -> None:
        """get_redis() failure falls through to DB query and returns data."""
        db_row = _make_db_row()
        result_mock = MagicMock()
        result_mock.fetchone.return_value = db_row
        mock_db_session.execute.return_value = result_mock

        with patch(
            "src.api.realtime.get_redis",
            new_callable=AsyncMock,
            side_effect=ConnectionError("Cannot connect to Redis"),
        ):
            response = client.get(f"/v1/realtime?device_id={DEVICE_ID}")

        assert response.status_code == 200
        body = response.json()
        assert body["device_id"] == DEVICE_ID


# ---------------------------------------------------------------------------
# Edge case: missing device_id query param
# ---------------------------------------------------------------------------


class TestMissingDeviceId:
    """Tests for missing device_id query parameter."""

    def test_missing_device_id_returns_422(self, client: TestClient) -> None:
        """Missing device_id query parameter returns 422."""
        response = client.get("/v1/realtime")
        assert response.status_code == 422
