"""
Edge daemon entry point -- poll loop + upload loop using threading.

Runs two threads:
1. **Poll thread**: polls the HomeWizard P1 meter at ``poll_interval_s``,
   normalizes the reading, and enqueues it into the local spool.
2. **Upload thread**: reads batches from the spool and uploads them to the
   VPS ingest endpoint at ``upload_interval_s``, with exponential backoff
   on failure.

Handles SIGTERM and SIGINT for graceful shutdown inside Docker:
- Sets a ``shutdown_event`` that stops both loops.
- Flushes pending uploads before exiting.
- Closes the spool.

CHANGELOG:
- 2026-02-13: Initial creation (STORY-005)
- 2026-02-13: Wire health file writing into poll/upload loops (quality fix)
- 2026-02-13: Structured JSON logging, graceful shutdown, signal
              handling (STORY-015)

TODO:
- None
"""

import logging
import signal
import threading
from datetime import UTC, datetime
from types import FrameType

from edge.src.config import EdgeSettings
from edge.src.health import (
    record_p1_connected,
    record_upload_failure,
    record_upload_success,
    write_health_file,
)
from edge.src.logging_config import setup_logging
from edge.src.normalizer import normalize
from edge.src.poller import poll_measurement
from edge.src.spool import Spool
from edge.src.uploader import Uploader

logger = logging.getLogger(__name__)

# Module-level shutdown event shared between signal handlers and loops.
shutdown_event = threading.Event()


def _poll_loop(
    settings: EdgeSettings,
    spool: Spool,
) -> None:
    """Continuously poll the P1 meter and enqueue samples.

    Runs until ``shutdown_event`` is set. On each iteration:
    1. Poll the HomeWizard P1 meter.
    2. Normalize the raw reading.
    3. Enqueue the normalized sample into the spool.
    4. Sleep for ``poll_interval_s`` (interruptible).

    Any single-poll failure is logged and skipped (the loop continues).
    Records P1 connectivity status for the health check.
    """
    device_id = settings.device_id
    while not shutdown_event.is_set():
        try:
            raw = poll_measurement(
                host=settings.hw_p1_host,
                token=settings.hw_p1_token,
            )
            record_p1_connected(raw is not None)
            if raw is not None:
                ts = datetime.now(tz=UTC)
                sample = normalize(raw, device_id, ts)
                spool.enqueue(sample)
                logger.info(
                    "Enqueued sample (spool count: %d)",
                    spool.count(),
                )
        except Exception:
            record_p1_connected(False)
            logger.exception("Unexpected error in poll loop")

        shutdown_event.wait(timeout=settings.poll_interval_s)


def _upload_loop(
    settings: EdgeSettings,
    spool: Spool,
    uploader: Uploader,
) -> None:
    """Continuously upload batches from the spool to the VPS.

    Runs until ``shutdown_event`` is set. On each iteration:
    1. Attempt ``upload_batch()``.
    2. Record upload result and write health file.
    3. On failure, sleep for the current backoff duration.
    4. On success or empty spool, sleep for ``upload_interval_s``.
    """
    while not shutdown_event.is_set():
        try:
            success = uploader.upload_batch()
        except Exception:
            logger.exception("Unexpected error in upload loop")
            success = False

        if success:
            record_upload_success()
            delay = settings.upload_interval_s
        else:
            record_upload_failure()
            # Use the larger of upload_interval and current backoff,
            # so we never upload faster than the configured interval.
            delay = max(
                settings.upload_interval_s,
                uploader.current_backoff,
            )

        write_health_file(spool, uploader)
        shutdown_event.wait(timeout=delay)


def _flush_uploads(uploader: Uploader) -> None:
    """Attempt one final upload batch to flush pending samples.

    Called during graceful shutdown to drain the spool as much as
    possible before the process exits.
    """
    logger.info("Flushing pending uploads before shutdown")
    try:
        flushed = uploader.upload_batch()
        if flushed:
            logger.info("Final upload flush succeeded")
        else:
            logger.info("No pending samples to flush (or flush failed)")
    except Exception:
        logger.exception("Error during final upload flush")


def _signal_handler(
    signum: int,
    _frame: FrameType | None,
) -> None:
    """Handle SIGTERM/SIGINT by signalling shutdown.

    Sets ``shutdown_event`` so all loops exit cleanly.
    """
    sig_name = signal.Signals(signum).name
    logger.info("Received %s, initiating graceful shutdown", sig_name)
    shutdown_event.set()


def main() -> None:
    """Edge daemon entry point.

    Loads configuration from environment variables, creates the spool
    and uploader, registers signal handlers, then starts poll and upload
    threads. The main thread blocks on ``shutdown_event`` until a signal
    is received, then flushes pending uploads and closes the spool.
    """
    setup_logging()

    settings = EdgeSettings()

    spool = Spool(path=settings.spool_path)
    uploader = Uploader(
        spool=spool,
        ingest_url=settings.vps_ingest_url,
        device_token=settings.vps_device_token,
        batch_size=settings.batch_size,
    )

    # Register signal handlers for graceful shutdown (AC4).
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    logger.info(
        "Edge daemon starting -- poll every %ds, upload every %ds, batch size %d",
        settings.poll_interval_s,
        settings.upload_interval_s,
        settings.batch_size,
    )

    poll_thread = threading.Thread(
        target=_poll_loop,
        args=(settings, spool),
        daemon=True,
        name="poll-thread",
    )
    upload_thread = threading.Thread(
        target=_upload_loop,
        args=(settings, spool, uploader),
        daemon=True,
        name="upload-thread",
    )

    poll_thread.start()
    upload_thread.start()

    # Block until a signal sets the shutdown event.
    shutdown_event.wait()

    logger.info("Shutdown event received, stopping loops")

    # Give threads a moment to exit their current iteration.
    poll_thread.join(timeout=5)
    upload_thread.join(timeout=5)

    # Flush any remaining samples before exit (AC2).
    _flush_uploads(uploader)

    spool.close()
    logger.info("Edge daemon shut down cleanly")


if __name__ == "__main__":
    main()
