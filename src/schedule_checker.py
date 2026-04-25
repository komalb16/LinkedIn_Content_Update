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

No sleeping = no timeout conflicts. The job finishes in seconds
if there is nothing to post, and in ~3-5 min when it posts.

Window sizing
─────────────
With an hourly cron, WINDOW_MINUTES must be < 60 to prevent two
consecutive crons from both matching the same slot. GitHub Actions
crons can fire up to ~20 min late, so the safe formula is:

    WINDOW_MINUTES = 55  (leaves a 5-min dead zone, tolerates 55-min drift)

Example — slot at 12:30 UTC:
  12:00 cron fires at 12:04 → 12:30 is 26 min in the future → no match ✓
  13:00 cron fires at 13:02 → 12:30 is 32 min ago ≤ 55 → MATCH ✅ posts
  14:00 cron fires at 14:01 → 12:30 is 91 min ago > 55 → no match ✓

The slot lock is a second line of defence against extreme GH drift
causing two crons to both match. The lock file is committed to the
repo in the existing "Save Topic History" step.

Cross-midnight handling:
  Slots after ~23:00 UTC (e.g. 00:30 UTC next day) are evaluated
  correctly because _candidate_target_datetimes generates candidates
  for today-1, today, and today+1 and filters by local day-of-week.

