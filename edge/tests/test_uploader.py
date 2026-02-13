"""
Unit tests for the batch uploader with exponential backoff retry (STORY-005).

Tests verify:
- AC1: Reads batch from spool via peek(batch_size).
- AC2: POSTs batch as JSON to {VPS_INGEST_URL}/v1/ingest with Bearer token.
- AC3: On 2xx response: acks the uploaded rowids from spool.
- AC4: On failure (network error, non-2xx): does NOT ack.
- AC5: Exponential backoff: 1s -> 2s -> 4s -> 8s -> ... -> max 300s.
- AC6: Backoff resets to 1s on successful upload.
- AC7: Validates VPS_INGEST_URL is HTTPS at startup; rejects HTTP (HC-003).
- AC8: TLS certificate verification enabled (verify=True).
- AC9: Empty spool: upload cycle is a no-op (no HTTP request).

CHANGELOG:
- 2026-02-13: Initial creation (STORY-005)

TODO:
- None
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest
from edge.src.uploader import Uploader

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_INGEST_URL = "https://vps.example.com"
_DEVICE_TOKEN = "test-device-token"
_BATCH_SIZE = 30


def _make_spool_rows(count: int = 3) -> list[dict]:
    """Return a list of fake spool rows with rowids and sample data."""
    return [
        {
            "rowid": i + 1,
            "device_id": "hw-p1-001",
            "ts": f"2026-02-13T10:00:0{i}Z",
            "power_w": 1500 + i * 10,
            "import_power_w": 1500 + i * 10,
            "energy_import_kwh": 123.456 + i,
            "energy_export_kwh": 78.9 + i,
            "created_at": "2026-02-13T10:00:00",
        }
        for i in range(count)
    ]


def _mock_response(*, status_code: int = 200) -> MagicMock:
    """Build a mock httpx.Response with the given status code."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.is_success = 200 <= status_code < 300
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            message=f"HTTP {status_code}",
            request=MagicMock(),
            response=resp,
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


def _make_uploader(
    spool: MagicMock,
    *,
    ingest_url: str = _INGEST_URL,
    device_token: str = _DEVICE_TOKEN,
    batch_size: int = _BATCH_SIZE,
    max_backoff: float = 300.0,
) -> Uploader:
    """Create an Uploader with a mocked httpx.Client."""
    with patch("edge.src.uploader.httpx.Client"):
        return Uploader(
            spool=spool,
            ingest_url=ingest_url,
            device_token=device_token,
            batch_size=batch_size,
            max_backoff=max_backoff,
        )


# ===========================================================================
# AC7: HTTPS validation at init (HC-003)
# ===========================================================================


class TestHttpsValidation:
    """Uploader rejects non-HTTPS ingest URLs at construction time."""

    def test_http_url_raises_value_error(self) -> None:
        """AC7: http:// scheme raises ValueError."""
        spool = MagicMock()
        with pytest.raises(ValueError, match="HTTPS"):
            Uploader(
                spool=spool,
                ingest_url="http://vps.example.com",
                device_token=_DEVICE_TOKEN,
            )

    def test_https_url_accepted(self) -> None:
        """AC7: https:// scheme is accepted without error."""
        spool = MagicMock()
        uploader = _make_uploader(spool, ingest_url="https://vps.example.com")
        assert uploader is not None

    def test_ftp_url_raises_value_error(self) -> None:
        """AC7: Non-HTTPS schemes like ftp:// are rejected."""
        spool = MagicMock()
        with pytest.raises(ValueError, match="HTTPS"):
            Uploader(
                spool=spool,
                ingest_url="ftp://vps.example.com",
                device_token=_DEVICE_TOKEN,
            )


# ===========================================================================
# AC8: TLS certificate verification enabled
# ===========================================================================


class TestTlsVerification:
    """Uploader creates httpx.Client with verify=True."""

    def test_client_created_with_verify_true(self) -> None:
        """AC8: httpx.Client is instantiated with verify=True."""
        spool = MagicMock()
        with patch("edge.src.uploader.httpx.Client") as MockClient:
            Uploader(
                spool=spool,
                ingest_url=_INGEST_URL,
                device_token=_DEVICE_TOKEN,
            )
        MockClient.assert_called_once_with(verify=True)


# ===========================================================================
# AC9: Empty spool is a no-op
# ===========================================================================


