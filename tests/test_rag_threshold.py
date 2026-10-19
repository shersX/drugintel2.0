#!/usr/bin/env python3
"""相关性阈值过滤单测。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.src.rag.threshold import filter_by_relevance


class TestRelevanceThreshold(unittest.TestCase):
    def test_keeps_above_threshold(self) -> None:
        a = SimpleNamespace(id=1)
        b = SimpleNamespace(id=2)
        hits = [(a, 0.8), (b, 0.1)]  # type: ignore[list-item]
        kept = filter_by_relevance(hits, min_score=0.25)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0][0].id, 1)

    def test_all_below_returns_empty(self) -> None:
        a = SimpleNamespace(id=1)
        b = SimpleNamespace(id=2)
        hits = [(a, 0.1), (b, 0.05)]  # type: ignore[list-item]
        kept = filter_by_relevance(hits, min_score=0.25)
        self.assertEqual(kept, [])

    def test_disabled_when_non_positive(self) -> None:
        a = SimpleNamespace(id=1)
        hits = [(a, 0.01)]  # type: ignore[list-item]
        kept = filter_by_relevance(hits, min_score=0.0)
        self.assertEqual(len(kept), 1)


if __name__ == "__main__":
    unittest.main()
