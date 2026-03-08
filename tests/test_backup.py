import unittest
import sqlite3
import tempfile
import os
from pathlib import Path
from datetime import date, datetime, timedelta
from unittest.mock import patch

from cashflow.backup import (
    create_backup, list_backups, restore_backup, auto_backup,
    apply_retention, write_backup_log, apply_log_retention,
    _slugify, _is_manual_backup, _parse_backup_datetime,
    BACKUP_PREFIX, MANUAL_PREFIX, BACKUP_EXT, BACKUP_LOG,
)


class TestBackup(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test.db")
        self.backup_dir = os.path.join(self.tmpdir, "backups")

        # Create a test DB with some data
        conn = sqlite3.connect(self.db_path)
        conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO test VALUES (1, 'hello')")
        conn.commit()
        conn.close()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_create_backup(self):
        path = create_backup(self.db_path, self.backup_dir)
        self.assertTrue(path.exists())
        self.assertTrue(path.name.startswith(BACKUP_PREFIX))
        self.assertFalse(path.name.startswith(MANUAL_PREFIX))
        self.assertTrue(path.name.endswith(BACKUP_EXT))

        # Verify backup is valid sqlite with same data
        conn = sqlite3.connect(str(path))
        row = conn.execute("SELECT value FROM test WHERE id=1").fetchone()
        conn.close()
        self.assertEqual(row[0], "hello")

    def test_create_manual_backup_unnamed(self):
        path = create_backup(self.db_path, self.backup_dir, manual=True)
        self.assertTrue(path.exists())
        self.assertTrue(path.name.startswith(MANUAL_PREFIX))
        self.assertTrue(path.name.endswith(BACKUP_EXT))
        # No slug after microseconds
        stem = path.stem
        ts_part = stem[len(MANUAL_PREFIX):]
        # Should be just timestamp: YYYYMMDD_HHMMSS_ffffff
        self.assertRegex(ts_part, r'^\d{8}_\d{6}_\d{6}$')

    def test_create_manual_backup_named(self):
        path = create_backup(self.db_path, self.backup_dir, manual=True, name="pre-migration")
        self.assertTrue(path.exists())
        self.assertTrue(path.name.startswith(MANUAL_PREFIX))
        self.assertIn("_pre_migration", path.name)
        self.assertTrue(path.name.endswith(BACKUP_EXT))

    def test_slugify(self):
        self.assertEqual(_slugify("pre-migration"), "pre_migration")
        self.assertEqual(_slugify("  Hello World!  "), "hello_world")
        self.assertEqual(_slugify("test@#$%123"), "test_123")
        # Length cap at 50
        long_name = "a" * 100
        self.assertEqual(len(_slugify(long_name)), 50)

    def test_is_manual_backup(self):
        self.assertTrue(_is_manual_backup("cash_flow_manual_20260307_143625_123456.db"))
        self.assertTrue(_is_manual_backup("cash_flow_manual_20260307_143625_123456_pre_migration.db"))
        self.assertFalse(_is_manual_backup("cash_flow_20260307_143625_123456.db"))
        self.assertFalse(_is_manual_backup("other_file.db"))

    def test_parse_datetime_manual(self):
        # unnamed manual
        dt = _parse_backup_datetime("cash_flow_manual_20260307_143625_123456.db")
        self.assertIsNotNone(dt)
        self.assertEqual(dt.year, 2026)
        self.assertEqual(dt.month, 3)
        self.assertEqual(dt.day, 7)
        self.assertEqual(dt.hour, 14)

        # named manual
        dt = _parse_backup_datetime("cash_flow_manual_20260307_143625_123456_pre_migration.db")
        self.assertIsNotNone(dt)
        self.assertEqual(dt.year, 2026)

        # auto
        dt = _parse_backup_datetime("cash_flow_20260307_143625_123456.db")
        self.assertIsNotNone(dt)
        self.assertEqual(dt.year, 2026)

    def test_list_backups(self):
        create_backup(self.db_path, self.backup_dir)
        backups = list_backups(self.backup_dir)
        self.assertEqual(len(backups), 1)
        self.assertIn("path", backups[0])
        self.assertIn("datetime", backups[0])
        self.assertIn("size", backups[0])

    def test_list_backups_manual_flag(self):
        create_backup(self.db_path, self.backup_dir)
        create_backup(self.db_path, self.backup_dir, manual=True)
        create_backup(self.db_path, self.backup_dir, manual=True, name="test")
        backups = list_backups(self.backup_dir)
        self.assertEqual(len(backups), 3)
        manual_flags = [b["manual"] for b in backups]
        self.assertEqual(manual_flags.count(True), 2)
        self.assertEqual(manual_flags.count(False), 1)

    def test_list_backups_empty(self):
        backups = list_backups(self.backup_dir)
        self.assertEqual(len(backups), 0)

    def test_restore_backup(self):
        backup_path = create_backup(self.db_path, self.backup_dir)

        # Modify the live DB
        conn = sqlite3.connect(self.db_path)
        conn.execute("UPDATE test SET value='modified' WHERE id=1")
        conn.commit()
        conn.close()

        # Verify it's modified
        conn = sqlite3.connect(self.db_path)
        row = conn.execute("SELECT value FROM test WHERE id=1").fetchone()
        conn.close()
        self.assertEqual(row[0], "modified")

        # Restore
        pre_restore = restore_backup(str(backup_path), self.db_path, self.backup_dir)
        self.assertTrue(pre_restore.exists())

        # Verify restored
        conn = sqlite3.connect(self.db_path)
        row = conn.execute("SELECT value FROM test WHERE id=1").fetchone()
        conn.close()
        self.assertEqual(row[0], "hello")

        # Verify pre-restore backup contains the modified data
        conn = sqlite3.connect(str(pre_restore))
        row = conn.execute("SELECT value FROM test WHERE id=1").fetchone()
        conn.close()
        self.assertEqual(row[0], "modified")

    def test_restore_creates_manual_pre_restore(self):
        backup_path = create_backup(self.db_path, self.backup_dir)
        pre_restore = restore_backup(str(backup_path), self.db_path, self.backup_dir)
        # Pre-restore backup should be manual
        self.assertTrue(pre_restore.name.startswith(MANUAL_PREFIX))
        self.assertIn("pre_restore", pre_restore.name)

    def test_restore_nonexistent(self):
        with self.assertRaises(FileNotFoundError):
            restore_backup("/nonexistent/file.db", self.db_path, self.backup_dir)

    def test_retention_today_keeps_first_and_last_n(self):
        """Create 10 backups 'today', retention with keep_today=3 should keep first + last 3."""
        os.makedirs(self.backup_dir, exist_ok=True)
        today = date.today()
        files = []
        for i in range(10):
            ts = today.strftime("%Y%m%d") + f"_{10+i:02d}0000"
            name = f"{BACKUP_PREFIX}{ts}{BACKUP_EXT}"
            p = Path(self.backup_dir) / name
            p.write_bytes(b"x")
            files.append(p)

        apply_retention(self.backup_dir, keep_today=3, recent_days=7, max_days=30)

        remaining = sorted(f.name for f in Path(self.backup_dir).iterdir())
        # Should keep: index 0 (first), 7, 8, 9 (last 3) = 4 files
        self.assertEqual(len(remaining), 4)
        self.assertIn(files[0].name, remaining)
        self.assertIn(files[7].name, remaining)
        self.assertIn(files[8].name, remaining)
        self.assertIn(files[9].name, remaining)

    def test_retention_old_days_keep_last_per_day(self):
        """Backups from 3 days ago should keep only the last one per day."""
        os.makedirs(self.backup_dir, exist_ok=True)
        old_date = date.today() - timedelta(days=3)
        for i in range(5):
            ts = old_date.strftime("%Y%m%d") + f"_{10+i:02d}0000"
            name = f"{BACKUP_PREFIX}{ts}{BACKUP_EXT}"
            (Path(self.backup_dir) / name).write_bytes(b"x")

        apply_retention(self.backup_dir, keep_today=5, recent_days=7, max_days=30)

        remaining = list(Path(self.backup_dir).iterdir())
        self.assertEqual(len(remaining), 1)
        # Should be the last one (highest timestamp)
        self.assertIn("140000", remaining[0].name)

    def test_retention_very_old_deleted(self):
        """Backups older than max_days should be deleted entirely."""
        os.makedirs(self.backup_dir, exist_ok=True)
        old_date = date.today() - timedelta(days=60)
        ts = old_date.strftime("%Y%m%d") + "_120000"
        name = f"{BACKUP_PREFIX}{ts}{BACKUP_EXT}"
        (Path(self.backup_dir) / name).write_bytes(b"x")

        apply_retention(self.backup_dir, keep_today=5, recent_days=7, max_days=30)

        remaining = list(Path(self.backup_dir).iterdir())
        self.assertEqual(len(remaining), 0)

    def test_retention_skips_manual(self):
        """Manual backups should never be auto-deleted, even if very old."""
        os.makedirs(self.backup_dir, exist_ok=True)
        old_date = date.today() - timedelta(days=60)
        ts = old_date.strftime("%Y%m%d") + "_120000_000000"

        # Create old auto backup (should be deleted)
        auto_name = f"{BACKUP_PREFIX}{ts}{BACKUP_EXT}"
        (Path(self.backup_dir) / auto_name).write_bytes(b"x")

        # Create old manual backup (should survive)
        manual_name = f"{MANUAL_PREFIX}{ts}{BACKUP_EXT}"
        (Path(self.backup_dir) / manual_name).write_bytes(b"x")

        # Create old named manual backup (should survive)
        named_manual = f"{MANUAL_PREFIX}{ts}_important{BACKUP_EXT}"
        (Path(self.backup_dir) / named_manual).write_bytes(b"x")

        apply_retention(self.backup_dir, keep_today=5, recent_days=7, max_days=30)

        remaining = sorted(f.name for f in Path(self.backup_dir).iterdir())
        # Auto backup deleted, both manual backups survive
        self.assertEqual(len(remaining), 2)
        self.assertIn(manual_name, remaining)
        self.assertIn(named_manual, remaining)

    def test_write_backup_log(self):
        os.makedirs(self.backup_dir, exist_ok=True)
        write_backup_log(self.backup_dir, "cash_flow_20260307_120000_000000.db", "add groceries")
        log_path = Path(self.backup_dir) / BACKUP_LOG
        self.assertTrue(log_path.exists())
        content = log_path.read_text()
        self.assertIn("cash_flow_20260307_120000_000000.db", content)
        self.assertIn("add groceries", content)
        # Format: timestamp | filename | operation
        lines = content.strip().split("\n")
        self.assertEqual(len(lines), 1)
        parts = lines[0].split(" | ")
        self.assertEqual(len(parts), 3)

    def test_write_backup_log_appends(self):
        os.makedirs(self.backup_dir, exist_ok=True)
        write_backup_log(self.backup_dir, "file1.db", "op1")
        write_backup_log(self.backup_dir, "file2.db", "op2")
        log_path = Path(self.backup_dir) / BACKUP_LOG
        lines = log_path.read_text().strip().split("\n")
        self.assertEqual(len(lines), 2)

    def test_log_retention(self):
        os.makedirs(self.backup_dir, exist_ok=True)
        log_path = Path(self.backup_dir) / BACKUP_LOG
        old_date = (date.today() - timedelta(days=40)).strftime("%Y-%m-%d")
        recent_date = date.today().strftime("%Y-%m-%d")
        with open(log_path, "w") as f:
            f.write(f"{old_date} 12:00:00 | old_file.db | old operation\n")
            f.write(f"{recent_date} 12:00:00 | new_file.db | new operation\n")
            f.write("unparseable line\n")

        apply_log_retention(self.backup_dir, max_days=30)

        content = log_path.read_text()
        lines = content.strip().split("\n")
        # Old entry removed, recent + unparseable kept
        self.assertEqual(len(lines), 2)
        self.assertNotIn("old_file.db", content)
        self.assertIn("new_file.db", content)
        self.assertIn("unparseable line", content)

    def test_log_retention_no_file(self):
        """apply_log_retention should not fail if log doesn't exist."""
        apply_log_retention(self.backup_dir, max_days=30)  # should not raise

    def test_auto_backup_creates_and_applies_retention(self):
        path = auto_backup(self.db_path, self.backup_dir, keep_today=5, recent_days=7, max_days=30)
        self.assertTrue(path.exists())
        backups = list_backups(self.backup_dir)
        self.assertEqual(len(backups), 1)

    def test_auto_backup_writes_log(self):
        path = auto_backup(self.db_path, self.backup_dir, keep_today=5, recent_days=7, max_days=30,
                           operation="add groceries")
        log_path = Path(self.backup_dir) / BACKUP_LOG
        self.assertTrue(log_path.exists())
        content = log_path.read_text()
        self.assertIn(path.name, content)
        self.assertIn("add groceries", content)

    def test_auto_backup_default_operation(self):
        auto_backup(self.db_path, self.backup_dir, keep_today=5, recent_days=7, max_days=30)
        log_path = Path(self.backup_dir) / BACKUP_LOG
        content = log_path.read_text()
        self.assertIn("auto", content)


if __name__ == "__main__":
    unittest.main()
