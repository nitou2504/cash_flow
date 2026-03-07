import sqlite3
import os
from pathlib import Path
from datetime import date, datetime
from collections import defaultdict

BACKUP_PREFIX = "cash_flow_"
BACKUP_EXT = ".db"


def _backup_dir(backup_dir: str) -> Path:
    path = Path(backup_dir)
    path.mkdir(exist_ok=True)
    return path


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def _parse_backup_datetime(filename: str) -> datetime | None:
    stem = Path(filename).stem
    if not stem.startswith(BACKUP_PREFIX):
        return None
    ts = stem[len(BACKUP_PREFIX):]
    try:
        return datetime.strptime(ts, "%Y%m%d_%H%M%S_%f")
    except ValueError:
        try:
            return datetime.strptime(ts, "%Y%m%d_%H%M%S")
        except ValueError:
            return None


def _parse_backup_date(filename: str) -> date | None:
    dt = _parse_backup_datetime(filename)
    return dt.date() if dt else None


def list_backups(backup_dir: str) -> list[dict]:
    """Return list of backups sorted by timestamp (newest first)."""
    path = _backup_dir(backup_dir)
    backups = []
    for f in path.iterdir():
        if f.suffix == BACKUP_EXT and f.name.startswith(BACKUP_PREFIX):
            dt = _parse_backup_datetime(f.name)
            if dt:
                size = f.stat().st_size
                backups.append({"path": f, "datetime": dt, "date": dt.date(), "size": size})
    backups.sort(key=lambda b: b["datetime"], reverse=True)
    return backups


def create_backup(db_path: str, backup_dir: str) -> Path:
    """Create a backup using sqlite3 backup API. Returns the backup path."""
    dest_dir = _backup_dir(backup_dir)
    dest_path = dest_dir / f"{BACKUP_PREFIX}{_timestamp()}{BACKUP_EXT}"

    src = sqlite3.connect(db_path)
    dst = sqlite3.connect(str(dest_path))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()

    return dest_path


def restore_backup(backup_path: str, db_path: str, backup_dir: str) -> Path:
    """Restore from a backup. Creates a pre-restore backup first. Returns pre-restore backup path."""
    if not os.path.exists(backup_path):
        raise FileNotFoundError(f"Backup not found: {backup_path}")

    pre_restore = create_backup(db_path, backup_dir)

    src = sqlite3.connect(backup_path)
    dst = sqlite3.connect(db_path)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()

    return pre_restore


def auto_backup(db_path: str, backup_dir: str, keep_today: int, recent_days: int, max_days: int) -> Path:
    """Create a backup and apply retention. Returns the backup path."""
    backup_path = create_backup(db_path, backup_dir)
    apply_retention(backup_dir, keep_today, recent_days, max_days)
    return backup_path


def apply_retention(backup_dir: str, keep_today: int, recent_days: int, max_days: int):
    """Apply retention policy:
    - Today: keep first + last `keep_today`
    - 1 to recent_days old: keep last per day
    - Older than max_days: delete
    - Between recent_days and max_days: keep last per day
    """
    today = date.today()
    backups = list_backups(backup_dir)

    by_date: dict[date, list[dict]] = defaultdict(list)
    for b in backups:
        by_date[b["date"]].append(b)

    to_delete = []

    for day, day_backups in by_date.items():
        age = (today - day).days
        # Sort oldest first within day
        day_backups.sort(key=lambda b: b["datetime"])

        if age > max_days:
            to_delete.extend(day_backups)
        elif age >= 1:
            # Past days: keep only the last one per day
            to_delete.extend(day_backups[:-1])
        else:
            # Today: keep first + last N
            if len(day_backups) <= keep_today + 1:
                continue
            first = day_backups[0]
            last_n = day_backups[-keep_today:]
            keep = {id(first)} | {id(b) for b in last_n}
            for b in day_backups:
                if id(b) not in keep:
                    to_delete.append(b)

    for b in to_delete:
        try:
            b["path"].unlink()
        except OSError:
            pass
