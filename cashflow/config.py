import os
from dotenv import load_dotenv

load_dotenv()

# Cash Flow
DB_PATH = "cash_flow.db"

# Backup
BACKUP_ENABLED = os.getenv("BACKUP_ENABLED", "true").lower() in ("true", "1", "yes")
BACKUP_DIR = os.getenv("BACKUP_DIR", "backups")
BACKUP_KEEP_TODAY = int(os.getenv("BACKUP_KEEP_TODAY", "5"))
BACKUP_RECENT_DAYS = int(os.getenv("BACKUP_RECENT_DAYS", "7"))
BACKUP_MAX_DAYS = int(os.getenv("BACKUP_MAX_DAYS", "30"))
BACKUP_LOG_RETENTION_DAYS = int(os.getenv("BACKUP_LOG_RETENTION_DAYS", "30"))

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
_allowed_raw = os.getenv("TELEGRAM_ALLOWED_USERS", "")
TELEGRAM_ALLOWED_USERS: set[int] = {
    int(uid.strip()) for uid in _allowed_raw.split(",") if uid.strip()
}
