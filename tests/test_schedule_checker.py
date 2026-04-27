"""
tests/test_schedule_checker.py
Exhaustive pytest suite for src/schedule_checker.py
Run: pytest -v tests/test_schedule_checker.py
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from unittest.mock import patch

import pytest

# Silence schedule_checker's own logging during tests
import src.schedule_checker as sc
sc.info = lambda m: None
sc.warn  = lambda m: None

from src.schedule_checker import (
    _check_and_set_post_lock,
    _find_matching_slot,
    _find_relevant_slot,        # backwards-compat alias
    _most_recent_weekday_date,
    _slot_utc_datetimes_for_day,
    load_config,
    DAYS,
    DAY_INDEX,
)

UTC = timezone.utc


# ── Helpers ───────────────────────────────────────────────────────────────────

def utc(y, mo, d, h, m):
    return datetime(y, mo, d, h, m, tzinfo=UTC)


def make_cfg(slots_by_day, skip_dates=None, disabled_days=None):
    """Build a minimal schedule_config dict for testing."""
    weekly = {}
    for day in DAYS:
        if day in slots_by_day:
            entry = {"enabled": True}
            s = slots_by_day[day]
            if isinstance(s, list):
                entry["times"] = s
            else:
                entry.update(s)
            weekly[day] = entry
        else:
            weekly[day] = {"enabled": True, "time_utc": "09:00"}
    if disabled_days:
        for d in disabled_days:
            weekly[d]["enabled"] = False
    return {
        "paused": False,
        "pause_until": None,
        "weekly": weekly,
        "skip_dates": skip_dates or [],
        "force_dates": [],
    }


WINDOW = 55  # minutes — matches workflow env SCHEDULE_WINDOW_MINUTES


# ── Section 1: Basic UTC slots, all 7 days ───────────────────────────────────

ANCHOR_MON = utc(2026, 4, 20, 0, 0)  # known Monday

@pytest.mark.parametrize("day_idx,day_name", list(enumerate(DAYS)))
def test_utc_slot_all_days(day_idx, day_name):
    """Each weekday's UTC slot is matched when the cron fires 30 min later."""
    slot_date = ANCHOR_MON + timedelta(days=day_idx)
    slot_dt   = slot_date.replace(hour=13, minute=30)
    now       = slot_date.replace(hour=14, minute=0)

    cfg = make_cfg({day_name: {"time_utc": "13:30"}})
    got_dt, got_day = _find_matching_slot(cfg, now, WINDOW)
    assert got_dt == slot_dt, f"{day_name}: expected {slot_dt}, got {got_dt}"
    assert got_day == day_name


# ── Section 2: Window boundary ───────────────────────────────────────────────

class TestWindowBoundary:
    slot_utc = utc(2026, 4, 22, 13, 30)  # Wednesday

    def _cfg(self):
        return make_cfg({"wed": {"time_utc": "13:30"}})

    def test_exactly_at_window_edge_matches(self):
        now = utc(2026, 4, 22, 14, 25)   # exactly 55 min after
        dt, day = _find_matching_slot(self._cfg(), now, WINDOW)
        assert dt == self.slot_utc
        assert day == "wed"

    def test_one_min_outside_no_match(self):
        now = utc(2026, 4, 22, 14, 26)   # 56 min after
        dt, day = _find_matching_slot(self._cfg(), now, WINDOW)
        assert dt is None

    def test_slot_well_in_future_no_match(self):
        now = utc(2026, 4, 22, 13, 4)   # 26 min before (beyond 20min lookahead)
        dt, day = _find_matching_slot(self._cfg(), now, WINDOW)
        assert dt is None

    def test_slot_in_lookahead_matches(self):
        now = utc(2026, 4, 22, 13, 25)   # 5 min before (within 20min lookahead)
        dt, day = _find_matching_slot(self._cfg(), now, WINDOW)
        assert dt == self.slot_utc
        assert day == "wed"

    def test_exactly_at_slot_time_matches(self):
        now = utc(2026, 4, 22, 13, 30)   # 0 min diff
        dt, day = _find_matching_slot(self._cfg(), now, WINDOW)
        assert dt == self.slot_utc
        assert day == "wed"


# ── Section 3: DST / local-time slots ────────────────────────────────────────

