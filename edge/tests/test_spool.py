"""
Unit tests for the SQLite spool (local buffer) module.

Tests verify:
- Spool creates SQLite DB with WAL mode at configurable path.
- enqueue(sample) inserts a normalized sample row.
- peek(n) returns up to n oldest samples with their rowids (FIFO).
- ack(rowids) deletes only the specified rows.
- count() returns number of pending samples.
- Spool DB file persists across process restarts (re-instantiation).

CHANGELOG:
- 2026-02-13: Initial creation (STORY-004)

TODO:
- None
"""

from pathlib import Path

from edge.src.spool import Spool

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_sample(
    device_id: str = "device-abc",
    ts: str = "2026-02-13T10:00:00Z",
    power_w: int = 1500,
    import_power_w: int = 1600,
    energy_import_kwh: float | None = 123.456,
    energy_export_kwh: float | None = 78.9,
) -> dict:
    """Return a valid sample dict matching the spool schema."""
    return {
        "device_id": device_id,
        "ts": ts,
        "power_w": power_w,
        "import_power_w": import_power_w,
        "energy_import_kwh": energy_import_kwh,
        "energy_export_kwh": energy_export_kwh,
    }


# ---------------------------------------------------------------------------
# WAL mode and DB creation
# ---------------------------------------------------------------------------


class TestSpoolCreation:
    """Spool creates a SQLite database with WAL journal mode."""

    def test_creates_db_file_at_configured_path(self, tmp_path: Path) -> None:
        """AC1: spool.py creates SQLite DB at configurable path."""
        db_path = tmp_path / "test_spool.db"
        spool = Spool(path=db_path)

        assert db_path.exists()
        spool.close()

    def test_wal_mode_enabled(self, tmp_path: Path) -> None:
        """AC1: WAL journal mode is set on the database."""
        db_path = tmp_path / "wal_test.db"
        spool = Spool(path=db_path)

        import sqlite3

        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("PRAGMA journal_mode;")
        journal_mode = cursor.fetchone()[0]
        conn.close()

        assert journal_mode == "wal"
        spool.close()

    def test_accepts_string_path(self, tmp_path: Path) -> None:
        """Constructor accepts both str and Path objects."""
        db_path = str(tmp_path / "str_path.db")
        spool = Spool(path=db_path)

        assert Path(db_path).exists()
        spool.close()

    def test_accepts_path_object(self, tmp_path: Path) -> None:
        """Constructor accepts pathlib.Path objects."""
        db_path = tmp_path / "path_obj.db"
        spool = Spool(path=db_path)

        assert db_path.exists()
        spool.close()


# ---------------------------------------------------------------------------
# enqueue + peek
# ---------------------------------------------------------------------------


class TestEnqueueAndPeek:
    """enqueue inserts samples; peek returns them with rowids."""

    def test_enqueue_peek_returns_sample_with_correct_data(
        self, tmp_path: Path
    ) -> None:
        """AC2 + AC3: enqueue inserts a row and peek returns it with correct values."""
        spool = Spool(path=tmp_path / "spool.db")
        sample = _make_sample()
        spool.enqueue(sample)

        rows = spool.peek(10)

        assert len(rows) == 1
        row = rows[0]
        assert "rowid" in row
        assert isinstance(row["rowid"], int)
        assert row["device_id"] == sample["device_id"]
        assert row["ts"] == sample["ts"]
        assert row["power_w"] == sample["power_w"]
        assert row["import_power_w"] == sample["import_power_w"]
        assert row["energy_import_kwh"] == sample["energy_import_kwh"]
        assert row["energy_export_kwh"] == sample["energy_export_kwh"]
        spool.close()

    def test_enqueue_with_null_energy_fields(self, tmp_path: Path) -> None:
        """AC2: energy_import_kwh and energy_export_kwh can be None."""
        spool = Spool(path=tmp_path / "spool.db")
        sample = _make_sample(energy_import_kwh=None, energy_export_kwh=None)
        spool.enqueue(sample)

        rows = spool.peek(1)

        assert len(rows) == 1
        assert rows[0]["energy_import_kwh"] is None
        assert rows[0]["energy_export_kwh"] is None
        spool.close()

    def test_peek_on_empty_spool_returns_empty_list(
        self, tmp_path: Path
    ) -> None:
        """AC3: peek on empty spool returns an empty list."""
        spool = Spool(path=tmp_path / "spool.db")

        rows = spool.peek(10)

        assert rows == []
        spool.close()

    def test_peek_limits_returned_rows(self, tmp_path: Path) -> None:
        """AC3: peek(n) returns at most n rows."""
        spool = Spool(path=tmp_path / "spool.db")
        for i in range(5):
            spool.enqueue(
                _make_sample(ts=f"2026-02-13T10:00:0{i}Z")
            )

        rows = spool.peek(3)

        assert len(rows) == 3
        spool.close()


# ---------------------------------------------------------------------------
# FIFO ordering
# ---------------------------------------------------------------------------


