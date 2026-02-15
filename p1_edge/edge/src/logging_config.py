"""
Structured JSON logging configuration for the edge daemon.

Provides a custom JSON formatter and a ``setup_logging()`` function
that replaces the default logging configuration with structured output.
Each log record is emitted as a single JSON line containing:
``timestamp``, ``level``, ``logger``, and ``message``.

CHANGELOG:
- 2026-02-13: Initial creation (STORY-015)

TODO:
- None
"""

import json
import logging
from datetime import UTC, datetime


class JSONFormatter(logging.Formatter):
    """Logging formatter that outputs a single JSON object per line.

    Fields emitted:
    - ``timestamp``: ISO-8601 UTC timestamp.
    - ``level``: Log level name (INFO, WARNING, ERROR, ...).
    - ``logger``: Logger name.
    - ``message``: Formatted log message.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format *record* as a JSON string.

        Args:
            record: The log record to format.

        Returns:
            A single-line JSON string.
        """
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        return json.dumps(log_entry, default=str)


def setup_logging(level: int = logging.INFO) -> None:
    """Configure the root logger with structured JSON output.

    Removes any existing handlers on the root logger and installs
    a single ``StreamHandler`` using :class:`JSONFormatter`.

    Args:
        level: Logging level for the root logger.  Defaults to
            ``logging.INFO``.
    """
    root = logging.getLogger()
    root.setLevel(level)

    # Remove existing handlers to avoid duplicate output.
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    root.addHandler(handler)
