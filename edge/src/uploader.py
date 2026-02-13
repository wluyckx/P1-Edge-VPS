"""
Batch uploader with exponential backoff retry for VPS ingest endpoint.

Reads batches of normalized energy samples from the local SQLite spool
and POSTs them to the VPS ingest API. On success the uploaded rows are
acknowledged (deleted from the spool). On failure (network error or
non-2xx response) the rows remain in the spool and the next attempt is
delayed by exponential backoff.

Key safety invariants:
- HC-001: Never deletes from spool without server confirmation.
- HC-003: Rejects non-HTTPS ingest URLs at startup.
- TLS certificate verification is always enabled (verify=True).

CHANGELOG:
- 2026-02-13: Initial creation (STORY-005)

TODO:
- None
"""

import logging

import httpx
from edge.src.spool import Spool

logger = logging.getLogger(__name__)

# Keys to strip from spool rows before sending to the VPS.
_STRIP_KEYS = frozenset({"rowid", "created_at"})


class Uploader:
    """Batch uploader that reads from a Spool and POSTs to VPS ingest.

    On construction the ingest URL is validated to use HTTPS (HC-003).
    An ``httpx.Client`` is created with ``verify=True`` so TLS
    certificates are always checked.

    Args:
        spool: Local durable queue to read pending samples from.
        ingest_url: Base URL for the VPS ingest API (must be HTTPS).
        device_token: Bearer token for VPS authentication.
        batch_size: Maximum number of samples per upload batch.
        max_backoff: Maximum backoff delay in seconds.

    Raises:
        ValueError: If *ingest_url* does not use the ``https://`` scheme.
    """

    def __init__(
        self,
        spool: Spool,
        ingest_url: str,
        device_token: str,
        batch_size: int = 30,
        max_backoff: float = 300.0,
    ) -> None:
        if not ingest_url.startswith("https://"):
            raise ValueError(
                "ingest_url must use HTTPS "
                f"(got: '{ingest_url}'). See HC-003."
            )

        self._spool = spool
        self._ingest_url = ingest_url.rstrip("/")
        self._device_token = device_token
        self._batch_size = batch_size
        self._max_backoff = max_backoff

        # Backoff state: attempt counter drives the formula
        # min(base * 2^attempt, max_backoff) with base=1.
        self._attempt: int = 0

        # TLS verification is always enabled (HC-003).
        self._client = httpx.Client(verify=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def upload_batch(self) -> bool:
        """Attempt one upload cycle.

        Reads up to *batch_size* samples from the spool. If the spool
        is empty the cycle is a no-op (returns ``False``). Otherwise
        the batch is POSTed to ``{ingest_url}/v1/ingest``.

        On a 2xx response the uploaded rowids are acknowledged (deleted
        from the spool) and the backoff counter resets. On any failure
        the rows are NOT acknowledged and the backoff counter increases.

        Returns:
            ``True`` if samples were uploaded and acknowledged,
            ``False`` if the spool was empty or the upload failed.
        """
        rows = self._spool.peek(self._batch_size)
        if not rows:
            return False

        rowids = [r["rowid"] for r in rows]
        samples = [
            {k: v for k, v in row.items() if k not in _STRIP_KEYS}
            for row in rows
        ]
        payload = {"samples": samples}

        url = f"{self._ingest_url}/v1/ingest"
        headers = {"Authorization": f"Bearer {self._device_token}"}

        try:
            response = self._client.post(
                url, json=payload, headers=headers
            )
            response.raise_for_status()
        except (httpx.HTTPStatusError, httpx.TransportError) as exc:
            self._attempt += 1
            logger.warning(
                "Upload failed (attempt %d, next backoff %.1fs): %s",
                self._attempt,
                self.current_backoff,
                exc,
            )
            return False

        # Success — ack rows and reset backoff.
        self._spool.ack(rowids)
        self._attempt = 0
        logger.info(
            "Uploaded %d samples, acked rowids %s", len(samples), rowids
        )
        return True

    @property
    def current_backoff(self) -> float:
        """Current backoff delay in seconds.

        Formula: ``min(1 * 2^attempt, max_backoff)`` where *attempt*
        starts at 0 (giving an initial value of 1s) and increments on
        each consecutive failure.
        """
        return min(2**self._attempt, self._max_backoff)
