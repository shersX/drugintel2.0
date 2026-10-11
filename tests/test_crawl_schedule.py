"""采集节奏判断，不连接数据库。"""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.src.crawl.schedule import (  # noqa: E402
    CrawlConfigError,
    compute_next_run,
    daily_due,
    hourly_due,
    parse_daily_time,
)

SH = ZoneInfo("Asia/Shanghai")


def at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 10, 11, hour, minute, tzinfo=SH)


class ScheduleTests(unittest.TestCase):
    def test_parse_daily_time(self):
        self.assertEqual(parse_daily_time("08:30"), (8, 30))
        with self.assertRaises(CrawlConfigError):
            parse_daily_time("25:00")

    def test_hourly_waits_one_hour_and_skips_running(self):
        start = at(9)
        self.assertFalse(hourly_due(start, "success", at(9, 30)))
        self.assertTrue(hourly_due(start, "success", at(10)))
        self.assertFalse(hourly_due(start, "running", at(11)))
        self.assertTrue(hourly_due(None, None, at(9)))

    def test_daily_slot_after_arming(self):
        armed = at(7)
        self.assertFalse(daily_due(at(7, 30), armed, "08:00", False))
        self.assertTrue(daily_due(at(8), armed, "08:00", False))
        self.assertFalse(daily_due(at(8, 5), armed, "08:00", True))
        self.assertFalse(daily_due(at(15), at(15), "08:00", False))

    def test_next_run(self):
        nxt = compute_next_run(
            mode="hourly",
            daily_time=None,
            armed_at=at(9),
            last_started=at(9),
            scheduled_today=False,
            now=at(9, 10),
        )
        self.assertEqual(nxt, at(9) + timedelta(hours=1))

        later = compute_next_run(
            mode="daily",
            daily_time="08:00",
            armed_at=at(15),
            last_started=at(15),
            scheduled_today=False,
            now=at(15, 5),
        )
        self.assertEqual(later, at(8) + timedelta(days=1))


if __name__ == "__main__":
    unittest.main()
