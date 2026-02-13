"""
Edge daemon entry point — poll loop + upload loop using threading.

Runs two threads:
1. **Poll thread**: polls the HomeWizard P1 meter at ``poll_interval_s``,
   normalizes the reading, and enqueues it into the local spool.
2. **Upload thread**: reads batches from the spool and uploads them to the
   VPS ingest endpoint at ``upload_interval_s``, with exponential backoff
   on failure.

Both threads run as daemon threads so the process exits cleanly on
KeyboardInterrupt (Ctrl-C).

CHANGELOG:
- 2026-02-13: Initial creation (STORY-005)

TODO:
- None
"""

import logging
import threading
import time
from datetime import UTC, datetime

from edge.src.config import EdgeSettings
from edge.src.normalizer import normalize
from edge.src.poller import poll_measurement
from edge.src.spool import Spool
from edge.src.uploader import Uploader

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


def _poll_loop(
    settings: EdgeSettings,
    spool: Spool,
) -> None:
    """Continuously poll the P1 meter and enqueue samples.

    Runs forever. On each iteration:
    1. Poll the HomeWizard P1 meter.
    2. Normalize the raw reading.
    3. Enqueue the normalized sample into the spool.
    4. Sleep for ``poll_interval_s``.

    Any single-poll failure is logged and skipped (the loop continues).
    """
    device_id = settings.device_id
    while True:
        try:
            raw = poll_measurement(
                host=settings.hw_p1_host,
                token=settings.hw_p1_token,
            )
            if raw is not None:
                ts = datetime.now(tz=UTC)
                sample = normalize(raw, device_id, ts)
                spool.enqueue(sample)
                logger.info(
                    "Enqueued sample (spool count: %d)",
                    spool.count(),
                )
        except Exception:
            logger.exception("Unexpected error in poll loop")

        time.sleep(settings.poll_interval_s)


def _upload_loop(
    settings: EdgeSettings,
    uploader: Uploader,
) -> None:
    """Continuously upload batches from the spool to the VPS.

    Runs forever. On each iteration:
    1. Attempt ``upload_batch()``.
    2. On failure, sleep for the current backoff duration.
    3. On success or empty spool, sleep for ``upload_interval_s``.
    """
    while True:
        try:
            success = uploader.upload_batch()
        except Exception:
            logger.exception("Unexpected error in upload loop")
            success = False

        if success:
            time.sleep(settings.upload_interval_s)
        else:
            # Use the larger of upload_interval and current backoff,
            # so we never upload faster than the configured interval.
            delay = max(
                settings.upload_interval_s,
                uploader.current_backoff,
            )
            time.sleep(delay)


def main() -> None:
    """Edge daemon entry point.

    Loads configuration from environment variables, creates the spool
    and uploader, then starts poll and upload threads. The main thread
    blocks until interrupted (Ctrl-C).
    """
    settings = EdgeSettings()

    spool = Spool(path=settings.spool_path)
    uploader = Uploader(
        spool=spool,
        ingest_url=settings.vps_ingest_url,
        device_token=settings.vps_device_token,
        batch_size=settings.batch_size,
    )

    logger.info(
        "Edge daemon starting — poll every %ds, upload every %ds, "
        "batch size %d",
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
        args=(settings, uploader),
        daemon=True,
        name="upload-thread",
    )

    poll_thread.start()
    upload_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Edge daemon shutting down")
    finally:
        spool.close()


if __name__ == "__main__":
    main()
