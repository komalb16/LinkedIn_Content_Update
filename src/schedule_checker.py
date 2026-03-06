"""
schedule_checker.py  ─  place this at src/schedule_checker.py
────────────────────────────────────────────────────────────────
Reads schedule_config.json and decides whether the agent should run today
and at what time. Called at the start of agent.py before any work is done.

Flow:
  1. Workflow cron fires at a fixed early time (e.g. 3:00 AM UTC / 8:30 IST)
  2. schedule_checker reads schedule_config.json from the repo root
  3. If paused / skip date / disabled day → exits cleanly (code 0, no post)
  4. If active day → sleeps until the per-day IST time configured for today
  5. Returns so agent.py can proceed with posting

IMPORTANT: This file must be at src/schedule_checker.py (same folder as agent.py).
           If it's in the repo root or missing, agent.py will log a warning and
           post anyway (no schedule enforcement).
"""

import json
import sys
import time
import os
from datetime import datetime, timedelta
from pathlib import Path

# ─── Try to import logger, fall back to print ────────────────────────────────
try:
    from logger import get_logger
    log = get_logger("schedule")
    def info(msg):  log.info(msg)
    def warn(msg):  log.warning(msg)
except Exception:
    def info(msg):  print(f"[schedule] {msg}")
    def warn(msg):  print(f"[schedule] WARNING: {msg}")


DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]  # weekday() 0=Mon


def _find_config() -> Path:
    """
    Look for schedule_config.json in several locations:
      1. Current working directory (repo root when run via GitHub Actions)
      2. Parent of this script's directory
      3. This script's directory
    """
    candidates = [
        Path("schedule_config.json"),               # repo root (most common)
        Path(__file__).parent.parent / "schedule_config.json",  # one level up from src/
        Path(__file__).parent / "schedule_config.json",          # same dir as script
    ]
    for p in candidates:
        if p.exists():
            info(f"Found schedule_config.json at: {p}")
            return p
    return Path("schedule_config.json")  # will trigger "not found" path


def load_config() -> dict:
    """Load schedule_config.json. Returns permissive defaults if file missing."""
    defaults = {
        "paused": False,
        "pause_until": None,
        "weekly": {d: {"enabled": True, "time_ist": "09:30"} for d in DAYS},
        "skip_dates": [],
        "force_dates": [],
    }
    path = _find_config()
    if not path.exists():
        warn("schedule_config.json not found — using defaults (post every day at 09:30 IST)")
        info("  → To control scheduling, save your config from the dashboard")
        return defaults
    try:
        with open(path) as f:
            cfg = json.load(f)
        # Merge with defaults so missing keys never cause KeyErrors
        merged = {**defaults, **cfg}
        for day in DAYS:
            if day not in merged.get("weekly", {}):
                merged.setdefault("weekly", {})[day] = defaults["weekly"][day]
        return merged
    except Exception as e:
        warn(f"Could not parse schedule_config.json ({e}) — using defaults")
        return defaults


def ist_now() -> datetime:
    """Current datetime in IST (UTC+5:30) as a naive datetime."""
    return datetime.utcnow() + timedelta(hours=5, minutes=30)


