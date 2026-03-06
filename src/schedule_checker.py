"""
schedule_checker.py
────────────────────
Reads schedule_config.json and decides whether the agent should run today
and at what time. Called at the start of agent.py before any work is done.

Flow:
  1. Workflow cron fires at the EARLIEST configured time (auto-calculated)
  2. schedule_checker determines if today is an active day
  3. If yes, sleeps until the correct IST time for today, then returns
  4. If no (paused / skip date / disabled day), exits with code 0 (clean skip)
"""

import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from logger import get_logger

log = get_logger("schedule")

CONFIG_FILE = "schedule_config.json"

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]  # weekday() 0=Mon


def load_config() -> dict:
    """Load schedule_config.json. Returns defaults if file missing."""
    defaults = {
        "paused": False,
        "pause_until": None,
        "weekly": {
            d: {"enabled": True, "time_ist": "09:30"} for d in DAYS
        },
        "skip_dates": [],
        "force_dates": [],
    }
    path = Path(CONFIG_FILE)
    if not path.exists():
        log.info("schedule_config.json not found — using defaults (post every day 09:30 IST)")
        return defaults
    try:
        with open(path) as f:
            cfg = json.load(f)
        # Merge with defaults so missing keys don't crash
        for day in DAYS:
            if day not in cfg.get("weekly", {}):
                cfg.setdefault("weekly", {})[day] = defaults["weekly"][day]
        return {**defaults, **cfg}
    except Exception as e:
        log.warning(f"Could not parse schedule_config.json ({e}) — using defaults")
        return defaults


def ist_now() -> datetime:
    """Current datetime in IST (UTC+5:30) as a naive datetime."""
    return datetime.utcnow() + timedelta(hours=5, minutes=30)


def check_and_wait(dry_run: bool = False) -> None:
    """
    Main entry point called by agent.py.
    Either sleeps until the right time, or calls sys.exit(0) to skip cleanly.
    """
    cfg    = load_config()
    now    = ist_now()
    today  = now.strftime("%Y-%m-%d")
    day_key = DAYS[now.weekday()]  # 0=Mon … 6=Sun

    # ── 1. CHECK PAUSE ────────────────────────────────────────────────────────
    if cfg["paused"]:
        resume = cfg.get("pause_until")
        if resume and today >= resume:
            log.info(f"Pause expired (resume date: {resume}) — proceeding normally")
        else:
            reason = f"until {resume}" if resume else "indefinitely"
            log.info(f"⏸️  Posting is paused {reason}. Exiting cleanly.")
            sys.exit(0)

    # ── 2. CHECK FORCE DATE (overrides everything else) ───────────────────────
    is_forced = today in cfg.get("force_dates", [])
    if is_forced:
        log.info(f"📌 {today} is a force-run date — will post regardless of day settings")

    # ── 3. CHECK SKIP DATE ────────────────────────────────────────────────────
    if today in cfg.get("skip_dates", []) and not is_forced:
        log.info(f"🚫 {today} is in skip_dates. Exiting cleanly.")
        sys.exit(0)

    # ── 4. CHECK WEEKLY DAY ───────────────────────────────────────────────────
    day_cfg = cfg["weekly"].get(day_key, {"enabled": True, "time_ist": "09:30"})
    if not day_cfg.get("enabled", True) and not is_forced:
        log.info(f"📅 {day_key.capitalize()} is disabled in weekly schedule. Exiting cleanly.")
        sys.exit(0)

    # ── 5. SLEEP UNTIL SCHEDULED TIME ────────────────────────────────────────
    if dry_run:
        log.info("Dry run — skipping schedule time check")
        return

    time_ist = day_cfg.get("time_ist", "09:30")
    try:
        sched_h, sched_m = map(int, time_ist.split(":"))
    except Exception:
        log.warning(f"Invalid time_ist '{time_ist}' — defaulting to 09:30")
        sched_h, sched_m = 9, 30

    target = now.replace(hour=sched_h, minute=sched_m, second=0, microsecond=0)

    if now < target:
        wait_secs = (target - now).total_seconds()
        wait_mins = int(wait_secs // 60)
        log.info(f"⏱️  Waiting {wait_mins}m until scheduled time {time_ist} IST ...")
        # Sleep in chunks so logs stay alive
        chunk = 60  # seconds
        while wait_secs > 0:
            time.sleep(min(chunk, wait_secs))
            wait_secs -= chunk
            if wait_secs > 60:
                remaining = int(wait_secs // 60)
                log.info(f"   ... {remaining}m remaining")
        log.info(f"✅ Reached scheduled time {time_ist} IST — starting agent")
    elif (now - target).total_seconds() > 3600:
        # Workflow fired more than 1h after scheduled time — probably a manual trigger
        log.info(f"⚠️  Current IST time ({now.strftime('%H:%M')}) is >1h past scheduled {time_ist} — running anyway (manual trigger?)")
    else:
        log.info(f"✅ Within 1h window of {time_ist} IST — proceeding")


if __name__ == "__main__":
    # Quick test: print what would happen right now
    cfg = load_config()
    now = ist_now()
    today = now.strftime("%Y-%m-%d")
    day_key = DAYS[now.weekday()]
    print(f"Now (IST):   {now.strftime('%Y-%m-%d %H:%M')}")
    print(f"Day:         {day_key}")
    print(f"Paused:      {cfg['paused']}")
    print(f"Skip dates:  {cfg['skip_dates']}")
    print(f"Force dates: {cfg['force_dates']}")
    print(f"Today enabled: {cfg['weekly'][day_key]['enabled']}")
    print(f"Today time:    {cfg['weekly'][day_key]['time_ist']} IST")
