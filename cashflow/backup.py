import re
import sqlite3
import os
from pathlib import Path
from datetime import date, datetime, timedelta
from collections import defaultdict

BACKUP_PREFIX = "cash_flow_"
MANUAL_PREFIX = "cash_flow_manual_"
BACKUP_EXT = ".db"
BACKUP_LOG = "backup.log"


def _backup_dir(backup_dir: str) -> Path:
    path = Path(backup_dir)
    path.mkdir(exist_ok=True)
    return path


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def _slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r'[^a-z0-9]+', '_', slug)
    slug = slug.strip('_')
    return slug[:50]


def _is_manual_backup(filename: str) -> bool:
    return Path(filename).stem.startswith(MANUAL_PREFIX)


def _parse_backup_datetime(filename: str) -> datetime | None:
    stem = Path(filename).stem
    # Check MANUAL_PREFIX first since it also starts with BACKUP_PREFIX
    if stem.startswith(MANUAL_PREFIX):
        ts_part = stem[len(MANUAL_PREFIX):]
    elif stem.startswith(BACKUP_PREFIX):
        ts_part = stem[len(BACKUP_PREFIX):]
    else:
        return None
    # Match timestamp: YYYYMMDD_HHMMSS_ffffff (slug may follow)
    match = re.match(r'(\d{8}_\d{6}_\d{6})', ts_part)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y%m%d_%H%M%S_%f")
        except ValueError:
            pass
    match = re.match(r'(\d{8}_\d{6})', ts_part)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y%m%d_%H%M%S")
        except ValueError:
            pass
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
                backups.append({
                    "path": f, "datetime": dt, "date": dt.date(),
                    "size": size, "manual": _is_manual_backup(f.name),
                })
    backups.sort(key=lambda b: b["datetime"], reverse=True)
    return backups


def create_backup(db_path: str, backup_dir: str, *, manual: bool = False, name: str | None = None) -> Path:
    """Create a backup using sqlite3 backup API. Returns the backup path."""
    dest_dir = _backup_dir(backup_dir)
    ts = _timestamp()
    if manual:
        slug = f"_{_slugify(name)}" if name else ""
        filename = f"{MANUAL_PREFIX}{ts}{slug}{BACKUP_EXT}"
    else:
        filename = f"{BACKUP_PREFIX}{ts}{BACKUP_EXT}"
    dest_path = dest_dir / filename

    src = sqlite3.connect(db_path)
    dst = sqlite3.connect(str(dest_path))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()

    return dest_path


def restore_backup(backup_path: str, db_path: str, backup_dir: str) -> Path:
    """Restore from a backup. Creates a pre-restore manual backup first. Returns pre-restore backup path."""
    if not os.path.exists(backup_path):
        raise FileNotFoundError(f"Backup not found: {backup_path}")

    pre_restore = create_backup(db_path, backup_dir, manual=True, name="pre-restore")

    src = sqlite3.connect(backup_path)
    dst = sqlite3.connect(db_path)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()

    return pre_restore


def write_backup_log(backup_dir: str, backup_filename: str, operation: str):
    """Append an entry to the backup log file."""
    log_path = Path(backup_dir) / BACKUP_LOG
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_path, "a") as f:
        f.write(f"{timestamp} | {backup_filename} | {operation}\n")


def apply_log_retention(backup_dir: str, max_days: int):
    """Remove log entries older than max_days."""
    log_path = Path(backup_dir) / BACKUP_LOG
    if not log_path.exists():
        return
    cutoff = date.today() - timedelta(days=max_days)
    kept = []
    with open(log_path, "r") as f:
        for line in f:
            try:
                line_date = datetime.strptime(line[:10], "%Y-%m-%d").date()
                if line_date >= cutoff:
                    kept.append(line)
            except ValueError:
                kept.append(line)  # keep unparseable lines
    with open(log_path, "w") as f:
        f.writelines(kept)


def auto_backup(db_path: str, backup_dir: str, keep_today: int, recent_days: int, max_days: int,
                operation: str = "", log_retention_days: int = 30) -> Path:
    """Create a backup and apply retention. Returns the backup path."""
    backup_path = create_backup(db_path, backup_dir)
    write_backup_log(backup_dir, backup_path.name, operation or "auto")
    apply_retention(backup_dir, keep_today, recent_days, max_days)
    apply_log_retention(backup_dir, log_retention_days)
    return backup_path


def apply_retention(backup_dir: str, keep_today: int, recent_days: int, max_days: int):
    """Apply retention policy:
    - Manual backups: never auto-deleted
    - Today: keep first + last `keep_today`
    - 1 to recent_days old: keep last per day
    - Older than max_days: delete
    - Between recent_days and max_days: keep last per day
    """
    today = date.today()
    backups = list_backups(backup_dir)

    by_date: dict[date, list[dict]] = defaultdict(list)
    for b in backups:
        if b["manual"]:
            continue  # never auto-delete manual backups
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
