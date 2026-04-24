import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from src.schedule_checker import _check_and_set_post_lock, _find_relevant_slot


class ScheduleCheckerTests(unittest.TestCase):
    def test_does_not_shift_friday_evening_slot_to_thursday_night_local(self):
        cfg = {
            "weekly": {
                "mon": {"enabled": False},
                "tue": {"enabled": False},
                "wed": {"enabled": False},
                "thu": {"enabled": False},
                "fri": {
                    "enabled": True,
                    "time_local": "20:30",
                    "time_tz": "America/New_York",
                    "time_utc": "00:30",
                },
                "sat": {"enabled": False},
                "sun": {"enabled": False},
            },
            "skip_dates": [],
            "force_dates": [],
        }

        matched_dt, matched_day, matched_status = _find_relevant_slot(
            cfg,
            datetime(2026, 4, 24, 1, 20, tzinfo=timezone.utc),
            window_min=59,
        )

        self.assertIsNone(matched_dt)
        self.assertEqual(matched_day, "")
        self.assertEqual(matched_status, "")

    def test_returns_upcoming_slot_within_next_hour(self):
        cfg = {
            "weekly": {
                "mon": {"enabled": False},
                "tue": {"enabled": False},
                "wed": {"enabled": False},
                "thu": {"enabled": False},
                "fri": {
                    "enabled": True,
                    "time_local": "20:30",
                    "time_tz": "America/New_York",
                    "time_utc": "00:30",
                },
                "sat": {"enabled": False},
                "sun": {"enabled": False},
            },
            "skip_dates": [],
            "force_dates": [],
        }

        matched_dt, matched_day, matched_status = _find_relevant_slot(
            cfg,
            datetime(2026, 4, 25, 0, 10, tzinfo=timezone.utc),
            window_min=59,
        )

        self.assertIsNotNone(matched_dt)
        self.assertEqual(matched_day, "fri")
        self.assertEqual(matched_status, "upcoming")
        self.assertEqual(matched_dt.isoformat(), "2026-04-25T00:30:00+00:00")

    def test_returns_recent_slot_within_backward_grace(self):
        cfg = {
            "weekly": {
                "mon": {"enabled": False},
                "tue": {"enabled": False},
                "wed": {"enabled": False},
                "thu": {
                    "enabled": True,
                    "time_tz": "America/New_York",
                    "time_utc": "13:30",
                },
                "fri": {"enabled": False},
                "sat": {"enabled": False},
                "sun": {"enabled": False},
            },
            "skip_dates": [],
            "force_dates": [],
        }

        matched_dt, matched_day, matched_status = _find_relevant_slot(
            cfg,
            datetime(2026, 4, 23, 13, 50, tzinfo=timezone.utc),
            window_min=59,
        )

        self.assertIsNotNone(matched_dt)
        self.assertEqual(matched_day, "thu")
        self.assertEqual(matched_status, "recent")
        self.assertEqual(matched_dt.isoformat(), "2026-04-23T13:30:00+00:00")

    def test_utc_slot_plus_timezone_stays_on_correct_local_day(self):
        cfg = {
            "weekly": {
                "mon": {"enabled": False},
                "tue": {"enabled": False},
                "wed": {"enabled": False},
                "thu": {"enabled": False},
                "fri": {
                    "enabled": True,
                    "time_tz": "America/New_York",
                    "time_utc": "00:30",
                },
                "sat": {"enabled": False},
                "sun": {"enabled": False},
            },
            "skip_dates": [],
            "force_dates": [],
        }

        matched_dt, matched_day, matched_status = _find_relevant_slot(
            cfg,
            datetime(2026, 4, 25, 0, 10, tzinfo=timezone.utc),
            window_min=59,
        )
        self.assertIsNotNone(matched_dt)
        self.assertEqual(matched_day, "fri")
        self.assertEqual(matched_status, "upcoming")
        self.assertEqual(matched_dt.isoformat(), "2026-04-25T00:30:00+00:00")

    def test_post_lock_blocks_same_slot_twice(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            lock_path = Path(temp_dir) / ".post_lock.json"
            matched_dt = datetime(2026, 4, 25, 0, 30, tzinfo=timezone.utc)

            with patch("src.schedule_checker.LOCK_FILE", lock_path):
                self.assertTrue(_check_and_set_post_lock(matched_dt))
                self.assertFalse(_check_and_set_post_lock(matched_dt))

                saved = json.loads(lock_path.read_text(encoding="utf-8"))
                self.assertIn("2026-04-25_00:30", saved)


if __name__ == "__main__":
    unittest.main()
