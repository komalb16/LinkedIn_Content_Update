"""
schedule_checker.py - src/schedule_checker.py
────────────────────────────────────────────────────────────────
Reads schedule_config.json and decides whether the agent should
post RIGHT NOW. Called at the start of agent.py.

Design: NO SLEEP — pure lookback window + slot lock
─────────────────────────────────────────────────────
The workflow cron fires hourly (0 * * * *).
This checker asks: "Did any configured slot pass within the last
WINDOW_MINUTES?" If yes → claim the slot lock → post. If the lock
is already claimed → exit (double-post guard). If no match → exit.

No sleeping = no timeout conflicts.

Window sizing
─────────────
With an hourly cron, WINDOW_MINUTES must be < 60 to prevent two
consecutive crons from both matching the same slot. GitHub Actions
crons can fire up to ~20 min late, so:

    WINDOW_MINUTES = 55  (5-min dead zone, tolerates 55-min GH drift)

Example — slot at 13:30 UTC:
  13:00 cron fires → 13:30 is 30 min in the future → no match ✓
  14:00 cron fires → 13:30 is 30 min ago ≤ 55 → MATCH ✅ posts
  15:00 cron fires → 13:30 is 90 min ago > 55 → no match ✓

How day matching works
──────────────────────
For each day_key (mon..sun) in the config, we compute the absolute
UTC datetime of that slot for the most recent occurrence of that
weekday — looking back up to 7 days. This is simple and correct:

    most_recent_sat = today - (today.weekday - SAT_INDEX) % 7 days

We then check if that UTC datetime falls in [now - window, now].
This handles cross-midnight, DST, and all timezone edge cases cleanly.
"""

import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Tuple

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

    HAS_ZONEINFO = True
except ImportError:
    HAS_ZONEINFO = False
    def _dst_offset_str(tz_name: str) -> str:
        return "unknown"

try:
    from logger import get_logger
    _log = get_logger("schedule")
    def info(msg: str) -> None: _log.info(msg)
    def warn(msg: str) -> None: _log.warning(msg)
except Exception:
    def _safe_print(msg: str) -> None:
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        print(str(msg).encode(enc, errors="replace").decode(enc, errors="replace"))
    def info(msg: str) -> None: _safe_print(f"[schedule] {msg}")
    def warn(msg: str) -> None: _safe_print(f"[schedule] WARNING: {msg}")


DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DAY_INDEX = {day: idx for idx, day in enumerate(DAYS)}
# Python's weekday(): 0=Mon, 1=Tue, ..., 5=Sat, 6=Sun — matches DAYS order.

LOCK_FILE = Path(__file__).resolve().parent / ".post_lock.json"

_DEFAULT_WINDOW_MINUTES = 55


def _window_minutes() -> int:
    try:
        return int(os.environ.get("SCHEDULE_WINDOW_MINUTES", str(_DEFAULT_WINDOW_MINUTES)))
    except Exception:
        return _DEFAULT_WINDOW_MINUTES


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
        warn("schedule_config.json not found - using defaults (09:00 UTC every day)")
        return defaults
    try:
        with path.open(encoding="utf-8") as f:
            cfg = json.load(f)
        merged = {**defaults, **cfg}
        for day in DAYS:
            if day not in merged.get("weekly", {}):
                merged.setdefault("weekly", {})[day] = defaults["weekly"][day]
        return merged
    except Exception as e:
        warn(f"Could not parse schedule_config.json ({e}) - using defaults")
        return defaults


def _mark_skip() -> None:
    gho = os.environ.get("GITHUB_OUTPUT", "")
    if not gho:
        return
    try:
        with open(gho, "a", encoding="utf-8") as fh:
            fh.write("SKIP_RUN=true\n")
    except Exception:
        pass


