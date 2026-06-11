"""
scheduler.py — Runs the agent on a market-hours schedule.

Sessions fire at:
  09:35 AM ET — opening session (after early volatility settles)
  03:50 PM ET — closing session (before market close)

Position monitor fires every 5 minutes during market hours to check
stop-loss and take-profit levels.

Keep this running in a separate terminal:
  python scheduler.py

Or run as a background process:
  nohup python scheduler.py >> logs/scheduler.log 2>&1 &
  ps aux | grep scheduler   # verify it's running
"""

import time
import logging
import datetime
import zoneinfo
from pathlib import Path

from agent import run_session
import memory

Path("logs").mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler("logs/scheduler.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

ET = zoneinfo.ZoneInfo("America/New_York")

SESSION_TIMES = [
    datetime.time(9, 35),    # morning session — after opening volatility
    datetime.time(15, 50),   # afternoon session — before close
]

MONITOR_INTERVAL_SECS = 300   # check positions every 5 minutes
MARKET_OPEN  = datetime.time(9, 30)
MARKET_CLOSE = datetime.time(16, 0)


def _now_et() -> datetime.datetime:
    return datetime.datetime.now(ET)


def _is_market_hours() -> bool:
    t = _now_et().time()
    return MARKET_OPEN <= t <= MARKET_CLOSE and _now_et().weekday() < 5   # Mon–Fri


def _seconds_until(target_time: datetime.time) -> float:
    """Seconds until the next occurrence of target_time ET (same or next weekday)."""
    now = _now_et()
    candidate = now.replace(hour=target_time.hour, minute=target_time.minute, second=0, microsecond=0)
    if candidate <= now:
        candidate += datetime.timedelta(days=1)
    # Skip weekends
    while candidate.weekday() >= 5:
        candidate += datetime.timedelta(days=1)
    return (candidate - now).total_seconds()


def _next_session_time() -> datetime.time | None:
    """Return the next upcoming session time today, or None if past all sessions."""
    now_t = _now_et().time()
    for t in SESSION_TIMES:
        if t > now_t:
            return t
    return None


def _should_run_session(label: str, last_ran: dict) -> bool:
    today = _now_et().date().isoformat()
    return last_ran.get(label) != today


def _mark_ran(label: str, last_ran: dict):
    last_ran[label] = _now_et().date().isoformat()


def run_monitor():
    """Check open positions for stop-loss / take-profit (non-trading, read-only scan)."""
    from agent import check_positions
    try:
        check_positions()
    except Exception as e:
        log.error(f"[monitor] Error: {e}")


def main():
    memory.init_db()
    last_ran: dict[str, str] = {}
    log.info("Scheduler started — sessions at 09:35 and 15:50 ET")

    while True:
        now = _now_et()

        # ── Full sessions ──────────────────────────────────────────────────────
        for session_time in SESSION_TIMES:
            label = session_time.strftime("%H:%M")
            diff_secs = abs((now.replace(
                hour=session_time.hour, minute=session_time.minute,
                second=0, microsecond=0
            ) - now).total_seconds())

            if diff_secs < 60 and _should_run_session(label, last_ran):
                log.info(f"[{label}] Firing session")
                try:
                    run_session()
                    _mark_ran(label, last_ran)
                    log.info(f"[{label}] Session complete")
                except Exception as e:
                    log.error(f"[{label}] Session failed: {e}")
                    _mark_ran(label, last_ran)   # don't retry — wait for next window

        # ── Position monitor ───────────────────────────────────────────────────
        if _is_market_hours():
            run_monitor()
            log.debug("[monitor] Position check done")

        # ── Sleep ──────────────────────────────────────────────────────────────
        if _is_market_hours():
            time.sleep(MONITOR_INTERVAL_SECS)
        else:
            # Outside market hours: sleep until 30 min before next session
            next_t = _next_session_time()
            if next_t:
                wait = _seconds_until(next_t) - 1800
            else:
                wait = _seconds_until(SESSION_TIMES[0]) - 1800
            wait = max(60, wait)
            log.info(f"Market closed — sleeping {wait/3600:.1f}h")
            time.sleep(wait)


if __name__ == "__main__":
    main()
