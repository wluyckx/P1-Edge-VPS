"""
Durable local queue using SQLite for buffering energy samples before upload.

This is the critical component for HC-001 (No Data Loss). Samples are written
to the spool before any upload attempt. They are only deleted after server
acknowledgment. The spool survives process restarts because it is backed by
a SQLite database file on disk.

Operations:
- enqueue(sample): INSERT a normalized sample row.
- peek(n): SELECT up to n oldest rows with their rowids (FIFO).
- ack(rowids): DELETE only the specified rows (confirmed by server).
- count(): SELECT COUNT(*) of pending samples.
- close(): Close the underlying database connection.

CHANGELOG:
- 2026-02-13: Initial creation (STORY-004)

TODO:
- None
"""

import sqlite3
from pathlib import Path

_CREATE_TABLE_SQL = """\
CREATE TABLE IF NOT EXISTS spool (
    rowid INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL,
    ts TEXT NOT NULL,
    power_w INTEGER NOT NULL,
    import_power_w INTEGER NOT NULL,
    energy_import_kwh REAL,
    energy_export_kwh REAL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

_INSERT_SQL = """\
INSERT INTO spool (device_id, ts, power_w, import_power_w,
    energy_import_kwh, energy_export_kwh)
VALUES (:device_id, :ts, :power_w, :import_power_w,
    :energy_import_kwh, :energy_export_kwh);
"""

_PEEK_SQL = """\
SELECT rowid, device_id, ts, power_w, import_power_w,
       energy_import_kwh, energy_export_kwh, created_at
FROM spool
ORDER BY rowid ASC
LIMIT :limit;
"""

_COUNT_SQL = "SELECT COUNT(*) FROM spool;"


class Spool:
    """Durable local FIFO queue backed by a SQLite database.

    Provides enqueue/peek/ack/count operations for buffering energy
    measurement samples before uploading to the VPS ingest endpoint.
    Uses WAL journal mode for concurrent read/write safety.

    Args:
        path: Filesystem path for the SQLite database file.
              Accepts ``str`` or ``pathlib.Path``.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._conn = sqlite3.connect(str(self._path))
        self._conn.row_factory = sqlite3.Row
        # Enable WAL mode for concurrent read/write (HC-001 durability).
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute(_CREATE_TABLE_SQL)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def enqueue(self, sample: dict) -> None:
        """Insert a normalized sample into the spool.

        The sample dict must contain keys: ``device_id``, ``ts``,
        ``power_w``, ``import_power_w``. Optional keys:
        ``energy_import_kwh``, ``energy_export_kwh`` (default ``None``).

        Args:
            sample: Dictionary with measurement fields.
        """
        params = {
            "device_id": sample["device_id"],
            "ts": sample["ts"],
            "power_w": sample["power_w"],
            "import_power_w": sample["import_power_w"],
            "energy_import_kwh": sample.get("energy_import_kwh"),
            "energy_export_kwh": sample.get("energy_export_kwh"),
        }
        self._conn.execute(_INSERT_SQL, params)
        self._conn.commit()

    def peek(self, n: int) -> list[dict]:
        """Return up to *n* oldest pending samples without removing them.

        Results are ordered by ``rowid ASC`` (FIFO). Each returned dict
        includes the ``rowid`` key so the caller can later acknowledge
        specific rows via :meth:`ack`.

        Args:
            n: Maximum number of rows to return.

        Returns:
            List of sample dicts, each containing ``rowid`` and all
            spool columns. Empty list when the spool has no pending rows.
        """
        if n < 1:
            return []
        cursor = self._conn.execute(_PEEK_SQL, {"limit": n})
        return [dict(row) for row in cursor.fetchall()]

    def ack(self, rowids: list[int]) -> None:
        """Delete confirmed rows from the spool.

        Only rows whose ``rowid`` appears in *rowids* are removed.
        Nonexistent rowids are silently ignored. An empty list is a no-op.

        Args:
            rowids: List of rowid integers to delete.
        """
        if not rowids:
            return
        # Use parameterized placeholders to prevent SQL injection (SKILL.md).
        placeholders = ",".join("?" for _ in rowids)
        sql = f"DELETE FROM spool WHERE rowid IN ({placeholders});"  # noqa: S608
        self._conn.execute(sql, rowids)
        self._conn.commit()

    def count(self) -> int:
        """Return the number of pending (unacknowledged) samples.

        Returns:
            Integer count of rows in the spool table.
        """
        cursor = self._conn.execute(_COUNT_SQL)
        return cursor.fetchone()[0]

    def close(self) -> None:
        """Close the underlying SQLite connection.

        After calling close, no further operations should be performed
        on this Spool instance.
        """
        self._conn.close()
