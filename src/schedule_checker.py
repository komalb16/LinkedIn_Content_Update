"""
schedule_checker.py - src/schedule_checker.py

Reads schedule_config.json and decides whether the agent should post.

Design:
- The workflow cron fires hourly.
- If a scheduled slot is within the next forward window, sleep until it.
- If a scheduled slot passed very recently, post immediately.
- A per-slot lock prevents the same UTC slot from firing twice.
"""

import json
import os
import sys
import time
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


def _forward_window_minutes() -> int:
    try:
        return int(os.environ.get("SCHEDULE_WINDOW_MINUTES", "59"))
    except Exception:
        return 59


def _backward_grace_minutes() -> int:
    try:
        return int(os.environ.get("SCHEDULE_BACKWARD_GRACE_MINUTES", "30"))
    except Exception:
        return 30


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
    Return False when a previous run already claimed the same slot.
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

    locks = {
        key: value
        for key, value in locks.items()
        if isinstance(key, str) and "_" in key and key.split("_", 1)[0] >= cutoff
    }

    if lock_key in locks:
        info(f"Lock exists for {lock_key} UTC - already claimed; skipping")
        return False

    locks[lock_key] = datetime.now(timezone.utc).isoformat()
    try:
        with LOCK_FILE.open("w", encoding="utf-8") as f:
            json.dump(locks, f, indent=2)
    except Exception as e:
        warn(f"Could not write post lock: {e}")

    return True


def _slot_to_utc_dt(slot: dict, date_utc: datetime) -> datetime | None:
    """
    Convert a single time slot dict to a UTC datetime on the given UTC date.
    """
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
    """
    Convert a local schedule date + local wall clock time into absolute UTC.
    """
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
            f"  Local-day aware: {local_date.isoformat()} {time_local} {time_tz} "
            f"-> {utc_dt.strftime('%H:%M')} UTC ({_dst_offset_str(time_tz)})"
        )
        return utc_dt
    except Exception as e:
        warn(f"Local-day conversion failed for {local_date.isoformat()} {time_local} {time_tz}: {e}")
        return None


def _utc_date_to_utc_dt_for_local_day(
    slot: dict,
    day_key: str,
    date_utc: date,
    fallback_tz: str = "",
) -> datetime | None:
    """
    Convert a stored UTC clock time into absolute UTC, but only when that
    instant lands on the configured local weekday in the slot timezone.
    """
    time_utc = slot.get("time_utc")
    time_tz = slot.get("time_tz") or fallback_tz

    if not (time_utc and time_tz and HAS_ZONEINFO):
        return None

    try:
        h, m = map(int, time_utc.split(":"))
        utc_dt = datetime(date_utc.year, date_utc.month, date_utc.day, h, m, tzinfo=timezone.utc)
        local_dt = utc_dt.astimezone(ZoneInfo(time_tz))
        if local_dt.weekday() != DAY_INDEX[day_key]:
            return None
        info(
            f"  UTC-slot aware: {date_utc.isoformat()} {time_utc} UTC "
            f"-> {local_dt.strftime('%Y-%m-%d %H:%M')} {time_tz}"
        )
        return utc_dt
    except Exception as e:
        warn(f"UTC-slot conversion failed for {date_utc.isoformat()} {time_utc} {time_tz}: {e}")
        return None