Supports unlimited posting slots per day via the "times" array.
Adding new slots requires only a schedule_config.json change.
"""

import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
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

    HAS_ZONEINFO = True
except ImportError:
    HAS_ZONEINFO = False
    def _dst_offset_str(tz_name: str) -> str:
        return "unknown"

try:
    from logger import get_logger

    _log = get_logger("schedule")

    def info(msg: str) -> None:
        _log.info(msg)

    def warn(msg: str) -> None:
        _log.warning(msg)
except Exception:
    def _safe_print(msg: str) -> None:
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        print(str(msg).encode(encoding, errors="replace").decode(encoding, errors="replace"))

    def info(msg: str) -> None:
        _safe_print(f"[schedule] {msg}")

    def warn(msg: str) -> None:
        _safe_print(f"[schedule] WARNING: {msg}")


DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DAY_INDEX = {day: idx for idx, day in enumerate(DAYS)}
LOCK_FILE = Path(__file__).resolve().parent / ".post_lock.json"

# ── WINDOW ─────────────────────────────────────────────────────────────────
# How far back to look for uncaught slots. Must be < cron interval (60 min)
# to prevent two consecutive crons from double-matching the same slot.
# 55 min leaves a 5-min dead zone and tolerates up to 55 min of GH drift.
# Override via env: SCHEDULE_WINDOW_MINUTES=55
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
    Return True when this exact UTC slot has not been claimed yet.
    Return False when a previous run already claimed the same slot (double-post guard).
    Writes the claim atomically and commits it via the existing git step.
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

    # Prune entries older than 2 days to keep the file small
    locks = {
        k: v for k, v in locks.items()
        if isinstance(k, str) and "_" in k and k.split("_", 1)[0] >= cutoff
    }

    if lock_key in locks:
        warn(f"🔒 Slot {lock_key} UTC already claimed by a previous run — skipping to prevent double-post")
        return False

    locks[lock_key] = datetime.now(timezone.utc).isoformat()
    try:
        with LOCK_FILE.open("w", encoding="utf-8") as f:
            json.dump(locks, f, indent=2)
        info(f"🔒 Slot {lock_key} UTC claimed — lock written")
    except Exception as e:
        # Non-fatal: window sizing is the primary guard
        warn(f"Could not write post lock ({e}) — proceeding without lock")

    return True


def _slot_to_utc_dt(slot: dict, date_utc: datetime) -> datetime | None:
    """Convert a time slot dict (time_utc or time_ist) to a UTC datetime."""
    time_utc = slot.get("time_utc")
    time_ist = slot.get("time_ist")

    if time_utc:
        try:
            h, m = map(int, time_utc.split(":"))
            return date_utc.replace(hour=h, minute=m, second=0, microsecond=0)
        except Exception:
            warn(f"Invalid time_utc format: {time_utc}")

    if time_ist:
        warn(f"Legacy time_ist='{time_ist}' - re-save config for timezone support")
        try:
            h, m = map(int, time_ist.split(":"))
            total_min = h * 60 + m - 330
            total_min %= 1440
            return date_utc.replace(
                hour=total_min // 60,
                minute=total_min % 60,
                second=0,
                microsecond=0,
            )
        except Exception:
            pass

    return None


def _local_date_to_utc_dt(slot: dict, local_date: date, fallback_tz: str = "") -> datetime | None:
    """Convert a local wall-clock time on a specific local date into absolute UTC."""
    time_local = slot.get("time_local")
    time_tz = slot.get("time_tz") or fallback_tz

    if not (time_local and time_tz and HAS_ZONEINFO):
        return None

    try:
        tz = ZoneInfo(time_tz)
        local_dt = datetime(
            local_date.year,
            local_date.month,
            local_date.day,
            int(time_local[:2]),
            int(time_local[3:]),
            tzinfo=tz,
        )
        utc_dt = local_dt.astimezone(timezone.utc)
        info(
            f"  DST-aware: {local_date.isoformat()} {time_local} {time_tz} "
            f"→ {utc_dt.strftime('%H:%M')} UTC ({_dst_offset_str(time_tz)})"
        )
        return utc_dt
    except Exception as e:
        warn(f"Local-day conversion failed for {local_date.isoformat()} {time_local} {time_tz}: {e}")
        return None


def _candidate_target_datetimes(
    day_key: str,
    day_cfg: dict,
    now_utc: datetime,
    window_min: int,
) -> list[datetime]:
    """
    Build all candidate absolute UTC datetimes for a schedule day.
    Evaluates yesterday, today, and tomorrow to handle cross-midnight slots.
    Deduplicates by exact UTC datetime.
    """
    targets: list[datetime] = []
    slots = day_cfg.get("times")
    slot_list = slots if isinstance(slots, list) and slots else [day_cfg]
    if isinstance(slots, list) and slots:
        info(f"  Multi-slot day: {len(slots)} time(s) configured")

    for slot in slot_list:
        slot_tz = slot.get("time_tz") or day_cfg.get("time_tz") or ""

        if slot.get("time_local") and slot_tz and HAS_ZONEINFO:
            # For local-time slots, find the local date(s) that fall on day_key
            # and are within the lookback window or in the very near future.
            try:
                tz = ZoneInfo(slot_tz)
                candidate_local_dates = {
                    (now_utc - timedelta(days=1)).astimezone(tz).date(),
                    now_utc.astimezone(tz).date(),
                    (now_utc + timedelta(days=1)).astimezone(tz).date(),
                }
                for local_date in sorted(candidate_local_dates):
                    if local_date.weekday() != DAY_INDEX[day_key]:
                        continue
                    dt = _local_date_to_utc_dt(slot, local_date, fallback_tz=slot_tz)
                    if dt:
                        targets.append(dt)
            except Exception as e:
                warn(f"Could not evaluate local schedule dates for {day_key}: {e}")
            continue

        # time_utc or time_ist slots — evaluate on nearby UTC dates
        for ref_dt in (
            now_utc - timedelta(days=1),
            now_utc,
            now_utc + timedelta(days=1),
        ):
            if DAYS[ref_dt.weekday()] != day_key:
                continue
            dt = _slot_to_utc_dt(slot, ref_dt)
            if dt and not dt.tzinfo:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt:
                targets.append(dt)

    # Deduplicate by exact UTC timestamp
    unique: dict[str, datetime] = {}
    for t in targets:
        unique[t.astimezone(timezone.utc).isoformat()] = t
    return list(unique.values())


def _find_matching_slot(
    cfg: dict,
    now_utc: datetime,
    window_min: int,
) -> tuple[datetime | None, str]:
    """
    Check all configured slots. Return the most recent one that falls
    within [now_utc - window_min, now_utc], or (None, "") if none match.

    "Most recent" = closest to now_utc (smallest diff_min), which ensures
    that if two slots somehow both fall in the window (e.g. a config with
    two slots 30 min apart and a 55-min window), we pick the later one.
    """
    best: tuple[datetime, str] | None = None

    for day_key in DAYS:
        day_cfg = cfg["weekly"].get(day_key, {})
        if not day_cfg.get("enabled", True):
            continue

        targets = _candidate_target_datetimes(day_key, day_cfg, now_utc, window_min)

        for target_dt in targets:
            # Ensure target_dt is tz-aware for comparison
            if not target_dt.tzinfo:
                target_dt = target_dt.replace(tzinfo=timezone.utc)

            # Check skip_dates against the slot's local date
            slot_tz = day_cfg.get("time_tz") or "UTC"
            try:
                local_date_str = (
                    target_dt.astimezone(ZoneInfo(slot_tz)).strftime("%Y-%m-%d")
                    if HAS_ZONEINFO else target_dt.strftime("%Y-%m-%d")
                )
            except Exception:
                local_date_str = target_dt.strftime("%Y-%m-%d")

            if local_date_str in cfg.get("skip_dates", []):
                info(f"  Skipping {target_dt.strftime('%H:%M')} UTC ({day_key}) — local date {local_date_str} is in skip_dates")
                continue

            diff_min = (now_utc - target_dt).total_seconds() / 60  # positive = past

            if 0 <= diff_min <= window_min:
                info(f"✅ Match: {target_dt.strftime('%H:%M')} UTC ({day_key}) — {diff_min:.0f}min ago")
                if best is None or target_dt > best[0]:
                    best = (target_dt, day_key)
            elif diff_min < 0:
                info(f"  ⏳ {target_dt.strftime('%H:%M')} UTC ({day_key}) is {abs(diff_min):.0f}min in the future")
            else:
                info(f"  ⏭️  {target_dt.strftime('%H:%M')} UTC ({day_key}) passed {diff_min:.0f}min ago (outside {window_min}min window)")

    if best:
        return best
    return None, ""


def check_and_wait(dry_run: bool = False, manual: bool = False) -> None:
    """
    Called at the start of agent.py. No sleeping — pure lookback + slot lock.

    manual=True / dry_run=True → skip schedule, run immediately.
    Scheduled (cron) → check if any slot passed in the last WINDOW_MINUTES.
      If yes → claim slot lock → proceed to post.
      If slot already locked → exit cleanly (double-post guard).
      If no match → exit cleanly.
    """
    # NOTE: workflow_dispatch does NOT auto-set manual=True.
    # Pass --manual explicitly only when you intend to bypass the schedule
    # (i.e. when the workflow input skip_schedule=true is set).

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

    # ── 4. MANUAL / DRY-RUN: skip time check ──────────────────────────────────
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
    print(f"  Window:         {window}min lookback (no sleep)")
    print(f"  Lock file:      {LOCK_FILE}")
    print("=" * 60)

    if LOCK_FILE.exists():
        try:
            with LOCK_FILE.open() as f:
                locks = json.load(f)
            recent = sorted(locks.keys())[-5:]
            print(f"\n  Recent lock entries ({len(locks)} total):")
            for k in recent:
                print(f"    {k}  →  claimed at {locks[k]}")
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
            status += "  ⚠️  already claimed — would be blocked by lock"
        print(f"\n  → Would post NOW: {status}\n")
    else:
        print(f"\n  → Would post NOW: NO ⏭️\n")
