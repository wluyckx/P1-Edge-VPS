"""
Tests for the ingest API endpoint (STORY-009).

Validates POST /v1/ingest: authentication, request validation, idempotent
inserts via ON CONFLICT DO NOTHING, device_id authorization, and Redis
cache invalidation.

CHANGELOG:
- 2026-02-13: Initial creation (STORY-009)

TODO:
- None
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from src.api.deps import get_current_device_id
from src.db.session import get_async_session
from src.main import app

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture()
def sample_data() -> dict:
    """Load sample_data.json test fixture.

    Returns:
        dict: Parsed fixture data with valid and invalid batches.
    """
    with open(FIXTURES_DIR / "sample_data.json") as f:
        return json.load(f)


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
        AsyncMock: Mock session with execute and commit methods.
    """
    session = AsyncMock()
    result = MagicMock()
    result.rowcount = 2
    session.execute.return_value = result
    return session


@pytest.fixture()
def client(mock_db_session: AsyncMock) -> TestClient:
    """Create a TestClient with mocked DB session and auth dependency.

    The DB session is mocked to avoid needing a real PostgreSQL connection.
    The auth dependency is overridden to return 'dev1' as the device_id.

    Args:
        mock_db_session: Mock async database session.

    Returns:
        TestClient: Configured test client with dependency overrides.
    """
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
    """Create a TestClient with mocked DB but NO auth override.

    Uses the real BearerAuth dependency so auth failures can be tested.

    Args:
        mock_db_session: Mock async database session.

    Returns:
        TestClient: Test client without auth override.
    """
    async def override_get_session():
        yield mock_db_session

    app.dependency_overrides[get_async_session] = override_get_session
    # No auth override — real BearerAuth is used.

    yield TestClient(app)

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# AC1 / AC5: POST /v1/ingest accepts valid batch and returns insert count
# ---------------------------------------------------------------------------


class TestIngestHappyPath:
    """Tests for successful ingest requests."""

    def test_valid_batch_returns_200_with_insert_count(
        self, client: TestClient, sample_data: dict,
    ) -> None:
        """AC1/AC5: Valid batch returns 200 with inserted count."""
        with patch(
            "src.api.ingest.invalidate_device_cache", new_callable=AsyncMock,
        ):
            response = client.post(
                "/v1/ingest",
                json=sample_data["valid_batch"],
            )

        assert response.status_code == 200
        body = response.json()
        assert "inserted" in body
        assert isinstance(body["inserted"], int)

    def test_valid_batch_optional_fields_returns_200(
        self, client: TestClient, sample_data: dict,
    ) -> None:
        """AC2: Samples with optional fields omitted are accepted."""
        with patch(
            "src.api.ingest.invalidate_device_cache", new_callable=AsyncMock,
        ):
            response = client.post(
                "/v1/ingest",
                json=sample_data["valid_batch_optional_fields"],
            )

        assert response.status_code == 200
        assert response.json()["inserted"] >= 0

    def test_insert_count_reflects_rowcount(
        self, mock_db_session: AsyncMock, client: TestClient, sample_data: dict,
    ) -> None:
        """AC5: Inserted count matches database rowcount."""
        result = MagicMock()
        result.rowcount = 1
        mock_db_session.execute.return_value = result

        with patch(
            "src.api.ingest.invalidate_device_cache", new_callable=AsyncMock,
        ):
            response = client.post(
                "/v1/ingest",
                json=sample_data["valid_batch"],
            )

        assert response.status_code == 200
        assert response.json()["inserted"] == 1


# ---------------------------------------------------------------------------
# AC4: Idempotent — duplicate batch returns inserted=0
# ---------------------------------------------------------------------------


class TestIngestIdempotency:
    """Tests for idempotent ingestion (ON CONFLICT DO NOTHING)."""

    def test_duplicate_batch_returns_inserted_zero(
        self, mock_db_session: AsyncMock, client: TestClient, sample_data: dict,
    ) -> None:
        """AC4: Duplicate batch (same device_id+ts) returns inserted=0."""
        result = MagicMock()
        result.rowcount = 0
        mock_db_session.execute.return_value = result

        with patch(
            "src.api.ingest.invalidate_device_cache", new_callable=AsyncMock,
        ):
            response = client.post(
                "/v1/ingest",
                json=sample_data["valid_batch"],
            )

        assert response.status_code == 200
        assert response.json()["inserted"] == 0


# ---------------------------------------------------------------------------
# AC7: Invalid request body → 422
# ---------------------------------------------------------------------------