class TestEmptySpool:
    """Empty spool means no HTTP request is made."""

    def test_empty_spool_returns_false(self) -> None:
        """AC9: upload_batch returns False when spool is empty."""
        spool = MagicMock()
        spool.peek.return_value = []

        uploader = _make_uploader(spool)
        result = uploader.upload_batch()

        assert result is False

    def test_empty_spool_no_http_request(self) -> None:
        """AC9: No HTTP POST is made when spool is empty."""
        spool = MagicMock()
        spool.peek.return_value = []

        uploader = _make_uploader(spool)

        with patch.object(uploader, "_client") as mock_client:
            uploader.upload_batch()
            mock_client.post.assert_not_called()

    def test_empty_spool_no_ack(self) -> None:
        """AC9: No ack is called when spool is empty."""
        spool = MagicMock()
        spool.peek.return_value = []

        uploader = _make_uploader(spool)
        uploader.upload_batch()

        spool.ack.assert_not_called()


# ===========================================================================
# AC1 + AC2 + AC3: Successful upload
# ===========================================================================


class TestSuccessfulUpload:
    """Successful POST (2xx) acks the uploaded rowids."""

    def test_peeks_with_batch_size(self) -> None:
        """AC1: peek is called with the configured batch_size."""
        spool = MagicMock()
        spool.peek.return_value = []

        uploader = _make_uploader(spool, batch_size=42)
        uploader.upload_batch()

        spool.peek.assert_called_once_with(42)

    def test_posts_to_correct_url(self) -> None:
        """AC2: POST goes to {ingest_url}/v1/ingest."""
        spool = MagicMock()
        rows = _make_spool_rows(2)
        spool.peek.return_value = rows

        uploader = _make_uploader(spool)
        mock_resp = _mock_response(status_code=200)

        with patch.object(uploader, "_client") as mock_client:
            mock_client.post.return_value = mock_resp
            uploader.upload_batch()

        post_call = mock_client.post.call_args
        assert post_call[0][0] == f"{_INGEST_URL}/v1/ingest"

    def test_posts_with_bearer_token(self) -> None:
        """AC2: POST includes Authorization: Bearer header."""
        spool = MagicMock()
        rows = _make_spool_rows(1)
        spool.peek.return_value = rows

        uploader = _make_uploader(spool)
        mock_resp = _mock_response(status_code=200)

        with patch.object(uploader, "_client") as mock_client:
            mock_client.post.return_value = mock_resp
            uploader.upload_batch()

        post_call = mock_client.post.call_args
        headers = post_call[1]["headers"]
        assert headers["Authorization"] == f"Bearer {_DEVICE_TOKEN}"

    def test_posts_samples_payload(self) -> None:
        """AC2: POST body is {"samples": [...]} with correct fields."""
        spool = MagicMock()
        rows = _make_spool_rows(2)
        spool.peek.return_value = rows

        uploader = _make_uploader(spool)
        mock_resp = _mock_response(status_code=200)

        with patch.object(uploader, "_client") as mock_client:
            mock_client.post.return_value = mock_resp
            uploader.upload_batch()

        post_call = mock_client.post.call_args
        payload = post_call[1]["json"]
        assert "samples" in payload
        assert len(payload["samples"]) == 2

        # Verify sample fields (no rowid or created_at in payload)
        sample = payload["samples"][0]
        assert "device_id" in sample
        assert "ts" in sample
        assert "power_w" in sample
        assert "import_power_w" in sample
        assert "energy_import_kwh" in sample
        assert "energy_export_kwh" in sample
        assert "rowid" not in sample
        assert "created_at" not in sample

    def test_acks_rowids_on_2xx(self) -> None:
        """AC3: On 2xx response, acks the uploaded rowids."""
        spool = MagicMock()
        rows = _make_spool_rows(3)
        spool.peek.return_value = rows

        uploader = _make_uploader(spool)
        mock_resp = _mock_response(status_code=200)

        with patch.object(uploader, "_client") as mock_client:
            mock_client.post.return_value = mock_resp
            result = uploader.upload_batch()

        assert result is True
        spool.ack.assert_called_once_with([1, 2, 3])

    def test_acks_on_201(self) -> None:
        """AC3: HTTP 201 Created is also treated as success."""
        spool = MagicMock()
        rows = _make_spool_rows(1)
        spool.peek.return_value = rows

        uploader = _make_uploader(spool)
        mock_resp = _mock_response(status_code=201)

        with patch.object(uploader, "_client") as mock_client:
            mock_client.post.return_value = mock_resp
            result = uploader.upload_batch()

        assert result is True
        spool.ack.assert_called_once_with([1])

    def test_returns_true_on_success(self) -> None:
        """upload_batch returns True on successful upload."""
        spool = MagicMock()
        rows = _make_spool_rows(1)
        spool.peek.return_value = rows

        uploader = _make_uploader(spool)
        mock_resp = _mock_response(status_code=200)

        with patch.object(uploader, "_client") as mock_client:
            mock_client.post.return_value = mock_resp
            result = uploader.upload_batch()

        assert result is True


