#!/usr/bin/env python3
"""标题去重单元测试（不联网）。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.src.processors.deduplicator import deduplicate_by_title, normalize_title


class TestDeduplicator(unittest.TestCase):
    def test_normalize_title(self) -> None:
        self.assertEqual(normalize_title(" Hello, World! "), normalize_title("hello world"))

    def test_batch_dedup(self) -> None:
        items = [
            {"title": "FDA 批准新药", "full_text": "a"},
            {"title": "FDA批准新药", "full_text": "b"},
            {"title": "另一条新闻", "full_text": "c"},
        ]
        kept = deduplicate_by_title(items)
        self.assertEqual(len(kept), 2)
        self.assertEqual(kept[0]["full_text"], "a")

    def test_against_existing(self) -> None:
        items = [{"title": "已有标题", "full_text": "x"}]
        kept = deduplicate_by_title(items, existing_titles=["已有标题"])
        self.assertEqual(kept, [])


if __name__ == "__main__":
    unittest.main()