class TestDST:
    def test_edt_slot_april(self):
        """8:30 AM EDT (UTC-4) in April = 12:30 UTC."""
        slot_utc = utc(2026, 4, 23, 12, 30)
        cfg = make_cfg({"thu": {"time_local": "08:30", "time_tz": "America/New_York"}})
        now = utc(2026, 4, 23, 13, 0)
        dt, day = _find_matching_slot(cfg, now, WINDOW)
        assert dt == slot_utc
        assert day == "thu"

    def test_est_slot_january(self):
        """8:30 AM EST (UTC-5) in January = 13:30 UTC."""
        slot_utc = utc(2026, 1, 8, 13, 30)   # Thursday Jan 8
        cfg = make_cfg({"thu": {"time_local": "08:30", "time_tz": "America/New_York"}})
        now = utc(2026, 1, 8, 13, 55)
        dt, day = _find_matching_slot(cfg, now, WINDOW)
        assert dt == slot_utc
        assert day == "thu"

    def test_ist_local_slot(self):
        """10:00 AM IST (UTC+5:30) = 04:30 UTC."""
        slot_utc = utc(2026, 4, 20, 4, 30)   # Monday
        cfg = make_cfg({"mon": {"time_local": "10:00", "time_tz": "Asia/Kolkata"}})
        now = utc(2026, 4, 20, 5, 0)
        dt, day = _find_matching_slot(cfg, now, WINDOW)
        assert dt == slot_utc
        assert day == "mon"


# ── Section 4: Multi-slot days ───────────────────────────────────────────────

class TestMultiSlot:
    def _cfg(self):
        return make_cfg({"fri": [
            {"time_local": "08:30", "time_tz": "America/New_York"},
            {"time_local": "20:30", "time_tz": "America/New_York"},
        ]})

    def test_morning_slot_matches(self):
        # 8:30 AM EDT = 12:30 UTC; cron at 13:00 (30 min later)
        now = utc(2026, 4, 24, 13, 0)
        dt, day = _find_matching_slot(self._cfg(), now, WINDOW)
        assert dt == utc(2026, 4, 24, 12, 30)
        assert day == "fri"

    def test_evening_slot_matches(self):
        # 8:30 PM EDT = 00:30 UTC Sat; cron at 01:00 (30 min later)
        now = utc(2026, 4, 25, 1, 0)
        dt, day = _find_matching_slot(self._cfg(), now, WINDOW)
        assert dt == utc(2026, 4, 25, 0, 30)
        assert day == "fri"

    def test_picks_most_recent_when_both_in_window(self):
        """Two UTC slots 20 min apart, both in window — picks the later one."""
        cfg = make_cfg({"thu": [
            {"time_utc": "13:00"},
            {"time_utc": "13:20"},
        ]})
        now = utc(2026, 4, 23, 13, 45)   # 45 min after 13:00, 25 min after 13:20
        dt, day = _find_matching_slot(cfg, now, WINDOW)
        assert dt == utc(2026, 4, 23, 13, 20)
        assert day == "thu"

    def test_three_slots_per_day(self):
        cfg = make_cfg({"mon": [
            {"time_utc": "08:00"},
            {"time_utc": "13:00"},
            {"time_utc": "18:00"},
        ]})
        for slot_h, now_h in [(8, 8), (13, 13), (18, 18)]:
            now = utc(2026, 4, 20, now_h, 30)
            dt, day = _find_matching_slot(cfg, now, WINDOW)
            assert dt == utc(2026, 4, 20, slot_h, 0), f"slot at {slot_h}:00 missed"
            assert day == "mon"


# ── Section 5: Cross-midnight ─────────────────────────────────────────────────

class TestCrossMidnight:
    def test_late_local_slot_fires_next_utc_day(self):
        """Sun 11 PM EDT = Mon 03:00 UTC — caught 30 min later on Monday."""
        slot_utc = utc(2026, 4, 27, 3, 0)
        cfg = make_cfg({"sun": {"time_local": "23:00", "time_tz": "America/New_York"}})
        now = utc(2026, 4, 27, 3, 30)
        dt, day = _find_matching_slot(cfg, now, WINDOW)
        assert dt == slot_utc
        assert day == "sun"

    def test_2345_utc_slot_caught_by_midnight_cron(self):
        """Sat 23:45 UTC — caught by Sun 00:00 cron (15 min later)."""
        slot_utc = utc(2026, 4, 25, 23, 45)
        cfg = make_cfg({"sat": {"time_utc": "23:45"}})
        now = utc(2026, 4, 26, 0, 0)
        dt, day = _find_matching_slot(cfg, now, WINDOW)
        assert dt == slot_utc
        assert day == "sat"

    def test_midnight_utc_slot(self):
        """Slot at exactly 00:00 UTC — caught 30 min later."""
        slot_utc = utc(2026, 4, 26, 0, 0)
        cfg = make_cfg({"sun": {"time_utc": "00:00"}})
        now = utc(2026, 4, 26, 0, 30)
        dt, day = _find_matching_slot(cfg, now, WINDOW)
        assert dt == slot_utc
        assert day == "sun"