class TestFIFOOrdering:
    """peek returns oldest samples first, preserving insertion order."""

    def test_peek_returns_oldest_first(self, tmp_path: Path) -> None:
        """AC3: peek returns oldest (lowest rowid) first."""
        spool = Spool(path=tmp_path / "spool.db")
        timestamps = [
            "2026-02-13T10:00:00Z",
            "2026-02-13T10:00:01Z",
            "2026-02-13T10:00:02Z",
        ]
        for ts in timestamps:
            spool.enqueue(_make_sample(ts=ts))

        rows = spool.peek(3)

        assert [r["ts"] for r in rows] == timestamps
        spool.close()

    def test_multiple_enqueues_maintain_insertion_order(
        self, tmp_path: Path
    ) -> None:
        """Multiple enqueues maintain insertion order across peek calls."""
        spool = Spool(path=tmp_path / "spool.db")
        devices = ["dev-1", "dev-2", "dev-3", "dev-4", "dev-5"]
        for dev in devices:
            spool.enqueue(_make_sample(device_id=dev))

        rows = spool.peek(10)

        assert [r["device_id"] for r in rows] == devices
        # Rowids must be monotonically increasing
        rowids = [r["rowid"] for r in rows]
        assert rowids == sorted(rowids)
        spool.close()


# ---------------------------------------------------------------------------
# ack
# ---------------------------------------------------------------------------


class TestAck:
    """ack(rowids) deletes only the specified rows."""

    def test_ack_removes_specified_rows(self, tmp_path: Path) -> None:
        """AC4: ack deletes the acknowledged rows."""
        spool = Spool(path=tmp_path / "spool.db")
        for i in range(3):
            spool.enqueue(
                _make_sample(ts=f"2026-02-13T10:00:0{i}Z")
            )

        rows = spool.peek(3)
        # Ack the first two rows
        spool.ack([rows[0]["rowid"], rows[1]["rowid"]])

        remaining = spool.peek(10)
        assert len(remaining) == 1
        assert remaining[0]["ts"] == "2026-02-13T10:00:02Z"
        spool.close()

    def test_ack_leaves_unspecified_rows(self, tmp_path: Path) -> None:
        """AC4: ack does not touch rows that are not in the rowids list."""
        spool = Spool(path=tmp_path / "spool.db")
        spool.enqueue(_make_sample(device_id="keep-1"))
        spool.enqueue(_make_sample(device_id="remove"))
        spool.enqueue(_make_sample(device_id="keep-2"))

        rows = spool.peek(3)
        remove_rowid = [r["rowid"] for r in rows if r["device_id"] == "remove"]
        spool.ack(remove_rowid)

        remaining = spool.peek(10)
        remaining_devices = [r["device_id"] for r in remaining]
        assert "keep-1" in remaining_devices
        assert "keep-2" in remaining_devices
        assert "remove" not in remaining_devices
        spool.close()

    def test_ack_empty_list_does_nothing(self, tmp_path: Path) -> None:
        """ack([]) does not raise and does not delete anything."""
        spool = Spool(path=tmp_path / "spool.db")
        spool.enqueue(_make_sample())

        spool.ack([])

        assert spool.count() == 1
        spool.close()

    def test_ack_nonexistent_rowids_does_not_raise(
        self, tmp_path: Path
    ) -> None:
        """ack with nonexistent rowids completes without error."""
        spool = Spool(path=tmp_path / "spool.db")
        spool.enqueue(_make_sample())

        spool.ack([9999, 8888])

        assert spool.count() == 1
        spool.close()


# ---------------------------------------------------------------------------
# count
# ---------------------------------------------------------------------------


class TestCount:
    """count() returns the number of pending samples."""

    def test_count_empty_spool(self, tmp_path: Path) -> None:
        """AC5: count is 0 on a freshly created spool."""
        spool = Spool(path=tmp_path / "spool.db")

        assert spool.count() == 0
        spool.close()

    def test_count_after_enqueue(self, tmp_path: Path) -> None:
        """AC5: count reflects number of enqueued samples."""
        spool = Spool(path=tmp_path / "spool.db")
        spool.enqueue(_make_sample(ts="2026-02-13T10:00:00Z"))
        spool.enqueue(_make_sample(ts="2026-02-13T10:00:01Z"))
        spool.enqueue(_make_sample(ts="2026-02-13T10:00:02Z"))

        assert spool.count() == 3
        spool.close()

    def test_count_after_ack(self, tmp_path: Path) -> None:
        """AC5: count decreases after ack."""
        spool = Spool(path=tmp_path / "spool.db")
        spool.enqueue(_make_sample(ts="2026-02-13T10:00:00Z"))
        spool.enqueue(_make_sample(ts="2026-02-13T10:00:01Z"))

        rows = spool.peek(2)
        spool.ack([rows[0]["rowid"]])

        assert spool.count() == 1
        spool.close()

    def test_count_reflects_actual_pending_after_enqueue_and_ack(
        self, tmp_path: Path
    ) -> None:
        """AC5: count is accurate after mixed enqueue/ack operations."""
        spool = Spool(path=tmp_path / "spool.db")

        # Enqueue 5
        for i in range(5):
            spool.enqueue(_make_sample(ts=f"2026-02-13T10:00:0{i}Z"))
        assert spool.count() == 5

        # Ack 2
        rows = spool.peek(2)
        spool.ack([r["rowid"] for r in rows])
        assert spool.count() == 3

        # Enqueue 1 more
        spool.enqueue(_make_sample(ts="2026-02-13T10:00:05Z"))
        assert spool.count() == 4

        spool.close()


