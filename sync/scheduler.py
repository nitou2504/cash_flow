import asyncio
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

EC_TZ = timezone(timedelta(hours=-5))
SYNC_HOURS = (0, 12)

_lock = asyncio.Lock()
_last_sync: dict | None = None
_running = False
_next_run: str | None = None


def _next_sync_time() -> tuple[float, datetime]:
    now = datetime.now(EC_TZ)
    candidates = []
    for h in SYNC_HOURS:
        t = now.replace(hour=h, minute=0, second=0, microsecond=0)
        if t <= now:
            t += timedelta(days=1)
        candidates.append(t)
    nxt = min(candidates)
    return (nxt - now).total_seconds(), nxt


def get_last_sync() -> dict:
    return {
        "last_run": _last_sync.get("timestamp") if _last_sync else None,
        "summary": _last_sync.get("summary") if _last_sync else None,
        "running": _running,
        "next_run": _next_run,
    }


async def trigger_sync() -> dict:
    global _last_sync, _running
    if _running:
        raise RuntimeError("Sync already running")
    async with _lock:
        _running = True
        try:
            from gmail_sync.scheduled import _run_sync
            summary = await asyncio.to_thread(_run_sync)
            _last_sync = {
                "timestamp": datetime.now(EC_TZ).isoformat(),
                "summary": summary,
            }
            return summary
        finally:
            _running = False


async def _sync_loop():
    global _next_run
    while True:
        delay, nxt = _next_sync_time()
        _next_run = nxt.isoformat()
        logger.info("Next Gmail sync at %s (in %.0f min)", _next_run, delay / 60)
        await asyncio.sleep(delay)
        try:
            summary = await trigger_sync()
            logger.info("Scheduled sync done: %s", summary)
        except RuntimeError:
            logger.info("Skipped scheduled sync — already running")
        except Exception:
            logger.exception("Scheduled sync failed")


def start_scheduler() -> asyncio.Task:
    return asyncio.create_task(_sync_loop())
