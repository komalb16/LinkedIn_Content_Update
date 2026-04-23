"""
schedule_checker.py  ─  src/schedule_checker.py
────────────────────────────────────────────────────────────────
Reads schedule_config.json and decides whether the agent should
post RIGHT NOW. Called at the start of agent.py.

Design: NO SLEEP
─────────────────
The workflow cron fires every 3 hours (0 */3 * * *).
This checker reads the configured target times and asks:
  "Did any target time pass within the last 3 hours?"
If yes → return immediately (agent posts).
If no  → sys.exit(0) (clean skip).

No sleeping = no timeout issues = works for any number of slots.
Posting precision: within 3 hours of configured time (the cron window).
If you need tighter precision (e.g. ±30min), switch to a 30min cron
and set WINDOW_MINUTES=28 in the environment.

Cross-midnight handling:
  Slots after 21:00 UTC (e.g. 22:30 UTC) are checked by the
  00:00 UTC cron on the NEXT day. To handle this correctly, the
  checker also looks back into the previous day's schedule for
  any uncaught late-night slots.

Supports unlimited posting slots per day via the "times" array.
Adding new slots requires only a schedule_config.json change.
"""

import json
import sys
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from zoneinfo import ZoneInfo

    def _dst_offset_str(tz_name: str) -> str:
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

    def _local_to_utc_hhmm(hhmm: str, tz_name: str, ref_utc: datetime = None) -> str:
        """Convert wall-clock HH:MM in tz_name to HH:MM UTC, DST-aware."""
        ref = ref_utc or datetime.now(timezone.utc)
        tz = ZoneInfo(tz_name)
        local_today = ref.astimezone(tz).replace(
            hour=int(hhmm[:2]), minute=int(hhmm[3:]), second=0, microsecond=0
        )
        return local_today.astimezone(timezone.utc).strftime("%H:%M")

    HAS_ZONEINFO = True
except ImportError:
    HAS_ZONEINFO = False
    def _dst_offset_str(tz_name): return "unknown"
    def _local_to_utc_hhmm(hhmm, tz_name, ref_utc=None): return hhmm

try:
    from logger import get_logger
    _log = get_logger("schedule")
    def info(msg): _log.info(msg)
    def warn(msg): _log.warning(msg)
except Exception:
    def info(msg): print(f"[schedule] {msg}")
    def warn(msg): print(f"[schedule] WARNING: {msg}")


DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

# How far back to look for uncaught slots (should match cron frequency).
# Default: 3h = 180min (matches "0 */3 * * *" cron).
# Override via env: SCHEDULE_WINDOW_MINUTES=28 for a 30min cron.
def _window_minutes() -> int:
    try:
        return int(os.environ.get("SCHEDULE_WINDOW_MINUTES", "180"))
    except Exception:
        return 180


def _find_config() -> Path:
    candidates = [
        Path("schedule_config.json"),
        Path(__file__).parent.parent / "schedule_config.json",
        Path(__file__).parent / "schedule_config.json",
    ]
    for p in candidates:
        if p.exists():
            info(f"Found schedule_config.json at: {p}")
            return p
    return Path("schedule_config.json")


def load_config() -> dict:
    defaults = {
        "paused": False,
        "pause_until": None,
        "weekly": {d: {"enabled": True, "time_utc": "09:00"} for d in DAYS},
        "skip_dates": [],
        "force_dates": [],
    }
    path = _find_config()
    if not path.exists():
        warn("schedule_config.json not found — using defaults (09:00 UTC every day)")
        return defaults
    try:
        with open(path) as f:
            cfg = json.load(f)
        merged = {**defaults, **cfg}
        for day in DAYS:
            if day not in merged.get("weekly", {}):
                merged.setdefault("weekly", {})[day] = defaults["weekly"][day]
        return merged
    except Exception as e:
        warn(f"Could not parse schedule_config.json ({e}) — using defaults")
        return defaults


def _mark_skip():
    gho = os.environ.get("GITHUB_OUTPUT", "")
    if gho:
        try:
            with open(gho, "a") as fh:
                fh.write("SKIP_RUN=true\n")
        except Exception:
            pass


