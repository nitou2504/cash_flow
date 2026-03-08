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
TELEGRAM_AUTO_CONFIRM = os.getenv("TELEGRAM_AUTO_CONFIRM", "extra_users_only")
TELEGRAM_DEFAULT_LANG = os.getenv("TELEGRAM_DEFAULT_LANG", "en")
if TELEGRAM_DEFAULT_LANG not in ("en", "es"):
    TELEGRAM_DEFAULT_LANG = "en"
_allowed_raw = os.getenv("TELEGRAM_ALLOWED_USERS", "")
TELEGRAM_ALLOWED_USERS: set[int] = {
    int(uid.strip()) for uid in _allowed_raw.split(",") if uid.strip()
}

# Extra users: TELEGRAM_EXTRA_USER_<NAME>=user_id,account,budget_name
# Example: TELEGRAM_EXTRA_USER_MOM=987654321,Visa Pichincha,Home Groceries
TELEGRAM_EXTRA_USERS: dict[int, dict] = {}
_extra_prefix = "TELEGRAM_EXTRA_USER_"
for key, value in os.environ.items():
    if key.startswith(_extra_prefix) and value.strip():
        name = key[len(_extra_prefix):].lower()
        parts = [p.strip() for p in value.split(",")]
        if len(parts) >= 3:
            try:
                user_id = int(parts[0])
                TELEGRAM_EXTRA_USERS[user_id] = {
                    "name": name,
                    "account": parts[1],
                    "budget": parts[2],
                }
            except ValueError:
                pass
