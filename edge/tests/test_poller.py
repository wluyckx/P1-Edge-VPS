"""
Unit tests for HomeWizard P1 poller (STORY-002).

Tests verify:
- Successful poll returns parsed measurement dict from /api/measurement.
- Connection errors return None without raising (poll loop never crashes).
- HTTP error responses (4xx, 5xx) return None without raising.
- Timeout errors return None without raising.
- Bearer token is sent in the Authorization header.
- Configurable timeout is passed to httpx.

CHANGELOG:
- 2026-02-13: Initial creation (STORY-002)

TODO:
- None
"""

import json
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest
from edge.src.poller import poll_measurement

# ---------------------------------------------------------------------------
# Fixture data
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture()
def hw_responses() -> dict:
    """Load HomeWizard fixture responses from JSON file."""
    fixture_path = FIXTURES_DIR / "hw_responses.json"
    return json.loads(fixture_path.read_text())


@pytest.fixture()
def success_response(hw_responses: dict) -> dict:
    """The successful measurement fixture."""
    return hw_responses["success_measurement"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HOST = "192.168.1.100"
_TOKEN = "test-bearer-token"
_EXPECTED_URL = f"http://{_HOST}/api/measurement"


def _mock_response(
    *, status_code: int = 200, json_data: dict | None = None
) -> MagicMock:
    """Build a mock httpx.Response with the given status and optional JSON."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data
    # raise_for_status raises on 4xx/5xx
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            message=f"HTTP {status_code}",
            request=MagicMock(),
            response=resp,
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


# ===========================================================================
# AC1 + AC2: Successful poll returns parsed dict
# ===========================================================================


class TestPollMeasurementSuccess:
    """Successful HTTP 200 responses are parsed and returned."""

    def test_returns_parsed_json_on_200(self, success_response: dict) -> None:
        """poll_measurement returns parsed dict when API returns 200 OK."""
        mock_resp = _mock_response(status_code=200, json_data=success_response)

        with patch("edge.src.poller.httpx.Client") as MockClient:
            client_instance = MockClient.return_value.__enter__.return_value
            client_instance.get.return_value = mock_resp

            result = poll_measurement(host=_HOST, token=_TOKEN)

        assert result == success_response
        assert result["power_w"] == 450
        assert result["energy_import_kwh"] == 1234.567

    def test_sends_bearer_token_header(self, success_response: dict) -> None:
        """poll_measurement sends Authorization: Bearer {token} header."""
        mock_resp = _mock_response(status_code=200, json_data=success_response)

        with patch("edge.src.poller.httpx.Client") as MockClient:
            client_instance = MockClient.return_value.__enter__.return_value
            client_instance.get.return_value = mock_resp

            poll_measurement(host=_HOST, token=_TOKEN)

        client_instance.get.assert_called_once_with(
            _EXPECTED_URL,
            headers={"Authorization": f"Bearer {_TOKEN}"},
        )

    def test_sends_request_to_correct_url(self, success_response: dict) -> None:
        """poll_measurement targets http://{host}/api/measurement."""
        mock_resp = _mock_response(status_code=200, json_data=success_response)

        with patch("edge.src.poller.httpx.Client") as MockClient:
            client_instance = MockClient.return_value.__enter__.return_value
            client_instance.get.return_value = mock_resp

            poll_measurement(host="10.0.0.50", token="other-token")

        call_args = client_instance.get.call_args
        assert call_args[0][0] == "http://10.0.0.50/api/measurement"

    def test_zero_power_response(self, hw_responses: dict) -> None:
        """Zero-power reading is returned correctly (not treated as falsy)."""
        data = hw_responses["zero_power_measurement"]
        mock_resp = _mock_response(status_code=200, json_data=data)

        with patch("edge.src.poller.httpx.Client") as MockClient:
            client_instance = MockClient.return_value.__enter__.return_value
            client_instance.get.return_value = mock_resp

            result = poll_measurement(host=_HOST, token=_TOKEN)

        assert result is not None
        assert result["power_w"] == 0

    def test_negative_power_response(self, hw_responses: dict) -> None:
        """Negative power (solar export) is returned correctly."""
        data = hw_responses["negative_power_measurement"]
        mock_resp = _mock_response(status_code=200, json_data=data)

        with patch("edge.src.poller.httpx.Client") as MockClient:
            client_instance = MockClient.return_value.__enter__.return_value
            client_instance.get.return_value = mock_resp

            result = poll_measurement(host=_HOST, token=_TOKEN)

        assert result is not None
        assert result["power_w"] == -200


# ===========================================================================
# AC3: Connection error returns None, logs warning
# ===========================================================================


class TestPollMeasurementConnectionError:
    """Network/connection errors return None and log a warning."""

    def test_connection_error_returns_none(self) -> None:
        """ConnectError from httpx returns None (poll loop does not crash)."""
        with patch("edge.src.poller.httpx.Client") as MockClient:
            client_instance = MockClient.return_value.__enter__.return_value
            client_instance.get.side_effect = httpx.ConnectError("Connection refused")

            result = poll_measurement(host=_HOST, token=_TOKEN)

        assert result is None

    def test_connection_error_logs_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """ConnectError is logged at WARNING level."""
        with patch("edge.src.poller.httpx.Client") as MockClient:
            client_instance = MockClient.return_value.__enter__.return_value
            client_instance.get.side_effect = httpx.ConnectError("Connection refused")

            with caplog.at_level(logging.WARNING, logger="edge.src.poller"):
                poll_measurement(host=_HOST, token=_TOKEN)

        assert len(caplog.records) >= 1
        assert caplog.records[0].levelno == logging.WARNING
        assert (
            "Connection refused" in caplog.text or "connection" in caplog.text.lower()
        )


# ===========================================================================
# AC4: HTTP error status returns None, logs warning
# ===========================================================================


class TestPollMeasurementHttpError:
    """HTTP 4xx/5xx responses return None and log a warning."""

    def test_http_500_returns_none(self) -> None:
        """HTTP 500 Internal Server Error returns None."""
        mock_resp = _mock_response(status_code=500)

        with patch("edge.src.poller.httpx.Client") as MockClient:
            client_instance = MockClient.return_value.__enter__.return_value
            client_instance.get.return_value = mock_resp

            result = poll_measurement(host=_HOST, token=_TOKEN)

        assert result is None

    def test_http_500_logs_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """HTTP 500 is logged at WARNING level."""
        mock_resp = _mock_response(status_code=500)

        with patch("edge.src.poller.httpx.Client") as MockClient:
            client_instance = MockClient.return_value.__enter__.return_value
            client_instance.get.return_value = mock_resp

            with caplog.at_level(logging.WARNING, logger="edge.src.poller"):
                poll_measurement(host=_HOST, token=_TOKEN)

        assert len(caplog.records) >= 1
        assert caplog.records[0].levelno == logging.WARNING

    def test_http_401_returns_none(self) -> None:
        """HTTP 401 Unauthorized returns None (bad token)."""
        mock_resp = _mock_response(status_code=401)

        with patch("edge.src.poller.httpx.Client") as MockClient:
            client_instance = MockClient.return_value.__enter__.return_value
            client_instance.get.return_value = mock_resp

            result = poll_measurement(host=_HOST, token=_TOKEN)

        assert result is None

    def test_http_403_returns_none(self) -> None:
        """HTTP 403 Forbidden returns None."""
        mock_resp = _mock_response(status_code=403)

        with patch("edge.src.poller.httpx.Client") as MockClient:
            client_instance = MockClient.return_value.__enter__.return_value
            client_instance.get.return_value = mock_resp

            result = poll_measurement(host=_HOST, token=_TOKEN)

        assert result is None


# ===========================================================================
# AC5: Timeout returns None, logs warning; timeout is configurable
# ===========================================================================


class TestPollMeasurementTimeout:
    """Timeout errors return None and log a warning."""

    def test_timeout_returns_none(self) -> None:
        """httpx.TimeoutException returns None (poll loop does not crash)."""
        with patch("edge.src.poller.httpx.Client") as MockClient:
            client_instance = MockClient.return_value.__enter__.return_value
            client_instance.get.side_effect = httpx.TimeoutException("Read timed out")

            result = poll_measurement(host=_HOST, token=_TOKEN)

        assert result is None

    def test_timeout_logs_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """Timeout is logged at WARNING level."""
        with patch("edge.src.poller.httpx.Client") as MockClient:
            client_instance = MockClient.return_value.__enter__.return_value
            client_instance.get.side_effect = httpx.TimeoutException("Read timed out")

            with caplog.at_level(logging.WARNING, logger="edge.src.poller"):
                poll_measurement(host=_HOST, token=_TOKEN)

        assert len(caplog.records) >= 1
        assert caplog.records[0].levelno == logging.WARNING

    def test_default_timeout_is_5_seconds(self, success_response: dict) -> None:
        """Default timeout passed to httpx.Client is 5 seconds."""
        mock_resp = _mock_response(status_code=200, json_data=success_response)

        with patch("edge.src.poller.httpx.Client") as MockClient:
            client_instance = MockClient.return_value.__enter__.return_value
            client_instance.get.return_value = mock_resp

            poll_measurement(host=_HOST, token=_TOKEN)

        MockClient.assert_called_once_with(timeout=5.0)

    def test_custom_timeout(self, success_response: dict) -> None:
        """Custom timeout value is forwarded to httpx.Client."""
        mock_resp = _mock_response(status_code=200, json_data=success_response)

        with patch("edge.src.poller.httpx.Client") as MockClient:
            client_instance = MockClient.return_value.__enter__.return_value
            client_instance.get.return_value = mock_resp

            poll_measurement(host=_HOST, token=_TOKEN, timeout=10.0)

        MockClient.assert_called_once_with(timeout=10.0)