def _check_and_set_post_lock(matched_dt: datetime) -> bool:
    """
    Return True if this UTC slot has not been claimed yet (safe to post).
    Return False if already claimed (double-post guard).
    """
    matched_utc = matched_dt.astimezone(timezone.utc)
    lock_key = matched_utc.strftime("%Y-%m-%d_%H:%M")
    cutoff = (matched_utc - timedelta(days=2)).strftime("%Y-%m-%d")

    locks: dict[str, str] = {}
    if LOCK_FILE.exists():
        try:
            with LOCK_FILE.open(encoding="utf-8") as f:
                locks = json.load(f)
        except Exception:
            locks = {}

    # Prune entries older than 2 days
    locks = {
        k: v for k, v in locks.items()
        if isinstance(k, str) and "_" in k and k.split("_", 1)[0] >= cutoff
    }

    if lock_key in locks:
        warn(f"🔒 Slot {lock_key} UTC already claimed — skipping to prevent double-post")
        return False

    locks[lock_key] = datetime.now(timezone.utc).isoformat()
    try:
        with LOCK_FILE.open("w", encoding="utf-8") as f:
            json.dump(locks, f, indent=2)
        info(f"🔒 Slot {lock_key} UTC claimed")
    except Exception as e:
        warn(f"Could not write post lock ({e}) — proceeding (window-size is primary guard)")

    return True


def _most_recent_weekday_date(target_weekday: int, ref_utc: datetime) -> date:
    """
    Return the most recent calendar date (UTC) that fell on target_weekday.
    target_weekday: 0=Mon .. 6=Sun (Python weekday() convention).
    If today IS target_weekday, returns today.
    """
    today = ref_utc.date()
    days_ago = (today.weekday() - target_weekday) % 7
    return today - timedelta(days=days_ago)


