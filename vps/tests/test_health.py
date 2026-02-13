"""
Tests for the health endpoints and application configuration.

CHANGELOG:
- 2026-02-13: Initial creation (STORY-006)
- 2026-02-13: Add /health endpoint tests for DB and Redis probes (STORY-014)

TODO:
- None
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from src.main import app


# ===========================================================================
# Existing tests for GET /
# ===========================================================================


def test_health_returns_200():
    """GET / returns 200 status code."""
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200


def test_health_returns_json_with_status():
    """GET / returns JSON body with 'status' key."""
    client = TestClient(app)
    response = client.get("/")
    data = response.json()
    assert "status" in data
    assert data["status"] == "ok"


def test_config_loads_from_env(monkeypatch):
    """Settings loads values from environment variables."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/testdb")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("DEVICE_TOKENS", "token1:device-1")
    monkeypatch.setenv("CACHE_TTL_S", "10")

    from src.config import Settings

    settings = Settings()
    assert settings.DATABASE_URL == "postgresql+asyncpg://user:pass@localhost/testdb"
    assert settings.REDIS_URL == "redis://localhost:6379/0"
    assert settings.DEVICE_TOKENS == "token1:device-1"
    assert settings.CACHE_TTL_S == 10


def test_config_default_cache_ttl(monkeypatch):
    """CACHE_TTL_S defaults to 5 when not set."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/testdb")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("DEVICE_TOKENS", "token1:device-1")
    monkeypatch.delenv("CACHE_TTL_S", raising=False)

    from src.config import Settings

    settings = Settings()
    assert settings.CACHE_TTL_S == 5


# ===========================================================================
# STORY-014: GET /health — rich health check with DB + Redis probes
# ===========================================================================


@pytest.fixture(autouse=True)
def _env_vars(monkeypatch):
    """Set required env vars for Settings to load during app startup."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("DEVICE_TOKENS", "tok1:dev-1")


class TestHealthEndpointAllOk:
    """GET /health returns 200 with status=ok when DB and Redis are healthy."""

    @patch("src.api.health._check_redis", new_callable=AsyncMock, return_value="ok")
    @patch("src.api.health._check_db", new_callable=AsyncMock, return_value="ok")
    def test_returns_200(self, mock_db, mock_redis):
        """AC1: Returns HTTP 200 when all components are ok."""
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200

    @patch("src.api.health._check_redis", new_callable=AsyncMock, return_value="ok")
    @patch("src.api.health._check_db", new_callable=AsyncMock, return_value="ok")
    def test_status_ok(self, mock_db, mock_redis):
        """AC1: Response body has status=ok when all components healthy."""
        client = TestClient(app)
        data = client.get("/health").json()
        assert data["status"] == "ok"
        assert data["db"] == "ok"
        assert data["redis"] == "ok"


class TestHealthEndpointDbDown:
    """GET /health returns 503 with status=degraded when DB is down."""

    @patch("src.api.health._check_redis", new_callable=AsyncMock, return_value="ok")
    @patch(
        "src.api.health._check_db", new_callable=AsyncMock, return_value="error"
    )
    def test_returns_503(self, mock_db, mock_redis):
        """AC1: Returns HTTP 503 when DB probe fails."""
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 503

    @patch("src.api.health._check_redis", new_callable=AsyncMock, return_value="ok")
    @patch(
        "src.api.health._check_db", new_callable=AsyncMock, return_value="error"
    )
    def test_status_degraded_db_error(self, mock_db, mock_redis):
        """AC1: Response shows db=error and status=degraded."""
        client = TestClient(app)
        data = client.get("/health").json()
        assert data["status"] == "degraded"
        assert data["db"] == "error"
        assert data["redis"] == "ok"


class TestHealthEndpointRedisDown:
    """GET /health returns 503 with status=degraded when Redis is down."""

    @patch(
        "src.api.health._check_redis",
        new_callable=AsyncMock,
        return_value="error",
    )
    @patch("src.api.health._check_db", new_callable=AsyncMock, return_value="ok")
    def test_returns_503(self, mock_db, mock_redis):
        """AC1: Returns HTTP 503 when Redis probe fails."""
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 503

    @patch(
        "src.api.health._check_redis",
        new_callable=AsyncMock,
        return_value="error",
    )
    @patch("src.api.health._check_db", new_callable=AsyncMock, return_value="ok")
    def test_status_degraded_redis_error(self, mock_db, mock_redis):
        """AC1: Response shows redis=error and status=degraded."""
        client = TestClient(app)
        data = client.get("/health").json()
        assert data["status"] == "degraded"
        assert data["db"] == "ok"
        assert data["redis"] == "error"


class TestHealthEndpointAllDown:
    """GET /health returns 503 with status=degraded when both are down."""

    @patch(
        "src.api.health._check_redis",
        new_callable=AsyncMock,
        return_value="error",
    )
    @patch(
        "src.api.health._check_db", new_callable=AsyncMock, return_value="error"
    )
    def test_returns_503(self, mock_db, mock_redis):
        """AC1: Returns HTTP 503 when both DB and Redis are down."""
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 503

    @patch(
        "src.api.health._check_redis",
        new_callable=AsyncMock,
        return_value="error",
    )
    @patch(
        "src.api.health._check_db", new_callable=AsyncMock, return_value="error"
    )
    def test_both_degraded(self, mock_db, mock_redis):
        """AC1: Response shows both db=error and redis=error."""
        client = TestClient(app)
        data = client.get("/health").json()
        assert data["status"] == "degraded"
        assert data["db"] == "error"
        assert data["redis"] == "error"


class TestHealthDbProbe:
    """Unit tests for the _check_db helper function."""

    @pytest.mark.asyncio()
    async def test_db_ok(self):
        """_check_db returns 'ok' when SELECT 1 succeeds."""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()

        async def fake_get_session():
            yield mock_session

        with patch("src.api.health.get_async_session", fake_get_session):
            from src.api.health import _check_db

            result = await _check_db()
        assert result == "ok"

    @pytest.mark.asyncio()
    async def test_db_error(self):
        """_check_db returns 'error' when the session raises."""

        async def failing_get_session():
            raise ConnectionError("DB unreachable")
            yield  # noqa: RET503 — makes it an async generator

        with patch("src.api.health.get_async_session", failing_get_session):
            from src.api.health import _check_db

            result = await _check_db()
        assert result == "error"


class TestHealthRedisProbe:
    """Unit tests for the _check_redis helper function."""

    @pytest.mark.asyncio()
    async def test_redis_ok(self):
        """_check_redis returns 'ok' when PING succeeds."""
        mock_client = AsyncMock()
        mock_client.ping = AsyncMock(return_value=True)
        mock_client.aclose = AsyncMock()

        with patch(
            "src.api.health.get_redis",
            new_callable=AsyncMock,
            return_value=mock_client,
        ):
            from src.api.health import _check_redis

            result = await _check_redis()
        assert result == "ok"

    @pytest.mark.asyncio()
    async def test_redis_error(self):
        """_check_redis returns 'error' when get_redis raises."""
        with patch(
            "src.api.health.get_redis",
            new_callable=AsyncMock,
            side_effect=ConnectionError("Redis down"),
        ):
            from src.api.health import _check_redis

            result = await _check_redis()
        assert result == "error"