# ── Section 6: skip_dates ────────────────────────────────────────────────────

class TestSkipDates:
    def test_skipped_local_date_no_match(self):
        cfg = make_cfg(
            {"wed": {"time_local": "08:30", "time_tz": "America/New_York"}},
            skip_dates=["2026-04-22"],
        )
        now = utc(2026, 4, 22, 13, 0)
        dt, day = _find_matching_slot(cfg, now, WINDOW)
        assert dt is None

    def test_non_skipped_date_matches(self):
        cfg = make_cfg(
            {"wed": {"time_local": "08:30", "time_tz": "America/New_York"}},
            skip_dates=["2026-04-15"],   # different week
        )
        now = utc(2026, 4, 22, 13, 0)
        dt, day = _find_matching_slot(cfg, now, WINDOW)
        assert dt is not None
        assert day == "wed"


# ── Section 7: Disabled days ─────────────────────────────────────────────────

def test_disabled_day_no_match():
    cfg = make_cfg({"tue": {"time_utc": "13:30"}}, disabled_days=["tue"])
    now = utc(2026, 4, 21, 14, 0)
    dt, day = _find_matching_slot(cfg, now, WINDOW)
    assert dt is None


# ── Section 8: GitHub Actions cron drift ─────────────────────────────────────

class TestCronDrift:
    def test_late_cron_still_matches(self):
        """09:00 cron fires 47 min late at 09:47 — slot still in 55-min window."""
        slot_utc = utc(2026, 4, 20, 9, 0)
        cfg = make_cfg({"mon": {"time_utc": "09:00"}})
        now = utc(2026, 4, 20, 9, 47)
        dt, day = _find_matching_slot(cfg, now, WINDOW)
        assert dt == slot_utc
        assert day == "mon"

    def test_next_cron_outside_window(self):
        """10:00 cron fires 60 min after slot — outside 55-min window, no match."""
        cfg = make_cfg({"mon": {"time_utc": "09:00"}})
        now = utc(2026, 4, 20, 10, 0)
        dt, day = _find_matching_slot(cfg, now, WINDOW)
        assert dt is None

    def test_extreme_drift_no_double_post(self):
        """09:00 cron fires at 09:52 (matches). 10:03 cron: slot 63 min ago, no match."""
        cfg = make_cfg({"mon": {"time_utc": "09:00"}})
        slot_utc = utc(2026, 4, 20, 9, 0)

        dt1, day1 = _find_matching_slot(cfg, utc(2026, 4, 20, 9, 52), WINDOW)
        assert dt1 == slot_utc and day1 == "mon"

        dt2, day2 = _find_matching_slot(cfg, utc(2026, 4, 20, 10, 3), WINDOW)
        assert dt2 is None


# ── Section 9: All days active — only today fires ────────────────────────────

def test_only_matching_day_fires():
    cfg = make_cfg({d: {"time_utc": "13:30"} for d in DAYS})
    now = utc(2026, 4, 22, 14, 0)   # Wednesday
    dt, day = _find_matching_slot(cfg, now, WINDOW)
    assert dt == utc(2026, 4, 22, 13, 30)
    assert day == "wed"


def test_no_false_positive_yesterday_slot():
    """Wednesday cron must not fire Tuesday's slot from 24h ago."""
    cfg = make_cfg({"tue": {"time_utc": "13:30"}})
    now = utc(2026, 4, 22, 14, 0)   # Wednesday
    dt, day = _find_matching_slot(cfg, now, WINDOW)
    assert dt is None


# ── Section 10: Legacy time_ist ──────────────────────────────────────────────

def test_legacy_ist_slot():
    """15:00 IST = 09:30 UTC — legacy time_ist field."""
    slot_utc = utc(2026, 4, 20, 9, 30)
    cfg = make_cfg({"mon": {"time_ist": "15:00"}})
    now = utc(2026, 4, 20, 10, 0)
    dt, day = _find_matching_slot(cfg, now, WINDOW)
    assert dt == slot_utc
    assert day == "mon"