# ===========================================================================
# AC4: Failed upload does NOT ack
# ===========================================================================


class TestFailedUpload:
    """Non-2xx or connection errors do not ack rows."""

    def test_5xx_does_not_ack(self) -> None:
        """AC4: Server error (500) does not ack rows."""
        spool = MagicMock()
        rows = _make_spool_rows(2)
        spool.peek.return_value = rows

        uploader = _make_uploader(spool)
        mock_resp = _mock_response(status_code=500)

        with patch.object(uploader, "_client") as mock_client:
            mock_client.post.return_value = mock_resp
            result = uploader.upload_batch()

        assert result is False
        spool.ack.assert_not_called()

    def test_4xx_does_not_ack(self) -> None:
        """AC4: Client error (400) does not ack rows."""
        spool = MagicMock()
        rows = _make_spool_rows(2)
        spool.peek.return_value = rows

        uploader = _make_uploader(spool)
        mock_resp = _mock_response(status_code=400)

        with patch.object(uploader, "_client") as mock_client:
            mock_client.post.return_value = mock_resp
            result = uploader.upload_batch()

        assert result is False
        spool.ack.assert_not_called()

    def test_connection_error_does_not_ack(self) -> None:
        """AC4: Connection error does not ack rows."""
        spool = MagicMock()
        rows = _make_spool_rows(2)
        spool.peek.return_value = rows

        uploader = _make_uploader(spool)

        with patch.object(uploader, "_client") as mock_client:
            mock_client.post.side_effect = httpx.ConnectError(
                "Connection refused"
            )
            result = uploader.upload_batch()

        assert result is False
        spool.ack.assert_not_called()

    def test_timeout_error_does_not_ack(self) -> None:
        """AC4: Timeout error does not ack rows."""
        spool = MagicMock()
        rows = _make_spool_rows(2)
        spool.peek.return_value = rows

        uploader = _make_uploader(spool)

        with patch.object(uploader, "_client") as mock_client:
            mock_client.post.side_effect = httpx.TimeoutException(
                "Read timed out"
            )
            result = uploader.upload_batch()

        assert result is False
        spool.ack.assert_not_called()

    def test_returns_false_on_5xx(self) -> None:
        """upload_batch returns False on server error."""
        spool = MagicMock()
        rows = _make_spool_rows(1)
        spool.peek.return_value = rows

        uploader = _make_uploader(spool)
        mock_resp = _mock_response(status_code=500)

        with patch.object(uploader, "_client") as mock_client:
            mock_client.post.return_value = mock_resp
            result = uploader.upload_batch()

        assert result is False

    def test_returns_false_on_connection_error(self) -> None:
        """upload_batch returns False on connection error."""
        spool = MagicMock()
        rows = _make_spool_rows(1)
        spool.peek.return_value = rows

        uploader = _make_uploader(spool)

        with patch.object(uploader, "_client") as mock_client:
            mock_client.post.side_effect = httpx.ConnectError(
                "Connection refused"
            )
            result = uploader.upload_batch()

        assert result is False


# ===========================================================================
# AC5: Exponential backoff sequence
# ===========================================================================