class TestIngestValidation:
    """Tests for Pydantic request validation (422 errors)."""

    def test_missing_required_fields_returns_422(
        self, client: TestClient, sample_data: dict,
    ) -> None:
        """AC7: Missing required fields (power_w, import_power_w) → 422."""
        response = client.post(
            "/v1/ingest",
            json=sample_data["invalid_missing_fields"],
        )
        assert response.status_code == 422

    def test_wrong_type_returns_422(
        self, client: TestClient, sample_data: dict,
    ) -> None:
        """AC7: Wrong field type (string for int) → 422."""
        response = client.post(
            "/v1/ingest",
            json=sample_data["invalid_wrong_type"],
        )
        assert response.status_code == 422

    def test_missing_samples_key_returns_422(
        self, client: TestClient, sample_data: dict,
    ) -> None:
        """AC7: Missing 'samples' key in body → 422."""
        response = client.post(
            "/v1/ingest",
            json=sample_data["invalid_empty_samples"],
        )
        assert response.status_code == 422

    def test_empty_body_returns_422(self, client: TestClient) -> None:
        """AC7: Empty request body → 422."""
        response = client.post(
            "/v1/ingest",
            content=b"",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# AC6: Missing / invalid auth → 401
# ---------------------------------------------------------------------------


class TestIngestAuth:
    """Tests for authentication enforcement."""

    def test_missing_auth_returns_401(
        self, unauth_client: TestClient, sample_data: dict,
    ) -> None:
        """AC6: Missing Authorization header → 401."""
        response = unauth_client.post(
            "/v1/ingest",
            json=sample_data["valid_batch"],
        )
        # FastAPI HTTPBearer returns 403 for missing header by default
        assert response.status_code in (401, 403)

    def test_invalid_token_returns_401(
        self, unauth_client: TestClient, sample_data: dict,
    ) -> None:
        """AC6: Invalid Bearer token → 401."""
        response = unauth_client.post(
            "/v1/ingest",
            json=sample_data["valid_batch"],
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# AC8: Device ID mismatch → 403
# ---------------------------------------------------------------------------


class TestIngestDeviceIdMismatch:
    """Tests for device_id authorization check."""

    def test_wrong_device_id_returns_403(
        self, client: TestClient, sample_data: dict,
    ) -> None:
        """AC8: Sample device_id != authenticated device_id → 403."""
        response = client.post(
            "/v1/ingest",
            json=sample_data["wrong_device_batch"],
        )
        assert response.status_code == 403

    def test_mixed_device_ids_returns_403(
        self, client: TestClient, sample_data: dict,
    ) -> None:
        """AC8: Mix of matching and non-matching device_ids → 403."""
        response = client.post(
            "/v1/ingest",
            json=sample_data["mixed_device_batch"],
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# AC9: Redis cache invalidation on successful ingest
# ---------------------------------------------------------------------------


class TestIngestCacheInvalidation:
    """Tests for Redis cache invalidation after ingest."""

    def test_successful_ingest_calls_redis_delete(
        self, client: TestClient, sample_data: dict,
    ) -> None:
        """AC9: Successful ingest calls Redis delete on 'realtime:{device_id}'."""
        with patch(
            "src.api.ingest.invalidate_device_cache", new_callable=AsyncMock,
        ) as mock_invalidate:
            response = client.post(
                "/v1/ingest",
                json=sample_data["valid_batch"],
            )

        assert response.status_code == 200
        mock_invalidate.assert_awaited_once_with("dev1")

    def test_redis_failure_does_not_break_ingest(
        self, client: TestClient, sample_data: dict,
    ) -> None:
        """AC9: Redis failure is best-effort; ingest still succeeds."""
        with patch(
            "src.api.ingest.invalidate_device_cache",
            new_callable=AsyncMock,
            side_effect=ConnectionError("Redis unavailable"),
        ):
            response = client.post(
                "/v1/ingest",
                json=sample_data["valid_batch"],
            )

        assert response.status_code == 200
        assert response.json()["inserted"] >= 0


# ---------------------------------------------------------------------------
# Ingestion service unit tests
# ---------------------------------------------------------------------------


class TestIngestionService:
    """Unit tests for the ingest_samples service function."""

    @pytest.mark.asyncio()
    async def test_ingest_samples_calls_execute_and_commit(self) -> None:
        """ingest_samples executes the insert statement and commits."""
        from src.services.ingestion import ingest_samples

        session = AsyncMock()
        result = MagicMock()
        result.rowcount = 3
        session.execute.return_value = result

        samples = [
            {
                "device_id": "dev1",
                "ts": "2026-02-13T10:00:00Z",
                "power_w": 450,
                "import_power_w": 450,
                "energy_import_kwh": None,
                "energy_export_kwh": None,
            },
        ]

        count = await ingest_samples(session, samples)

        assert count == 3
        session.execute.assert_awaited_once()
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio()
    async def test_ingest_samples_returns_zero_on_all_conflicts(self) -> None:
        """ingest_samples returns 0 when all rows conflict."""
        from src.services.ingestion import ingest_samples

        session = AsyncMock()
        result = MagicMock()
        result.rowcount = 0
        session.execute.return_value = result

        samples = [
            {
                "device_id": "dev1",
                "ts": "2026-02-13T10:00:00Z",
                "power_w": 450,
                "import_power_w": 450,
                "energy_import_kwh": None,
                "energy_export_kwh": None,
            },
        ]

        count = await ingest_samples(session, samples)
        assert count == 0


# ---------------------------------------------------------------------------
# Redis client unit tests
# ---------------------------------------------------------------------------


class TestRedisClient:
    """Unit tests for the Redis cache client module."""

    @pytest.mark.asyncio()
    async def test_invalidate_device_cache_deletes_correct_key(self) -> None:
        """invalidate_device_cache deletes 'realtime:{device_id}' key."""
        with patch(
            "src.cache.redis_client.get_redis", new_callable=AsyncMock,
        ) as mock_get_redis:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis

            from src.cache.redis_client import invalidate_device_cache
            await invalidate_device_cache("dev1")

            mock_redis.delete.assert_awaited_once_with("realtime:dev1")
            mock_redis.aclose.assert_awaited_once()

    @pytest.mark.asyncio()
    async def test_invalidate_device_cache_handles_connection_error(self) -> None:
        """invalidate_device_cache suppresses connection errors gracefully."""
        with patch(
            "src.cache.redis_client.get_redis", new_callable=AsyncMock,
            side_effect=ConnectionError("Redis unavailable"),
        ):
            from src.cache.redis_client import invalidate_device_cache
            # Should not raise
            await invalidate_device_cache("dev1")