def _candidate_target_datetimes(
    day_key: str,
    day_cfg: dict,
    now_utc: datetime,
    window_min: int,
) -> list[datetime]:
    """
    Build absolute UTC datetimes for a schedule day.
    """
    window_start = now_utc - timedelta(minutes=window_min)
    targets: list[datetime] = []

    slots = day_cfg.get("times")
    slot_list = slots if isinstance(slots, list) and slots else [day_cfg]
    if isinstance(slots, list) and slots:
        info(f"  Multi-slot day: {len(slots)} time(s) configured")

    for slot in slot_list:
        slot_tz = slot.get("time_tz") or day_cfg.get("time_tz") or ""

        if slot.get("time_local") and slot_tz and HAS_ZONEINFO:
            try:
                tz = ZoneInfo(slot_tz)
                candidate_local_dates = {
                    now_utc.astimezone(tz).date(),
                    window_start.astimezone(tz).date(),
                    (now_utc + timedelta(minutes=window_min)).astimezone(tz).date(),
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

        if slot.get("time_utc") and slot_tz and HAS_ZONEINFO:
            candidate_utc_dates = {
                now_utc.date(),
                window_start.date(),
                (now_utc + timedelta(minutes=window_min)).date(),
            }
            for candidate_date in sorted(candidate_utc_dates):
                dt = _utc_date_to_utc_dt_for_local_day(slot, day_key, candidate_date, fallback_tz=slot_tz)
                if dt:
                    targets.append(dt)
            continue

        for ref_date in (
            now_utc,
            now_utc - timedelta(days=1),
            now_utc + timedelta(days=1),
        ):
            if DAYS[ref_date.weekday()] != day_key:
                continue
            dt = _slot_to_utc_dt(slot, ref_date)
            if dt:
                targets.append(dt)

    unique: dict[str, datetime] = {}
    for target in targets:
        unique[target.isoformat()] = target
    return list(unique.values())


def _find_relevant_slot(
    cfg: dict,
    now_utc: datetime,
    window_min: int,
) -> tuple[datetime | None, str, str]:
    """
    Find the most relevant slot for this run.

    Returns:
    - (target, day, "recent") for a slot within backward grace
    - (target, day, "upcoming") for the nearest upcoming slot within window
    - (None, "", "") when nothing is relevant
    """
    backward_grace_min = _backward_grace_minutes()
    best_recent: tuple[datetime, str] | None = None
    best_upcoming: tuple[datetime, str] | None = None

    for day_key in DAYS:
        day_cfg = cfg["weekly"].get(day_key, {})
        if not day_cfg.get("enabled", True):
            continue

        targets = _candidate_target_datetimes(day_key, day_cfg, now_utc, window_min)

        for target_dt in targets:
            slot_tz = day_cfg.get("time_tz") or "UTC"
            try:
                local_date_str = (
                    target_dt.astimezone(ZoneInfo(slot_tz)).strftime("%Y-%m-%d")
                    if HAS_ZONEINFO else ""
                )
            except Exception:
                local_date_str = ""
            if local_date_str and local_date_str in cfg.get("skip_dates", []):
                info(
                    f"  Skipping {target_dt.strftime('%H:%M')} UTC ({day_key}) "
                    f"because local date {local_date_str} is skipped"
                )
                continue

            diff_min = (target_dt - now_utc).total_seconds() / 60

            if -backward_grace_min <= diff_min <= 0:
                mins_ago = abs(diff_min)
                info(f"Recent slot: {target_dt.strftime('%H:%M')} UTC ({day_key}) - {mins_ago:.0f}min ago")
                if best_recent is None or target_dt > best_recent[0]:
                    best_recent = (target_dt, day_key)
            elif 0 < diff_min <= window_min:
                info(f"Upcoming slot: {target_dt.strftime('%H:%M')} UTC ({day_key}) in {diff_min:.0f}min")
                if best_upcoming is None or target_dt < best_upcoming[0]:
                    best_upcoming = (target_dt, day_key)
            elif diff_min < -backward_grace_min:
                info(
                    f"  Passed: {target_dt.strftime('%H:%M')} UTC ({day_key}) "
                    f"{abs(diff_min):.0f}min ago (outside {backward_grace_min}min grace)"
                )
            else:
                info(
                    f"  Future: {target_dt.strftime('%H:%M')} UTC ({day_key}) "
                    f"{diff_min:.0f}min away (outside {window_min}min forward window)"
                )

    if best_recent:
        return best_recent[0], best_recent[1], "recent"
    if best_upcoming:
        return best_upcoming[0], best_upcoming[1], "upcoming"
    return None, "", ""


def check_and_wait(dry_run: bool = False, manual: bool = False) -> None:
    if not manual and os.environ.get("GH_EVENT_NAME") == "workflow_dispatch":
        manual = True
        info("Manual trigger detected via GH_EVENT_NAME")

    cfg = load_config()
    now_utc = datetime.now(timezone.utc)
    today = now_utc.strftime("%Y-%m-%d")
    day_key = DAYS[now_utc.weekday()]
    forward_window = _forward_window_minutes()
    backward_grace = _backward_grace_minutes()

    trigger = "MANUAL" if manual else ("DRY-RUN" if dry_run else "SCHEDULED")
    info(f"Schedule check - {today} ({day_key.upper()}) - {now_utc.strftime('%H:%M')} UTC - trigger: {trigger}")
    info(f"Forward window: {forward_window}min (set SCHEDULE_WINDOW_MINUTES to override)")
    info(f"Backward grace: {backward_grace}min (set SCHEDULE_BACKWARD_GRACE_MINUTES to override)")

    if cfg["paused"]:
        resume = cfg.get("pause_until")
        if resume and today >= resume:
            info(f"Pause expired (resume was {resume}) - proceeding")
        else:
            info(f"Paused {f'until {resume}' if resume else 'indefinitely'} - exiting")
            sys.exit(0)

    is_forced = today in cfg.get("force_dates", [])
    if is_forced:
        info(f"{today} is a force-run date")

    if today in cfg.get("skip_dates", []) and not is_forced:
        info(f"{today} is in skip_dates - exiting")
        sys.exit(0)

    if dry_run or manual:
        info(f"Skipping schedule check ({trigger}) - running immediately")
        return

    matched_dt, matched_day, matched_status = _find_relevant_slot(cfg, now_utc, forward_window)

    if matched_dt is None:
        info(f"No slots in the next {forward_window}min or last {backward_grace}min - exiting cleanly")
        _mark_skip()
        sys.exit(0)

    if matched_status == "upcoming":
        sleep_secs = max(0, int((matched_dt - now_utc).total_seconds()))
        if sleep_secs > 0:
            info(f"Sleeping {sleep_secs}s until {matched_dt.strftime('%H:%M')} UTC ({matched_day})")
            time.sleep(sleep_secs)
    else:
        mins_ago = int((datetime.now(timezone.utc) - matched_dt).total_seconds() // 60)
        info(
            f"Proceeding immediately - matched recent slot "
            f"{matched_dt.strftime('%H:%M')} UTC ({matched_day}), {mins_ago}min ago"
        )

    if not _check_and_set_post_lock(matched_dt):
        _mark_skip()
        sys.exit(0)

    info(f"Proceeding - matched {matched_dt.strftime('%H:%M')} UTC ({matched_day})")


if __name__ == "__main__":
    cfg = load_config()
    now_utc = datetime.now(timezone.utc)
    today = now_utc.strftime("%Y-%m-%d")
    day_key = DAYS[now_utc.weekday()]
    forward_window = _forward_window_minutes()

    print("\n" + "=" * 55)
    print("  schedule_checker.py - diagnostic")
    print("=" * 55)
    print(f"  Now (UTC):      {now_utc.strftime('%Y-%m-%d %H:%M')}")
    print(f"  Day:            {day_key.upper()}")
    print(f"  Paused:         {cfg['paused']}")
    print(f"  Pause until:    {cfg.get('pause_until') or '(none)'}")
    print(f"  Skip today:     {today in cfg.get('skip_dates', [])}")
    print(f"  Force today:    {today in cfg.get('force_dates', [])}")
    print(f"  Forward window: {forward_window}min")
    print(f"  Backward grace: {_backward_grace_minutes()}min")
    print("=" * 55)

    matched_dt, matched_day, matched_status = _find_relevant_slot(cfg, now_utc, forward_window)
    if matched_dt:
        print(f"\n  -> Relevant slot: YES ({matched_dt.strftime('%H:%M')} UTC, {matched_day}, {matched_status})\n")
    else:
        print("\n  -> Relevant slot: NO\n")