class TestExponentialBackoff:
    """Backoff increases exponentially: 1s, 2s, 4s, 8s, ..., max."""

    def test_initial_backoff_is_one(self) -> None:
        """AC5: Initial backoff is 1 second."""
        spool = MagicMock()
        uploader = _make_uploader(spool)

        assert uploader.current_backoff == 1.0

    def test_backoff_doubles_on_failure(self) -> None:
        """AC5: Backoff doubles after each failed upload."""
        spool = MagicMock()
        rows = _make_spool_rows(1)
        spool.peek.return_value = rows

        uploader = _make_uploader(spool)

        with patch.object(uploader, "_client") as mock_client:
            mock_client.post.return_value = _mock_response(
                status_code=500
            )

            uploader.upload_batch()
            assert uploader.current_backoff == 2.0

            uploader.upload_batch()
            assert uploader.current_backoff == 4.0

            uploader.upload_batch()
            assert uploader.current_backoff == 8.0

    def test_backoff_sequence(self) -> None:
        """AC5: Full sequence 1 -> 2 -> 4 -> 8 -> 16 -> 32."""
        spool = MagicMock()
        rows = _make_spool_rows(1)
        spool.peek.return_value = rows

        uploader = _make_uploader(spool, max_backoff=300.0)
        expected = [1.0, 2.0, 4.0, 8.0, 16.0, 32.0]

        with patch.object(uploader, "_client") as mock_client:
            mock_client.post.return_value = _mock_response(
                status_code=500
            )

            for i, expected_backoff in enumerate(expected):
                assert uploader.current_backoff == expected_backoff, (
                    f"Attempt {i}: expected {expected_backoff}, "
                    f"got {uploader.current_backoff}"
                )
                uploader.upload_batch()

    def test_backoff_capped_at_max(self) -> None:
        """AC5: Backoff never exceeds max_backoff."""
        spool = MagicMock()
        rows = _make_spool_rows(1)
        spool.peek.return_value = rows

        uploader = _make_uploader(spool, max_backoff=10.0)

        with patch.object(uploader, "_client") as mock_client:
            mock_client.post.return_value = _mock_response(
                status_code=500
            )

            # Fail many times: 1 -> 2 -> 4 -> 8 -> 10 -> 10
            for _ in range(10):
                uploader.upload_batch()

            assert uploader.current_backoff == 10.0

    def test_connection_error_increases_backoff(self) -> None:
        """AC5: Connection errors also increase backoff."""
        spool = MagicMock()
        rows = _make_spool_rows(1)
        spool.peek.return_value = rows

        uploader = _make_uploader(spool)

        with patch.object(uploader, "_client") as mock_client:
            mock_client.post.side_effect = httpx.ConnectError(
                "Connection refused"
            )

            uploader.upload_batch()
            assert uploader.current_backoff == 2.0

            uploader.upload_batch()
            assert uploader.current_backoff == 4.0


# ===========================================================================
# AC6: Backoff resets after success
# ===========================================================================


class TestBackoffReset:
    """Backoff resets to 1s after a successful upload."""

    def test_backoff_resets_after_success(self) -> None:
        """AC6: After a failure and then a success, backoff returns to 1s."""
        spool = MagicMock()
        rows = _make_spool_rows(1)
        spool.peek.return_value = rows

        uploader = _make_uploader(spool)

        with patch.object(uploader, "_client") as mock_client:
            # Fail twice: backoff goes 1 -> 2 -> 4
            mock_client.post.return_value = _mock_response(
                status_code=500
            )
            uploader.upload_batch()
            uploader.upload_batch()
            assert uploader.current_backoff == 4.0

            # Succeed: backoff resets to 1
            mock_client.post.return_value = _mock_response(
                status_code=200
            )
            uploader.upload_batch()
            assert uploader.current_backoff == 1.0

    def test_backoff_resets_after_deep_failure_then_success(self) -> None:
        """AC6: Even after many failures, success resets backoff to 1s."""
        spool = MagicMock()
        rows = _make_spool_rows(1)
        spool.peek.return_value = rows

        uploader = _make_uploader(spool, max_backoff=300.0)

        with patch.object(uploader, "_client") as mock_client:
            # Fail many times
            mock_client.post.return_value = _mock_response(
                status_code=500
            )
            for _ in range(15):
                uploader.upload_batch()

            assert uploader.current_backoff == 300.0

            # One success resets everything
            mock_client.post.return_value = _mock_response(
                status_code=200
            )
            uploader.upload_batch()
            assert uploader.current_backoff == 1.0

    def test_empty_spool_does_not_change_backoff(self) -> None:
        """AC9 + AC6: Empty spool skip does not affect backoff state."""
        spool = MagicMock()
        rows = _make_spool_rows(1)

        uploader = _make_uploader(spool)

        with patch.object(uploader, "_client") as mock_client:
            # Fail once: backoff goes to 2
            spool.peek.return_value = rows
            mock_client.post.return_value = _mock_response(
                status_code=500
            )
            uploader.upload_batch()
            assert uploader.current_backoff == 2.0

            # Empty spool: backoff stays at 2
            spool.peek.return_value = []
            uploader.upload_batch()
            assert uploader.current_backoff == 2.0


# ===========================================================================
# URL normalisation: trailing slash stripped
# ===========================================================================


class TestUrlNormalisation:
    """Trailing slash on ingest URL is stripped to avoid //v1/ingest."""

    def test_trailing_slash_stripped(self) -> None:
        """Trailing slash on ingest URL does not produce double-slash."""
        spool = MagicMock()
        uploader = _make_uploader(
            spool, ingest_url="https://vps.example.com/",
        )
        assert uploader._ingest_url == "https://vps.example.com"

    def test_no_trailing_slash_unchanged(self) -> None:
        """URL without trailing slash is unchanged."""
        spool = MagicMock()
        uploader = _make_uploader(
            spool, ingest_url="https://vps.example.com",
        )
        assert uploader._ingest_url == "https://vps.example.com"