# ---------------------------------------------------------------------------
# Persistence across restarts
# ---------------------------------------------------------------------------


class TestPersistence:
    """Spool DB file persists data across process restarts (re-instantiation)."""

    def test_data_persists_after_close_and_reopen(
        self, tmp_path: Path
    ) -> None:
        """AC6: Samples survive closing and reopening the spool."""
        db_path = tmp_path / "persist.db"

        # First "process"
        spool1 = Spool(path=db_path)
        spool1.enqueue(
            _make_sample(device_id="persist-test", ts="2026-02-13T10:00:00Z")
        )
        spool1.enqueue(
            _make_sample(device_id="persist-test", ts="2026-02-13T10:00:01Z")
        )
        spool1.close()

        # Second "process" — simulates restart
        spool2 = Spool(path=db_path)
        assert spool2.count() == 2

        rows = spool2.peek(10)
        assert len(rows) == 2
        assert rows[0]["device_id"] == "persist-test"
        assert rows[0]["ts"] == "2026-02-13T10:00:00Z"
        assert rows[1]["ts"] == "2026-02-13T10:00:01Z"
        spool2.close()

    def test_ack_persists_after_close_and_reopen(
        self, tmp_path: Path
    ) -> None:
        """AC6: Acknowledged (deleted) rows stay deleted after restart."""
        db_path = tmp_path / "ack_persist.db"

        # First process: enqueue 3, ack 1
        spool1 = Spool(path=db_path)
        for i in range(3):
            spool1.enqueue(
                _make_sample(ts=f"2026-02-13T10:00:0{i}Z")
            )
        rows = spool1.peek(1)
        spool1.ack([rows[0]["rowid"]])
        spool1.close()

        # Second process: only 2 should remain
        spool2 = Spool(path=db_path)
        assert spool2.count() == 2

        remaining = spool2.peek(10)
        assert remaining[0]["ts"] == "2026-02-13T10:00:01Z"
        spool2.close()


# ---------------------------------------------------------------------------
# Schema validation (AC7)
# ---------------------------------------------------------------------------


class TestSchema:
    """Table schema matches specification from technicaldesign.md."""

    def test_table_has_expected_columns(self, tmp_path: Path) -> None:
        """AC7: spool table has the documented columns with correct types."""
        import sqlite3

        db_path = tmp_path / "schema_test.db"
        spool = Spool(path=db_path)

        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("PRAGMA table_info(spool);")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        conn.close()

        assert "device_id" in columns
        assert "ts" in columns
        assert "power_w" in columns
        assert "import_power_w" in columns
        assert "energy_import_kwh" in columns
        assert "energy_export_kwh" in columns
        assert "created_at" in columns

        # Verify types
        assert columns["device_id"] == "TEXT"
        assert columns["ts"] == "TEXT"
        assert columns["power_w"] == "INTEGER"
        assert columns["import_power_w"] == "INTEGER"
        assert columns["energy_import_kwh"] == "REAL"
        assert columns["energy_export_kwh"] == "REAL"
        assert columns["created_at"] == "TEXT"

        spool.close()

    def test_rowid_is_autoincrement(self, tmp_path: Path) -> None:
        """AC7: rowid uses AUTOINCREMENT (never reused after deletion)."""
        spool = Spool(path=tmp_path / "autoincrement.db")

        spool.enqueue(_make_sample(ts="2026-02-13T10:00:00Z"))
        spool.enqueue(_make_sample(ts="2026-02-13T10:00:01Z"))
        rows = spool.peek(2)
        first_rowid = rows[0]["rowid"]
        second_rowid = rows[1]["rowid"]

        # Delete the first row
        spool.ack([first_rowid])

        # Insert a new row — its rowid should be higher than the second
        spool.enqueue(_make_sample(ts="2026-02-13T10:00:02Z"))
        all_rows = spool.peek(10)
        new_rowid = all_rows[-1]["rowid"]

        assert new_rowid > second_rowid
        spool.close()

    def test_created_at_is_auto_populated(self, tmp_path: Path) -> None:
        """AC7: created_at column is automatically populated."""
        spool = Spool(path=tmp_path / "created_at.db")
        spool.enqueue(_make_sample())

        rows = spool.peek(1)
        # created_at should be a non-empty string (datetime)
        assert rows[0].get("created_at") is not None
        assert isinstance(rows[0]["created_at"], str)
        assert len(rows[0]["created_at"]) > 0
        spool.close()