def check_and_wait(dry_run: bool = False, manual: bool = False) -> None:
    """
    manual=True  → workflow_dispatch: skip sleep, run immediately.
    dry_run=True → also skips sleep.
    Cron (scheduled) triggers: sleep until configured time.
    """
    cfg     = load_config()
    now     = ist_now()
    today   = now.strftime("%Y-%m-%d")
    day_key = DAYS[now.weekday()]   # 0=Mon … 6=Sun

    trigger = "MANUAL" if manual else ("DRY-RUN" if dry_run else "SCHEDULED")
    info(f"Schedule check — {today} ({day_key.upper()}) — IST {now.strftime('%H:%M')} — trigger: {trigger}")

    # ── 1. PAUSE CHECK ────────────────────────────────────────────────────────
    if cfg["paused"]:
        resume = cfg.get("pause_until")
        if resume and today >= resume:
            info(f"Pause expired (resume date was {resume}) — proceeding normally")
        else:
            reason = f"until {resume}" if resume else "indefinitely"
            info(f"⏸️  Posting is PAUSED {reason}. Skipping today. Exiting cleanly.")
            sys.exit(0)

    # ── 2. FORCE DATE (overrides disabled days and skip dates) ───────────────
    is_forced = today in cfg.get("force_dates", [])
    if is_forced:
        info(f"📌 {today} is a force-run date — overriding all other settings")

    # ── 3. SKIP DATE ─────────────────────────────────────────────────────────
    if today in cfg.get("skip_dates", []) and not is_forced:
        info(f"🚫 {today} is in skip_dates. Skipping today. Exiting cleanly.")
        sys.exit(0)

    # ── 4. WEEKLY DAY ENABLED ─────────────────────────────────────────────────
    day_cfg = cfg["weekly"].get(day_key, {"enabled": True, "time_ist": "09:30"})
    if not day_cfg.get("enabled", True) and not is_forced:
        info(f"📅 {day_key.capitalize()} is disabled in weekly schedule. Exiting cleanly.")
        sys.exit(0)

    # ── 5. SLEEP UNTIL SCHEDULED TIME (only for cron triggers) ─────────────────
    if dry_run or manual:
        info(f"Skipping time-of-day sleep ({trigger}) — running immediately")
        return

    time_ist = day_cfg.get("time_ist", "09:30")
    try:
        sched_h, sched_m = map(int, time_ist.split(":"))
    except Exception:
        warn(f"Invalid time_ist value '{time_ist}' — defaulting to 09:30")
        sched_h, sched_m = 9, 30

    target = now.replace(hour=sched_h, minute=sched_m, second=0, microsecond=0)
    diff_secs = (target - now).total_seconds()

    if diff_secs > 0:
        wait_mins = int(diff_secs // 60)
        info(f"⏱️  Waiting {wait_mins}m until {time_ist} IST...")
        # Sleep in 60-second chunks so GitHub Actions logs stay alive
        remaining = diff_secs
        while remaining > 0:
            time.sleep(min(60, remaining))
            remaining -= 60
            if remaining > 60:
                info(f"   ... {int(remaining // 60)}m remaining until {time_ist} IST")
        info(f"✅ Reached scheduled time {time_ist} IST — starting agent")
    elif diff_secs < -3600:
        # Triggered more than 1h late — probably a manual re-run or GitHub delay
        info(f"⚠️  Now ({now.strftime('%H:%M')} IST) is >1h past {time_ist} IST — running anyway")
    else:
        info(f"✅ Within 1h window of {time_ist} IST — proceeding")


# ─── Quick diagnostic (python src/schedule_checker.py) ───────────────────────
if __name__ == "__main__":
    cfg     = load_config()
    now     = ist_now()
    today   = now.strftime("%Y-%m-%d")
    day_key = DAYS[now.weekday()]

    print("\n" + "=" * 50)
    print("  schedule_checker.py — diagnostic")
    print("=" * 50)
    print(f"  Now (IST):      {now.strftime('%Y-%m-%d %H:%M')}")
    print(f"  Day:            {day_key}")
    print(f"  Paused:         {cfg['paused']}")
    print(f"  Pause until:    {cfg.get('pause_until') or '(none)'}")
    print(f"  Today skip:     {today in cfg.get('skip_dates', [])}")
    print(f"  Today force:    {today in cfg.get('force_dates', [])}")
    print(f"  Day enabled:    {cfg['weekly'][day_key]['enabled']}")
    print(f"  Scheduled time: {cfg['weekly'][day_key]['time_ist']} IST")
    print("=" * 50)

    would_run = (
        not cfg["paused"] and
        today not in cfg.get("skip_dates", []) and
        (cfg["weekly"][day_key]["enabled"] or today in cfg.get("force_dates", []))
    )
    print(f"\n  → Would post today: {'YES ✅' if would_run else 'NO ⏸️'}\n")
