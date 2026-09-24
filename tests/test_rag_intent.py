#!/usr/bin/env python3
"""意图识别与 RRF 单测。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.src.rag.intent import Intent, classify_intent
from backend.src.search.hybrid import rrf_fuse


class TestIntent(unittest.TestCase):
    def test_drug(self) -> None:
        self.assertEqual(classify_intent("这款抑制剂的适应症是什么").intent, Intent.DRUG_INFO)

    def test_compare(self) -> None:
        self.assertEqual(classify_intent("对比两家公司管线差异").intent, Intent.COMPARE)

    def test_default_news(self) -> None:
        self.assertEqual(classify_intent("FDA 最近批准了什么").intent, Intent.NEWS_QUERY)


class TestRRF(unittest.TestCase):
    def test_fuse_order(self) -> None:
        a = SimpleNamespace(id=1)
        b = SimpleNamespace(id=2)
        c = SimpleNamespace(id=3)
        fused = rrf_fuse(
            [[(a, 0.9), (b, 0.8)], [(b, 1.0), (c, 0.5)]],  # type: ignore[list-item]
            weights=[0.6, 0.4],
        )
        self.assertEqual(fused[0][0].id, 2)


if __name__ == "__main__":
    unittest.main()
