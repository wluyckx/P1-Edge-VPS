"""
Tests for the health endpoint and application configuration.

CHANGELOG:
- 2026-02-13: Initial creation (STORY-006)

TODO:
- None
"""

from fastapi.testclient import TestClient
from src.main import app


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
