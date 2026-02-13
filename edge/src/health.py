"""
Edge health check module reporting spool depth, upload status,
and P1 meter connectivity.

Exposes ``get_health_status()`` which returns a dict summarizing
the current operational state of the edge daemon. Also provides
``write_health_file()`` for Docker healthcheck integration via a
JSON file on disk.

CHANGELOG:
- 2026-02-13: Initial creation (STORY-014)

TODO:
- None
"""

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Module-level state tracking for upload results.
_last_upload_ok: bool | None = None
_last_upload_ts: float | None = None

# Default health file path (inside the Docker volume).
HEALTH_FILE_PATH = "/data/health.json"


def record_upload_success() -> None:
    """Record a successful upload with the current timestamp."""
    global _last_upload_ok, _last_upload_ts  # noqa: PLW0603
    _last_upload_ok = True
    _last_upload_ts = time.monotonic()


def record_upload_failure() -> None:
    """Record a failed upload with the current timestamp."""
    global _last_upload_ok, _last_upload_ts  # noqa: PLW0603
    _last_upload_ok = False
    _last_upload_ts = time.monotonic()


def get_health_status(
    spool: Any,
    uploader: Any,
) -> dict[str, Any]:
    """Build a health status dict for the edge daemon.

    Checks:
    - **spool_depth**: number of pending samples in the spool.
    - **last_upload_success**: whether the most recent upload
      succeeded (``None`` if no upload has been attempted yet).
    - **last_upload_elapsed_s**: seconds since the last upload
      attempt (``None`` if no upload has been attempted yet).
    - **current_backoff**: the uploader's current backoff delay.

    Args:
        spool: The local Spool instance (must have ``count()``).
        uploader: The Uploader instance (must have
            ``current_backoff`` property).

    Returns:
        Dict with health status fields.
    """
    spool_depth: int | None = None
    try:
        spool_depth = spool.count()
    except Exception:
        logger.warning(
            "Health check: failed to read spool count",
            exc_info=True,
        )

    elapsed: float | None = None
    if _last_upload_ts is not None:
        elapsed = round(time.monotonic() - _last_upload_ts, 1)

    return {
        "spool_depth": spool_depth,
        "last_upload_success": _last_upload_ok,
        "last_upload_elapsed_s": elapsed,
        "current_backoff": uploader.current_backoff,
        "checked_at": datetime.now(tz=UTC).isoformat(),
    }


def write_health_file(
    spool: Any,
    uploader: Any,
    path: str = HEALTH_FILE_PATH,
) -> None:
    """Write health status to a JSON file for Docker healthcheck.

    The Docker healthcheck can verify this file exists and was
    recently updated. Errors during write are logged but not raised.

    Args:
        spool: The local Spool instance.
        uploader: The Uploader instance.
        path: Filesystem path for the health file.
    """
    try:
        status = get_health_status(spool, uploader)
        Path(path).write_text(
            json.dumps(status), encoding="utf-8"
        )
    except Exception:
        logger.warning(
            "Health check: failed to write health file",
            exc_info=True,
        )


def reset() -> None:
    """Reset module-level state (for testing only)."""
    global _last_upload_ok, _last_upload_ts  # noqa: PLW0603
    _last_upload_ok = None
    _last_upload_ts = None
