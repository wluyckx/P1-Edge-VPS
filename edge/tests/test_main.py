"""
Unit tests for the edge daemon entry point (STORY-015).

Tests verify:
- AC1: Structured JSON logging is configured via setup_logging().
- AC2: Graceful shutdown flushes pending uploads before exit.
- AC4: SIGTERM/SIGINT handlers are registered.
- Shutdown event stops poll and upload loops.
- _flush_uploads() calls upload_batch() one final time.

CHANGELOG:
- 2026-02-13: Initial creation (STORY-015)

TODO:
- None
"""

import json
import logging
import signal
import threading
from unittest.mock import MagicMock, patch

from edge.src.logging_config import JSONFormatter, setup_logging

# ====================================================================
# AC1: Structured JSON logging
# ====================================================================


class TestJSONFormatter:
    """JSONFormatter outputs valid JSON with required fields."""

    def test_format_returns_valid_json(self) -> None:
        """Log output is parseable JSON."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="hello world",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert isinstance(parsed, dict)

    def test_format_contains_required_fields(self) -> None:
        """Output JSON contains timestamp, level, logger, message."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="myapp.module",
            level=logging.WARNING,
            pathname="test.py",
            lineno=42,
            msg="something happened",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)

        assert "timestamp" in parsed
        assert parsed["level"] == "WARNING"
        assert parsed["logger"] == "myapp.module"
        assert parsed["message"] == "something happened"

    def test_format_with_args(self) -> None:
        """Message formatting with %-style args works."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="count=%d",
            args=(42,),
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["message"] == "count=42"


class TestSetupLogging:
    """setup_logging() configures root logger with JSONFormatter."""

    def test_root_logger_has_json_handler(self) -> None:
        """After setup_logging(), root has a handler with JSONFormatter."""
        setup_logging()
        root = logging.getLogger()
        assert len(root.handlers) >= 1
        has_json = any(isinstance(h.formatter, JSONFormatter) for h in root.handlers)
        assert has_json

    def test_setup_logging_sets_level(self) -> None:
        """setup_logging(level=DEBUG) sets root to DEBUG."""
        setup_logging(level=logging.DEBUG)
        root = logging.getLogger()
        assert root.level == logging.DEBUG

        # Reset to INFO for other tests.
        setup_logging(level=logging.INFO)


# ====================================================================
# AC4: Signal handlers registered
# ====================================================================


class TestSignalHandlers:
    """Signal handlers for SIGTERM and SIGINT are registered."""

    @patch("edge.src.main.setup_logging")
    @patch("edge.src.main.EdgeSettings")
    @patch("edge.src.main.Spool")
    @patch("edge.src.main.Uploader")
    def test_sigterm_handler_registered(
        self,
        mock_uploader_cls: MagicMock,
        mock_spool_cls: MagicMock,
        mock_settings_cls: MagicMock,
        mock_setup: MagicMock,
    ) -> None:
        """SIGTERM handler is registered during main()."""
        from edge.src.main import (
            shutdown_event,
        )

        # Ensure shutdown_event is clear before the test.
        shutdown_event.clear()

        mock_settings = MagicMock()
        mock_settings.poll_interval_s = 2
        mock_settings.upload_interval_s = 10
        mock_settings.batch_size = 30
        mock_settings_cls.return_value = mock_settings

        mock_spool = MagicMock()
        mock_spool_cls.return_value = mock_spool

        mock_uploader = MagicMock()
        mock_uploader.upload_batch.return_value = False
        mock_uploader_cls.return_value = mock_uploader

        with patch("signal.signal") as mock_signal:
            # Set shutdown event immediately so main() does not block.
            shutdown_event.set()

            from edge.src.main import main

            main()

            # Verify both signals were registered.
            calls = mock_signal.call_args_list
            registered_signals = {c[0][0] for c in calls}
            assert signal.SIGTERM in registered_signals
            assert signal.SIGINT in registered_signals

        # Clean up for other tests.
        shutdown_event.clear()

    def test_signal_handler_sets_event(self) -> None:
        """_signal_handler sets the shutdown_event."""
        from edge.src.main import (
            _signal_handler,
            shutdown_event,
        )

        shutdown_event.clear()
        _signal_handler(signal.SIGTERM, None)
        assert shutdown_event.is_set()

        # Clean up.
        shutdown_event.clear()


# ====================================================================
# Shutdown event stops loops
# ====================================================================


class TestShutdownEvent:
    """Setting shutdown_event causes _poll_loop and _upload_loop
    to exit."""

    def test_poll_loop_exits_on_shutdown(self) -> None:
        """_poll_loop exits when shutdown_event is set."""
        from edge.src.main import _poll_loop, shutdown_event

        shutdown_event.clear()

        settings = MagicMock()
        settings.poll_interval_s = 0.01
        settings.device_id = "test"
        spool = MagicMock()

        with patch("edge.src.main.poll_measurement", return_value=None):
            # Set shutdown immediately.
            shutdown_event.set()
            thread = threading.Thread(
                target=_poll_loop,
                args=(settings, spool),
                daemon=True,
            )
            thread.start()
            thread.join(timeout=2)
            assert not thread.is_alive()

        shutdown_event.clear()

    def test_upload_loop_exits_on_shutdown(self) -> None:
        """_upload_loop exits when shutdown_event is set."""
        from edge.src.main import _upload_loop, shutdown_event

        shutdown_event.clear()

        settings = MagicMock()
        settings.upload_interval_s = 0.01
        spool = MagicMock()
        spool.count.return_value = 0
        uploader = MagicMock()
        uploader.upload_batch.return_value = False
        uploader.current_backoff = 0.01

        shutdown_event.set()
        thread = threading.Thread(
            target=_upload_loop,
            args=(settings, spool, uploader),
            daemon=True,
        )
        thread.start()
        thread.join(timeout=2)
        assert not thread.is_alive()

        shutdown_event.clear()


# ====================================================================
# AC2: Flush pending uploads before exit
# ====================================================================


class TestFlushUploads:
    """_flush_uploads() calls upload_batch one final time."""

    def test_flush_calls_upload_batch(self) -> None:
        """_flush_uploads calls uploader.upload_batch()."""
        from edge.src.main import _flush_uploads

        uploader = MagicMock()
        uploader.upload_batch.return_value = True

        _flush_uploads(uploader)
        uploader.upload_batch.assert_called_once()

    def test_flush_handles_exception(self) -> None:
        """_flush_uploads does not raise if upload_batch fails."""
        from edge.src.main import _flush_uploads

        uploader = MagicMock()
        uploader.upload_batch.side_effect = RuntimeError("network")

        # Should not raise.
        _flush_uploads(uploader)
        uploader.upload_batch.assert_called_once()

    def test_flush_on_empty_spool(self) -> None:
        """_flush_uploads handles empty spool (upload_batch=False)."""
        from edge.src.main import _flush_uploads

        uploader = MagicMock()
        uploader.upload_batch.return_value = False

        _flush_uploads(uploader)
        uploader.upload_batch.assert_called_once()