def _slot_utc_datetimes_for_day(
    day_key: str,
    day_cfg: dict,
    now_utc: datetime,
) -> list[datetime]:
    """
    For a given day_key, compute the absolute UTC datetime(s) of its
    configured slots for:
      - the most recent occurrence of that weekday (this week or today)
      - the occurrence one week earlier (edge case: slot was very late
        Sunday night and we're checking Monday morning with a small window)

    Returns a deduplicated list of tz-aware UTC datetimes.
    """
    target_weekday = DAY_INDEX[day_key]
    # Check this week's occurrence and last week's (for cross-week edge cases)
    ref_dates = []
    most_recent = _most_recent_weekday_date(target_weekday, now_utc)
    ref_dates.append(most_recent)
    ref_dates.append(most_recent - timedelta(weeks=1))

    slots = day_cfg.get("times")
    slot_list = slots if isinstance(slots, list) and slots else [day_cfg]
    if isinstance(slots, list) and slots:
        info(f"  [{day_key}] Multi-slot: {len(slots)} time(s)")

    results: list[datetime] = []

    for slot in slot_list:
        slot_tz = slot.get("time_tz") or day_cfg.get("time_tz") or ""
        time_local = slot.get("time_local")
        time_utc_str = slot.get("time_utc")
        time_ist = slot.get("time_ist")

        for ref_date in ref_dates:
            dt: Optional[datetime] = None

            if time_local and slot_tz and HAS_ZONEINFO:
                # Build the datetime in local time on the local calendar date
                # that corresponds to ref_date (which is a UTC date).
                # Because local date == UTC date for most timezones near UTC,
                # we try ref_date directly; for large UTC offsets we also try
                # ref_date ± 1 day to find the matching local weekday.
                try:
                    tz = ZoneInfo(slot_tz)
                    h, m = int(time_local[:2]), int(time_local[3:])
                    for delta in (0, -1, 1):
                        local_candidate = ref_date + timedelta(days=delta)
                        if local_candidate.weekday() != target_weekday:
                            continue
                        local_dt = datetime(
                            local_candidate.year, local_candidate.month, local_candidate.day,
                            h, m, tzinfo=tz,
                        )
                        dt = local_dt.astimezone(timezone.utc)
                        info(
                            f"  [{day_key}] DST-aware: {local_candidate} {time_local} {slot_tz}"
                            f" → {dt.strftime('%H:%M')} UTC ({_dst_offset_str(slot_tz)})"
                        )
                        break
                except Exception as e:
                    warn(f"  [{day_key}] DST conversion failed: {e}")

            elif time_utc_str:
                try:
                    h, m = map(int, time_utc_str.split(":"))
                    # ref_date is already a UTC date
                    naive = datetime(ref_date.year, ref_date.month, ref_date.day, h, m)
                    dt = naive.replace(tzinfo=timezone.utc)
                except Exception:
                    warn(f"  [{day_key}] Invalid time_utc: {time_utc_str}")

            elif time_ist:
                warn(f"  [{day_key}] Legacy time_ist='{time_ist}' — re-save config")
                try:
                    h, m = map(int, time_ist.split(":"))
                    total_min = (h * 60 + m - 330) % 1440
                    naive = datetime(ref_date.year, ref_date.month, ref_date.day,
                                     total_min // 60, total_min % 60)
                    dt = naive.replace(tzinfo=timezone.utc)
                except Exception:
                    pass

            if dt:
                results.append(dt)

    # Deduplicate by exact UTC timestamp
    unique: dict[str, datetime] = {}
    for t in results:
        unique[t.isoformat()] = t
    return list(unique.values())


def _find_matching_slot(
    cfg: dict,
    now_utc: datetime,
    window_min: int,
) -> Tuple[Optional[datetime], str]:
    """
    Check all configured slots across all days.
    Return the most recent slot (closest to now) that falls within
    [now_utc - window_min, now_utc], or (None, "") if none match.
    """
    best: Optional[Tuple[datetime, str]] = None

    for day_key in DAYS:
        day_cfg = cfg["weekly"].get(day_key, {})
        if not day_cfg.get("enabled", True):
            continue

        targets = _slot_utc_datetimes_for_day(day_key, day_cfg, now_utc)

        for target_dt in targets:
            if not target_dt.tzinfo:
                target_dt = target_dt.replace(tzinfo=timezone.utc)

            # Skip-date check against local calendar date
            slot_tz = day_cfg.get("time_tz") or "UTC"
            try:
                local_date_str = (
                    target_dt.astimezone(ZoneInfo(slot_tz)).strftime("%Y-%m-%d")
                    if HAS_ZONEINFO else target_dt.strftime("%Y-%m-%d")
                )
            except Exception:
                local_date_str = target_dt.strftime("%Y-%m-%d")

            if local_date_str in cfg.get("skip_dates", []):
                info(f"  [{day_key}] Skipping {target_dt.strftime('%H:%M')} UTC — {local_date_str} in skip_dates")
                continue

            diff_min = (now_utc - target_dt).total_seconds() / 60  # positive = past

            if 0 <= diff_min <= window_min:
                info(f"✅ Match: {target_dt.strftime('%H:%M')} UTC ({day_key}) — {diff_min:.0f}min ago")
                if best is None or target_dt > best[0]:
                    best = (target_dt, day_key)
            elif diff_min < 0:
                info(f"  ⏳ [{day_key}] {target_dt.strftime('%H:%M')} UTC is {abs(diff_min):.0f}min in the future")
            else:
                info(f"  ⏭️  [{day_key}] {target_dt.strftime('%H:%M')} UTC passed {diff_min:.0f}min ago (outside {window_min}min window)")

    if best:
        return best
    return None, ""


def check_and_wait(dry_run: bool = False, manual: bool = False) -> None:
    """
    Called at the start of agent.py. No sleeping — pure lookback + slot lock.

    manual=True / dry_run=True → skip schedule, run immediately.
    Scheduled → check if any slot passed in the last WINDOW_MINUTES.
    """
    cfg = load_config()
    now_utc = datetime.now(timezone.utc)
    today = now_utc.strftime("%Y-%m-%d")
    day_key = DAYS[now_utc.weekday()]
    window = _window_minutes()

    trigger = "MANUAL" if manual else ("DRY-RUN" if dry_run else "SCHEDULED")
    info(f"Schedule check — {today} ({day_key.upper()}) — {now_utc.strftime('%H:%M')} UTC — trigger: {trigger}")
    info(f"Lookback window: {window}min (hourly cron, no sleep, override via SCHEDULE_WINDOW_MINUTES)")

    # ── 1. PAUSE ──────────────────────────────────────────────────────────────
    if cfg["paused"]:
        resume = cfg.get("pause_until")
        if resume and today >= resume:
            info(f"Pause expired (resume was {resume}) — proceeding")
        else:
            info(f"⏸️  Paused {f'until {resume}' if resume else 'indefinitely'} — exiting")
            sys.exit(0)

    # ── 2. FORCE DATE ─────────────────────────────────────────────────────────
    is_forced = today in cfg.get("force_dates", [])
    if is_forced:
        info(f"📌 {today} is a force-run date")

    # ── 3. SKIP DATE ──────────────────────────────────────────────────────────
    if today in cfg.get("skip_dates", []) and not is_forced:
        info(f"🚫 {today} is in skip_dates — exiting")
        sys.exit(0)

    # ── 4. MANUAL / DRY-RUN ───────────────────────────────────────────────────
    if dry_run or manual:
        info(f"Skipping schedule check ({trigger}) — running immediately")
        return

    # ── 5. LOOKBACK WINDOW CHECK ───────────────────────────────────────────────
    matched_dt, matched_day = _find_matching_slot(cfg, now_utc, window)

    if matched_dt is None:
        info(f"⏭️  No slots in {window}min lookback window — exiting cleanly")
        _mark_skip()
        sys.exit(0)

    # ── 6. SLOT LOCK (double-post guard) ──────────────────────────────────────
    if not _check_and_set_post_lock(matched_dt):
        _mark_skip()
        sys.exit(0)

    info(f"🚀 Proceeding — matched {matched_dt.strftime('%H:%M')} UTC ({matched_day})")


# ─── Diagnostic ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    cfg = load_config()
    now_utc = datetime.now(timezone.utc)
    today = now_utc.strftime("%Y-%m-%d")
    day_key = DAYS[now_utc.weekday()]
    window = _window_minutes()

    print("\n" + "=" * 60)
    print("  schedule_checker.py — diagnostic")
    print("=" * 60)
    print(f"  Now (UTC):      {now_utc.strftime('%Y-%m-%d %H:%M')}")
    print(f"  Day:            {day_key.upper()}")
    print(f"  Paused:         {cfg['paused']}")
    print(f"  Pause until:    {cfg.get('pause_until') or '(none)'}")
    print(f"  Skip today:     {today in cfg.get('skip_dates', [])}")
    print(f"  Force today:    {today in cfg.get('force_dates', [])}")
    print(f"  Window:         {window}min lookback")
    print(f"  Lock file:      {LOCK_FILE}")
    print("=" * 60)

    if LOCK_FILE.exists():
        try:
            with LOCK_FILE.open() as f:
                locks = json.load(f)
            recent = sorted(locks.keys())[-8:]
            print(f"\n  Recent lock entries ({len(locks)} total):")
            for k in recent:
                print(f"    {k}  →  {locks[k]}")
        except Exception:
            pass

    matched_dt, matched_day = _find_matching_slot(cfg, now_utc, window)
    if matched_dt:
        key = matched_dt.astimezone(timezone.utc).strftime("%Y-%m-%d_%H:%M")
        locks = {}
        if LOCK_FILE.exists():
            try:
                with LOCK_FILE.open() as f:
                    locks = json.load(f)
            except Exception:
                pass
        already = key in locks
        status = f"YES ✅  ({matched_dt.strftime('%H:%M')} UTC, {matched_day})"
        if already:
            status += "  ⚠️  already claimed — would be blocked"
        print(f"\n  → Would post NOW: {status}\n")
    else:
        print(f"\n  → Would post NOW: NO ⏭️\n")


# ── Backwards-compatibility alias ────────────────────────────────────────────
# The old sleep-based design exposed _find_relevant_slot; tests may import it.
# This shim wraps _find_matching_slot to return the same (dt, day, status) tuple
# the old function returned, so existing tests keep working unchanged.
def _find_relevant_slot(
    cfg: dict,
    now_utc: datetime,
    window_min: int,
) -> "Tuple[Optional[datetime], str, str]":
    dt, day = _find_matching_slot(cfg, now_utc, window_min)
    status = "recent" if dt is not None else ""
    return dt, day, status
