"""
Unit tests for the edge health check module (STORY-014).

Tests verify:
- AC2: get_health_status reports spool depth.
- AC2: get_health_status reports last upload success/failure.
- AC2: get_health_status reports current backoff.
- write_health_file writes valid JSON to disk.
- record_upload_success/failure update module state.

CHANGELOG:
- 2026-02-13: Initial creation (STORY-014)

TODO:
- None
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from edge.src.health import (
    get_health_status,
    record_upload_failure,
    record_upload_success,
    reset,
    write_health_file,
)


@pytest.fixture(autouse=True)
def _reset_health_state():
    """Reset module-level health state before each test."""
    reset()
    yield
    reset()


# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------


def _mock_spool(count: int = 5) -> MagicMock:
    """Return a mock Spool with a configurable count()."""
    spool = MagicMock()
    spool.count.return_value = count
    return spool


def _mock_uploader(backoff: float = 1.0) -> MagicMock:
    """Return a mock Uploader with a configurable current_backoff."""
    uploader = MagicMock()
    type(uploader).current_backoff = property(
        lambda self: backoff
    )
    return uploader


# ===========================================================
# AC2: get_health_status reports spool depth
# ===========================================================


class TestSpoolDepth:
    """Health status includes spool depth from spool.count()."""

    def test_spool_depth_reported(self):
        """AC2: spool_depth matches spool.count()."""
        spool = _mock_spool(count=42)
        uploader = _mock_uploader()

        result = get_health_status(spool, uploader)

        assert result["spool_depth"] == 42
        spool.count.assert_called_once()

    def test_spool_depth_zero(self):
        """AC2: spool_depth is 0 when spool is empty."""
        spool = _mock_spool(count=0)
        uploader = _mock_uploader()

        result = get_health_status(spool, uploader)

        assert result["spool_depth"] == 0

    def test_spool_error_returns_none(self):
        """AC2: spool_depth is None when count() raises."""
        spool = MagicMock()
        spool.count.side_effect = Exception("DB locked")
        uploader = _mock_uploader()

        result = get_health_status(spool, uploader)

        assert result["spool_depth"] is None


# ===========================================================
# AC2: get_health_status reports upload status
# ===========================================================


class TestUploadStatus:
    """Health status reports last upload success/failure."""

    def test_no_upload_yet(self):
        """AC2: Before any upload, last_upload_success is None."""
        spool = _mock_spool()
        uploader = _mock_uploader()

        result = get_health_status(spool, uploader)

        assert result["last_upload_success"] is None
        assert result["last_upload_elapsed_s"] is None

    def test_after_success(self):
        """AC2: After record_upload_success, status shows True."""
        record_upload_success()
        spool = _mock_spool()
        uploader = _mock_uploader()

        result = get_health_status(spool, uploader)

        assert result["last_upload_success"] is True
        assert result["last_upload_elapsed_s"] is not None
        assert result["last_upload_elapsed_s"] >= 0.0

    def test_after_failure(self):
        """AC2: After record_upload_failure, status shows False."""
        record_upload_failure()
        spool = _mock_spool()
        uploader = _mock_uploader()

        result = get_health_status(spool, uploader)

        assert result["last_upload_success"] is False
        assert result["last_upload_elapsed_s"] is not None
        assert result["last_upload_elapsed_s"] >= 0.0

    def test_failure_then_success(self):
        """AC2: Success after failure updates to True."""
        record_upload_failure()
        record_upload_success()
        spool = _mock_spool()
        uploader = _mock_uploader()

        result = get_health_status(spool, uploader)

        assert result["last_upload_success"] is True


# ===========================================================
# AC2: get_health_status reports backoff
# ===========================================================


class TestBackoffReporting:
    """Health status includes current_backoff from uploader."""

    def test_backoff_reported(self):
        """AC2: current_backoff matches uploader property."""
        spool = _mock_spool()
        uploader = _mock_uploader(backoff=16.0)

        result = get_health_status(spool, uploader)

        assert result["current_backoff"] == 16.0


# ===========================================================
# get_health_status includes checked_at timestamp
# ===========================================================


class TestCheckedAt:
    """Health status includes an ISO timestamp."""

    def test_checked_at_present(self):
        """checked_at is a non-empty ISO timestamp string."""
        spool = _mock_spool()
        uploader = _mock_uploader()

        result = get_health_status(spool, uploader)

        assert "checked_at" in result
        assert isinstance(result["checked_at"], str)
        assert len(result["checked_at"]) > 0


# ===========================================================
# write_health_file writes JSON to disk
# ===========================================================


class TestWriteHealthFile:
    """write_health_file creates a valid JSON health file."""

    def test_writes_valid_json(self, tmp_path):
        """Health file contains valid JSON with expected keys."""
        spool = _mock_spool(count=10)
        uploader = _mock_uploader(backoff=2.0)
        path = str(tmp_path / "health.json")

        write_health_file(spool, uploader, path=path)

        data = json.loads((tmp_path / "health.json").read_text())
        assert data["spool_depth"] == 10
        assert data["current_backoff"] == 2.0
        assert "checked_at" in data

    def test_overwrites_existing_file(self, tmp_path):
        """Health file is overwritten on each call."""
        spool = _mock_spool(count=5)
        uploader = _mock_uploader()
        path = str(tmp_path / "health.json")

        write_health_file(spool, uploader, path=path)
        spool.count.return_value = 99
        write_health_file(spool, uploader, path=path)

        data = json.loads((tmp_path / "health.json").read_text())
        assert data["spool_depth"] == 99

    def test_error_does_not_raise(self, tmp_path):
        """write_health_file logs but does not raise on error."""
        spool = _mock_spool()
        uploader = _mock_uploader()
        # Write to a path that does not exist (bad parent dir).
        bad_path = "/nonexistent_dir_xyz/health.json"

        # Should not raise
        write_health_file(spool, uploader, path=bad_path)


# ===========================================================
# reset() clears module state
# ===========================================================


class TestReset:
    """reset() clears the upload tracking state."""

    def test_reset_clears_state(self):
        """After reset, last_upload_success is None again."""
        record_upload_success()
        reset()

        spool = _mock_spool()
        uploader = _mock_uploader()
        result = get_health_status(spool, uploader)

        assert result["last_upload_success"] is None
        assert result["last_upload_elapsed_s"] is None