# ── Section 11: Full week simulation ─────────────────────────────────────────

@pytest.mark.parametrize("day_name,slot_utc_dt", [
    ("mon", utc(2026, 4, 20, 12, 30)),
    ("tue", utc(2026, 4, 21, 12, 30)),
    ("wed", utc(2026, 4, 22, 12, 30)),
    ("thu", utc(2026, 4, 23, 12, 30)),
    ("fri", utc(2026, 4, 24, 12, 30)),
    ("sat", utc(2026, 4, 25, 12, 30)),
    ("sun", utc(2026, 4, 26, 12, 30)),
])
def test_full_week_830am_edt(day_name, slot_utc_dt):
    """8:30 AM EDT every day of the week — all fire correctly."""
    cfg = make_cfg({d: {"time_local": "08:30", "time_tz": "America/New_York"} for d in DAYS})
    now = slot_utc_dt + timedelta(minutes=30)
    dt, day = _find_matching_slot(cfg, now, WINDOW)
    assert dt == slot_utc_dt, f"{day_name}: expected {slot_utc_dt}, got {dt}"
    assert day == day_name


# ── Section 12: Slot lock (_check_and_set_post_lock) ─────────────────────────

class TestPostLock:
    def test_first_claim_succeeds(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sc, "LOCK_FILE", tmp_path / ".post_lock.json")
        slot = utc(2026, 4, 22, 13, 30)
        assert _check_and_set_post_lock(slot) is True

    def test_second_claim_blocked(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sc, "LOCK_FILE", tmp_path / ".post_lock.json")
        slot = utc(2026, 4, 22, 13, 30)
        assert _check_and_set_post_lock(slot) is True
        assert _check_and_set_post_lock(slot) is False

    def test_different_slots_both_succeed(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sc, "LOCK_FILE", tmp_path / ".post_lock.json")
        slot1 = utc(2026, 4, 22, 9, 0)
        slot2 = utc(2026, 4, 22, 13, 30)
        assert _check_and_set_post_lock(slot1) is True
        assert _check_and_set_post_lock(slot2) is True

    def test_old_entries_pruned(self, tmp_path, monkeypatch):
        lock_file = tmp_path / ".post_lock.json"
        monkeypatch.setattr(sc, "LOCK_FILE", lock_file)
        # Write an entry 3 days old (should be pruned)
        old_key = (utc(2026, 4, 19, 9, 0)).strftime("%Y-%m-%d_%H:%M")
        lock_file.write_text(json.dumps({old_key: "2026-04-19T09:00:00+00:00"}))
        slot = utc(2026, 4, 22, 13, 30)
        assert _check_and_set_post_lock(slot) is True
        locks = json.loads(lock_file.read_text())
        assert old_key not in locks

    def test_lock_file_written_to_disk(self, tmp_path, monkeypatch):
        lock_file = tmp_path / ".post_lock.json"
        monkeypatch.setattr(sc, "LOCK_FILE", lock_file)
        slot = utc(2026, 4, 22, 13, 30)
        _check_and_set_post_lock(slot)
        assert lock_file.exists()
        data = json.loads(lock_file.read_text())
        assert "2026-04-22_13:30" in data


# ── Section 13: _find_relevant_slot backwards-compat alias ───────────────────

def test_find_relevant_slot_alias_returns_three_tuple():
    cfg = make_cfg({"wed": {"time_utc": "13:30"}})
    now = utc(2026, 4, 22, 14, 0)
    result = _find_relevant_slot(cfg, now, WINDOW)
    assert len(result) == 3
    dt, day, status = result
    assert dt == utc(2026, 4, 22, 13, 30)
    assert day == "wed"
    assert status == "recent"


def test_find_relevant_slot_alias_no_match():
    cfg = make_cfg({"wed": {"time_utc": "13:30"}})
    now = utc(2026, 4, 22, 9, 0)   # slot is 4.5h in the future
    dt, day, status = _find_relevant_slot(cfg, now, WINDOW)
    assert dt is None
    assert day == ""
    assert status == ""


# ── Section 14: load_config defaults ─────────────────────────────────────────

def test_load_config_missing_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = load_config()
    assert cfg["paused"] is False
    assert "mon" in cfg["weekly"]
    assert cfg["weekly"]["mon"]["enabled"] is True


def test_load_config_respects_paused(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "schedule_config.json").write_text(
        json.dumps({"paused": True, "weekly": {}})
    )
    cfg = load_config()
    assert cfg["paused"] is True
