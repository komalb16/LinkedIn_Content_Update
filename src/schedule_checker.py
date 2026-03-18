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
from datetime import datetime, timedelta, timezone
from pathlib import Path

# zoneinfo is built-in from Python 3.9+. On older Pythons fall back to
# a UTC-only stub so the rest of the code still runs (GitHub runners use 3.11+).
try:
    from zoneinfo import ZoneInfo

    def _dst_offset_str(tz_name: str) -> str:
        """Return current UTC offset as a readable string, e.g. '-04:00 (DST)'."""
        try:
            now = datetime.now(ZoneInfo(tz_name))
            off = now.utcoffset()
            total = int(off.total_seconds())
            sign = "+" if total >= 0 else "-"
            h, m = divmod(abs(total) // 60, 60)
            dst = " (DST)" if now.dst() and now.dst().total_seconds() != 0 else ""
            return f"UTC{sign}{h:02d}:{m:02d}{dst}"
        except Exception:
            return "unknown"

    def _local_to_utc_hhmm(hhmm: str, tz_name: str) -> str:
        """Convert wall-clock HH:MM in tz_name to HH:MM UTC using TODAY's DST offset."""
        now_utc = datetime.now(timezone.utc)
        tz = ZoneInfo(tz_name)
        local_today = now_utc.astimezone(tz).replace(
            hour=int(hhmm[:2]), minute=int(hhmm[3:]), second=0, microsecond=0
        )
        utc_dt = local_today.astimezone(timezone.utc)
        return f"{utc_dt.hour:02d}:{utc_dt.minute:02d}"

    HAS_ZONEINFO = True
except ImportError:
    HAS_ZONEINFO = False
    def _dst_offset_str(tz_name): return "unknown"
    def _local_to_utc_hhmm(hhmm, tz_name): return hhmm  # fallback: treat as UTC

# ─── Try to import logger, fall back to print ────────────────────────────────
try:
    from logger import get_logger
    _log = get_logger("schedule")
    def info(msg): _log.info(msg)
    def warn(msg): _log.warning(msg)
except Exception:
    def info(msg): print(f"[schedule] {msg}")
    def warn(msg): print(f"[schedule] WARNING: {msg}")


def _mark_skip():
    """Write SKIP_RUN=true to GITHUB_OUTPUT so the YAML can cancel the run."""
    gho = os.environ.get("GITHUB_OUTPUT", "")
    if gho:
        try:
            with open(gho, "a") as fh:
                fh.write("SKIP_RUN=true\n")
        except Exception:
            pass


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


def utc_now() -> datetime:
    """Current UTC datetime (naive)."""
    return datetime.utcnow()


def _schedule_reference_tz(cfg: dict) -> str:
    weekly = cfg.get("weekly", {}) or {}
    for day in DAYS:
        tz_name = (weekly.get(day) or {}).get("time_tz")
        if tz_name:
            return tz_name
    return ""


def _schedule_now(cfg: dict):
    now_utc = utc_now()
    ref_tz = _schedule_reference_tz(cfg)
    if ref_tz and HAS_ZONEINFO:
        try:
            localized = datetime.now(timezone.utc).astimezone(ZoneInfo(ref_tz))
            return localized.replace(tzinfo=None), ref_tz
        except Exception as e:
            warn(f"Could not resolve schedule timezone '{ref_tz}' ({e}) — using UTC day resolution")
    return now_utc, ""

def ist_now() -> datetime:
    """Legacy alias — kept so old configs using time_ist still work."""
    return datetime.utcnow() + timedelta(hours=5, minutes=30)


def check_and_wait(dry_run: bool = False, manual: bool = False) -> None:
    """
    manual=True  → workflow_dispatch: skip sleep, run immediately.
    dry_run=True → also skips sleep.
    Cron (scheduled) fires every 30 min. This function:
      - Exits in ~2s if configured time is more than 30 min away
      - Sleeps the gap if within 30 min of configured time, then returns
      - Exits if more than 90 min past (already posted this window)
    """
    # Also check env var as fallback — in case --manual flag wasn't passed
    if not manual and os.environ.get("GH_EVENT_NAME") == "workflow_dispatch":
        manual = True
        info("Manual trigger detected via GH_EVENT_NAME env var")

    cfg = load_config()
    schedule_now, schedule_tz = _schedule_now(cfg)
    now = utc_now()
    today = schedule_now.strftime("%Y-%m-%d")
    day_key = DAYS[schedule_now.weekday()]

    trigger = "MANUAL" if manual else ("DRY-RUN" if dry_run else "SCHEDULED")
    tz_label = schedule_tz or "UTC"
    info(f"Schedule check — {today} ({day_key.upper()}) — {tz_label} {schedule_now.strftime('%H:%M')} — trigger: {trigger}")

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

    # Prefer time_utc (set by modern dashboard). Fall back to time_ist for
    # legacy configs — convert IST → UTC by subtracting 5h30m.
    now = utc_now()   # re-fetch as UTC for time comparison

    # ── DST-AWARE time resolution ─────────────────────────────────────────────
    # Priority 1: time_local + time_tz (set by modern dashboard, DST-safe)
    #   → convert wall-clock time in the saved timezone to UTC using TODAY's offset
    #   → 6 PM America/New_York is always 6 PM, whether DST is on or off
    # Priority 2: time_utc (fixed UTC, no DST awareness — legacy)
    # Priority 3: time_ist (oldest legacy, warn and default)
    time_local = day_cfg.get("time_local")
    time_tz    = day_cfg.get("time_tz", "")
    time_utc   = day_cfg.get("time_utc")

    if time_local and time_tz and HAS_ZONEINFO:
        try:
            time_str = _local_to_utc_hhmm(time_local, time_tz)
            info(f"Using time_local={time_local} {time_tz} → {time_str} UTC "
                 f"(DST-aware, offset today: {_dst_offset_str(time_tz)})")
        except Exception as e:
            warn(f"DST conversion failed ({e}) — falling back to time_utc")
            time_str = time_utc or "09:00"
    elif time_utc:
        time_str = time_utc
        info(f"Using time_utc={time_utc} (fixed UTC — re-save schedule for DST support)")
    else:
        raw = day_cfg.get("time_ist", "")
        warn(f"LEGACY CONFIG: time_ist='{raw}' found but no time_utc or time_local. "
             f"Open dashboard → Save Schedule to fix. Defaulting to 09:00 UTC.")
        time_str = "09:00"

    try:
        sched_h, sched_m = map(int, time_str.split(":"))
    except Exception:
        warn(f"Invalid scheduled time '{time_str}' — defaulting to 09:00 UTC")
        sched_h, sched_m = 9, 0

    target = now.replace(hour=sched_h, minute=sched_m, second=0, microsecond=0)
    diff_secs = (target - now).total_seconds()

    # Cron fires twice daily. We only proceed if within a 6-hour window
    # of the configured time. Otherwise exit cleanly (costs ~2 sec of Actions time).
    WINDOW = 4 * 60 * 60  # 4-hour window — cron fires every 8h, each covers a 4h posting slot

    if diff_secs > WINDOW:
        # Too early — a future cron will catch the right window
        mins_away = int(diff_secs // 60)
        info(f"⏭️  Not yet time — {time_str} UTC is {mins_away}m away. Exiting (next cron will check again).")
        _mark_skip()
        sys.exit(0)
    elif diff_secs > 0:
        # Within the window — sleep the remaining gap then post
        wait_mins = int(diff_secs // 60)
        wait_secs = int(diff_secs % 60)
        info(f"⏱️  Sleeping {wait_mins}m {wait_secs}s until {time_str} UTC...")
        remaining = diff_secs
        while remaining > 0:
            time.sleep(min(60, remaining))
            remaining -= 60
            if remaining > 60:
                info(f"   ... {int(remaining // 60)}m remaining until {time_str} UTC")
        info(f"✅ Reached {time_str} UTC — starting agent")
    elif diff_secs >= -WINDOW:
        # Slightly past the target (cron fired just after) — run immediately
        info(f"✅ Within window of {time_str} UTC — proceeding immediately")
    else:
        # More than 90 min past — already ran this window, skip
        mins_past = int(-diff_secs // 60)
        info(f"⏭️  {time_str} UTC was {mins_past}m ago — already handled. Exiting.")
        _mark_skip()
        sys.exit(0)


# ─── Quick diagnostic (python src/schedule_checker.py) ───────────────────────
if __name__ == "__main__":
    cfg     = load_config()
    now     = utc_now()
    today   = now.strftime("%Y-%m-%d")
    day_key = DAYS[now.weekday()]

    print("\n" + "=" * 50)
    print("  schedule_checker.py — diagnostic")
    print("=" * 50)
    print(f"  Now (UTC):      {now.strftime('%Y-%m-%d %H:%M')}")
    print(f"  Day:            {day_key}")
    print(f"  Paused:         {cfg['paused']}")
    print(f"  Pause until:    {cfg.get('pause_until') or '(none)'}")
    print(f"  Today skip:     {today in cfg.get('skip_dates', [])}")
    print(f"  Today force:    {today in cfg.get('force_dates', [])}")
    print(f"  Day enabled:    {cfg['weekly'][day_key]['enabled']}")
    time_utc = cfg["weekly"][day_key].get("time_utc") or cfg["weekly"][day_key].get("time_ist","09:30")
    print(f"  Scheduled time: {time_utc} UTC")
    print("=" * 50)

    would_run = (
        not cfg["paused"] and
        today not in cfg.get("skip_dates", []) and
        (cfg["weekly"][day_key]["enabled"] or today in cfg.get("force_dates", []))
    )
    print (f"\n  → Would post today: {'YES ✅' if would_run else 'NO ⏸️'}\n")