def _slot_to_utc_dt(slot: dict, date_utc: datetime) -> datetime | None:
    """
    Convert a single time slot dict to a UTC datetime on the given date.
    Returns None if the slot cannot be parsed.
    """
    time_local = slot.get("time_local")
    time_tz    = slot.get("time_tz", "")
    time_utc   = slot.get("time_utc")
    time_ist   = slot.get("time_ist")

    if time_local and time_tz and HAS_ZONEINFO:
        try:
            hhmm = _local_to_utc_hhmm(time_local, time_tz, ref_utc=date_utc)
            h, m = map(int, hhmm.split(":"))
            result = date_utc.replace(hour=h, minute=m, second=0, microsecond=0)
            info(f"  DST-aware: {time_local} {time_tz} → {hhmm} UTC ({_dst_offset_str(time_tz)})")
            return result
        except Exception as e:
            warn(f"  DST conversion failed for {time_local} {time_tz}: {e}")

    if time_utc:
        try:
            h, m = map(int, time_utc.split(":"))
            return date_utc.replace(hour=h, minute=m, second=0, microsecond=0)
        except Exception:
            warn(f"  Invalid time_utc format: {time_utc}")

    if time_ist:
        warn(f"  LEGACY time_ist='{time_ist}' — re-save config for DST support")
        try:
            h, m = map(int, time_ist.split(":"))
            total_min = h * 60 + m - 330  # IST = UTC+5:30
            total_min %= 1440
            return date_utc.replace(hour=total_min // 60, minute=total_min % 60,
                                    second=0, microsecond=0)
        except Exception:
            pass

    return None


def _get_target_datetimes(day_cfg: dict, date_utc: datetime) -> list[datetime]:
    """
    Return all UTC posting datetimes for a given day config and date.
    Handles both single-time and multi-time (times array) formats.
    """
    targets = []

    if "times" in day_cfg and isinstance(day_cfg["times"], list) and day_cfg["times"]:
        info(f"  Multi-slot day: {len(day_cfg['times'])} time(s) configured")
        for slot in day_cfg["times"]:
            dt = _slot_to_utc_dt(slot, date_utc)
            if dt:
                targets.append(dt)
        return targets

    # Single-time format — use top-level fields
    dt = _slot_to_utc_dt(day_cfg, date_utc)
    if dt:
        targets.append(dt)
    return targets


def _find_matching_slot(
    cfg: dict,
    now_utc: datetime,
    window_min: int,
) -> tuple[datetime | None, str]:
    """
    Check if any configured slot falls within [now - window_min, now].
    Also checks yesterday's late slots to handle cross-midnight edge cases
    (e.g. a 22:30 UTC slot caught by the 00:00 UTC next-day cron).

    Returns (matched_datetime, day_key) or (None, "").
    """
    window = timedelta(minutes=window_min)
    window_start = now_utc - window

    # Check today and yesterday (for cross-midnight slots)
    dates_to_check = [
        (now_utc,                   DAYS[now_utc.weekday()]),
        (now_utc - timedelta(days=1), DAYS[(now_utc.weekday() - 1) % 7]),
    ]

    for ref_date, day_key in dates_to_check:
        day_cfg = cfg["weekly"].get(day_key, {})
        if not day_cfg.get("enabled", True):
            continue

        # Skip if this date is in skip_dates
        date_str = ref_date.strftime("%Y-%m-%d")
        if date_str in cfg.get("skip_dates", []):
            continue

        targets = _get_target_datetimes(day_cfg, ref_date)

        for target_dt in targets:
            # Handle cross-midnight: if target is 22:30 on Tuesday and we're
            # checking from Wednesday's 00:00, the target_dt will be on Tuesday.
            # We need to check if it falls in [now - window, now].
            diff_min = (now_utc - target_dt).total_seconds() / 60

            if 0 <= diff_min <= window_min:
                info(f"✅ Match: {target_dt.strftime('%H:%M')} UTC ({day_key}) — {diff_min:.0f}min ago")
                return target_dt, day_key
            elif diff_min < 0:
                info(f"  ⏳ {target_dt.strftime('%H:%M')} UTC ({day_key}) is {abs(diff_min):.0f}min in the future")
            else:
                info(f"  ⏭️  {target_dt.strftime('%H:%M')} UTC ({day_key}) passed {diff_min:.0f}min ago (outside {window_min}min window)")

    return None, ""


