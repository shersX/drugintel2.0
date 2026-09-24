#!/usr/bin/env python3
"""告警匹配单测。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.src.alerts.matcher import match_news_to_watchlists


class TestAlertMatch(unittest.TestCase):
    def test_match_keyword(self) -> None:
        news = SimpleNamespace(
            title="司美格鲁肽新适应症获批",
            abstract="体重管理",
            content="",
        )
        wl_hit = SimpleNamespace(enabled=True, entity_name="司美格鲁肽", email="a@b.com")
        wl_miss = SimpleNamespace(enabled=True, entity_name="无关词", email="a@b.com")
        hits = match_news_to_watchlists(news, [wl_hit, wl_miss])  # type: ignore[arg-type]
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].entity_name, "司美格鲁肽")


if __name__ == "__main__":
    unittest.main()
