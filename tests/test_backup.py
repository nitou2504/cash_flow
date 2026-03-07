import unittest
import sqlite3
import tempfile
import os
from pathlib import Path
from datetime import date, datetime, timedelta
from unittest.mock import patch

from cashflow.backup import (
    create_backup, list_backups, restore_backup, auto_backup,
    apply_retention, BACKUP_PREFIX, BACKUP_EXT,
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
        self.assertTrue(path.name.endswith(BACKUP_EXT))

        # Verify backup is valid sqlite with same data
        conn = sqlite3.connect(str(path))
        row = conn.execute("SELECT value FROM test WHERE id=1").fetchone()
        conn.close()
        self.assertEqual(row[0], "hello")

    def test_list_backups(self):
        create_backup(self.db_path, self.backup_dir)
        backups = list_backups(self.backup_dir)
        self.assertEqual(len(backups), 1)
        self.assertIn("path", backups[0])
        self.assertIn("datetime", backups[0])
        self.assertIn("size", backups[0])

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

    def test_auto_backup_creates_and_applies_retention(self):
        path = auto_backup(self.db_path, self.backup_dir, keep_today=5, recent_days=7, max_days=30)
        self.assertTrue(path.exists())
        backups = list_backups(self.backup_dir)
        self.assertEqual(len(backups), 1)


if __name__ == "__main__":
    unittest.main()
