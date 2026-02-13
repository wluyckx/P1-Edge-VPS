"""
Tests for Bearer token authentication (STORY-008).

Validates that the auth dependency correctly authenticates devices using
Bearer tokens from the Authorization header, with tokens parsed from the
DEVICE_TOKENS environment variable.

CHANGELOG:
- 2026-02-13: Initial creation (STORY-008)

TODO:
- None
"""

from unittest.mock import patch

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from src.auth.bearer import (
    BearerAuth,
    parse_device_tokens,
    verify_bearer_token,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VALID_TOKENS = "tokenA:device-1,tokenB:device-2"


@pytest.fixture(autouse=True)
def _set_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure required env vars are set for every test."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("DEVICE_TOKENS", VALID_TOKENS)


def _make_test_app(token_map: dict[str, str]) -> FastAPI:
    """Create a minimal FastAPI app with a protected test endpoint.

    Args:
        token_map: Mapping of token -> device_id.

    Returns:
        FastAPI: Application with a single protected GET /protected endpoint.
    """
    test_app = FastAPI()
    auth = BearerAuth(token_map)

    @test_app.get("/protected")
    async def protected(device_id: str = Depends(auth.verify)) -> dict:
        return {"device_id": device_id}

    return test_app


# ---------------------------------------------------------------------------
# Tests for parse_device_tokens()
# ---------------------------------------------------------------------------


class TestParseDeviceTokens:
    """Tests for the token string parser."""

    def test_single_token(self) -> None:
        """Single token:device pair is parsed correctly."""
        result = parse_device_tokens("abc123:device-1")
        assert result == {"abc123": "device-1"}

    def test_multiple_tokens(self) -> None:
        """Multiple comma-separated pairs are parsed correctly."""
        result = parse_device_tokens("tokenA:device-1,tokenB:device-2")
        assert result == {"tokenA": "device-1", "tokenB": "device-2"}

    def test_empty_string_returns_empty_dict(self) -> None:
        """Empty string produces an empty dict."""
        result = parse_device_tokens("")
        assert result == {}

    def test_whitespace_is_stripped(self) -> None:
        """Leading/trailing whitespace in tokens and device IDs is stripped."""
        result = parse_device_tokens(" tokenA : device-1 , tokenB : device-2 ")
        assert result == {"tokenA": "device-1", "tokenB": "device-2"}

    def test_malformed_entry_without_colon_is_skipped(self) -> None:
        """Entries without a colon separator are silently skipped."""
        result = parse_device_tokens("tokenA:device-1,badentry,tokenB:device-2")
        assert result == {"tokenA": "device-1", "tokenB": "device-2"}


# ---------------------------------------------------------------------------
# Tests for BearerAuth.verify (the FastAPI dependency)
# ---------------------------------------------------------------------------


class TestBearerAuthVerify:
    """Tests for the verify dependency used with FastAPI Depends()."""

    def test_valid_token_returns_device_id(self) -> None:
        """AC2: Valid token returns associated device_id."""
        token_map = {"tokenA": "device-1", "tokenB": "device-2"}
        app = _make_test_app(token_map)
        client = TestClient(app)

        response = client.get("/protected", headers={"Authorization": "Bearer tokenA"})

        assert response.status_code == 200
        assert response.json() == {"device_id": "device-1"}

    def test_valid_token_second_device(self) -> None:
        """Valid second token returns its associated device_id."""
        token_map = {"tokenA": "device-1", "tokenB": "device-2"}
        app = _make_test_app(token_map)
        client = TestClient(app)

        response = client.get("/protected", headers={"Authorization": "Bearer tokenB"})

        assert response.status_code == 200
        assert response.json() == {"device_id": "device-2"}

    def test_invalid_token_returns_401(self) -> None:
        """AC3: Invalid token returns 401 with JSON error body."""
        token_map = {"tokenA": "device-1"}
        app = _make_test_app(token_map)
        client = TestClient(app)

        response = client.get("/protected", headers={"Authorization": "Bearer wrong-token"})

        assert response.status_code == 401
        assert "detail" in response.json()

    def test_missing_authorization_header_returns_401(self) -> None:
        """AC4: Missing Authorization header returns 401."""
        token_map = {"tokenA": "device-1"}
        app = _make_test_app(token_map)
        client = TestClient(app)

        response = client.get("/protected")

        assert response.status_code == 401

    def test_malformed_header_no_bearer_prefix_returns_401(self) -> None:
        """Malformed header without 'Bearer ' prefix returns 401/403."""
        token_map = {"tokenA": "device-1"}
        app = _make_test_app(token_map)
        client = TestClient(app)

        response = client.get("/protected", headers={"Authorization": "Basic tokenA"})

        assert response.status_code == 401

    def test_empty_token_string_returns_401(self) -> None:
        """Empty token string after 'Bearer ' returns 401."""
        token_map = {"tokenA": "device-1"}
        app = _make_test_app(token_map)
        client = TestClient(app)

        response = client.get("/protected", headers={"Authorization": "Bearer "})

        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Tests for verify_bearer_token() standalone function
# ---------------------------------------------------------------------------


class TestVerifyBearerTokenStandalone:
    """Tests for the standalone verify_bearer_token function."""

    def test_valid_token_returns_device_id(self) -> None:
        """AC1/AC2: Valid token returns device_id."""
        token_map = {"tokenA": "device-1", "tokenB": "device-2"}
        result = verify_bearer_token("tokenA", token_map)
        assert result == "device-1"

    def test_invalid_token_returns_none(self) -> None:
        """AC3: Invalid token returns None."""
        token_map = {"tokenA": "device-1"}
        result = verify_bearer_token("wrong-token", token_map)
        assert result is None

    def test_empty_token_returns_none(self) -> None:
        """Empty token string returns None."""
        token_map = {"tokenA": "device-1"}
        result = verify_bearer_token("", token_map)
        assert result is None

    def test_empty_token_map_returns_none(self) -> None:
        """Empty token map always returns None."""
        result = verify_bearer_token("tokenA", {})
        assert result is None


# ---------------------------------------------------------------------------
# Tests for constant-time comparison (AC7)
# ---------------------------------------------------------------------------


class TestConstantTimeComparison:
    """Ensure secrets.compare_digest is used for token comparison."""

    def test_uses_compare_digest(self) -> None:
        """AC7: Token comparison uses secrets.compare_digest."""
        token_map = {"tokenA": "device-1"}

        with patch("src.auth.bearer.secrets.compare_digest", return_value=True) as mock_cmp:
            result = verify_bearer_token("tokenA", token_map)

        mock_cmp.assert_called()
        assert result == "device-1"