def check_and_wait(dry_run: bool = False, manual: bool = False) -> None:
    """
    Called at the start of agent.py. No sleeping — pure window check.

    manual=True / dry_run=True → skip schedule, run immediately.
    Scheduled (cron) → check if any slot passed in the last WINDOW_MINUTES.
    If yes → return. If no → sys.exit(0).
    """
    if not manual and os.environ.get("GH_EVENT_NAME") == "workflow_dispatch":
        manual = True
        info("Manual trigger detected via GH_EVENT_NAME")

    cfg     = load_config()
    now_utc = datetime.utcnow()
    today   = now_utc.strftime("%Y-%m-%d")
    day_key = DAYS[now_utc.weekday()]
    window  = _window_minutes()

    trigger = "MANUAL" if manual else ("DRY-RUN" if dry_run else "SCHEDULED")
    info(f"Schedule check — {today} ({day_key.upper()}) — {now_utc.strftime('%H:%M')} UTC — trigger: {trigger}")
    info(f"Lookback window: {window}min (set SCHEDULE_WINDOW_MINUTES to override)")

    # ── 1. PAUSE ─────────────────────────────────────────────────────────────
    if cfg["paused"]:
        resume = cfg.get("pause_until")
        if resume and today >= resume:
            info(f"Pause expired (resume was {resume}) — proceeding")
        else:
            info(f"⏸️  Paused {f'until {resume}' if resume else 'indefinitely'} — exiting")
            sys.exit(0)

    # ── 2. FORCE DATE ────────────────────────────────────────────────────────
    is_forced = today in cfg.get("force_dates", [])
    if is_forced:
        info(f"📌 {today} is a force-run date")

    # ── 3. SKIP DATE ─────────────────────────────────────────────────────────
    if today in cfg.get("skip_dates", []) and not is_forced:
        info(f"🚫 {today} is in skip_dates — exiting")
        sys.exit(0)

    # ── 4. MANUAL / DRY-RUN: skip time check ─────────────────────────────────
    if dry_run or manual:
        info(f"Skipping time check ({trigger}) — running immediately")
        return

    # ── 5. WINDOW CHECK (no sleep) ────────────────────────────────────────────
    matched_dt, matched_day = _find_matching_slot(cfg, now_utc, window)

    if matched_dt is None:
        info(f"⏭️  No slots in {window}min lookback window — exiting cleanly")
        _mark_skip()
        sys.exit(0)

    info(f"🚀 Proceeding — matched {matched_dt.strftime('%H:%M')} UTC ({matched_day})")


# ─── Diagnostic ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    cfg     = load_config()
    now_utc = datetime.utcnow()
    today   = now_utc.strftime("%Y-%m-%d")
    day_key = DAYS[now_utc.weekday()]
    window  = _window_minutes()

    print("\n" + "=" * 55)
    print("  schedule_checker.py — diagnostic")
    print("=" * 55)
    print(f"  Now (UTC):      {now_utc.strftime('%Y-%m-%d %H:%M')}")
    print(f"  Day:            {day_key.upper()}")
    print(f"  Paused:         {cfg['paused']}")
    print(f"  Pause until:    {cfg.get('pause_until') or '(none)'}")
    print(f"  Skip today:     {today in cfg.get('skip_dates', [])}")
    print(f"  Force today:    {today in cfg.get('force_dates', [])}")
    print(f"  Window:         {window}min lookback")
    print("=" * 55)

    matched_dt, matched_day = _find_matching_slot(cfg, now_utc, window)
    print(f"\n  → Would post NOW: {'YES ✅  (' + matched_dt.strftime('%H:%M') + ' UTC slot)' if matched_dt else 'NO ⏭️'}\n")
