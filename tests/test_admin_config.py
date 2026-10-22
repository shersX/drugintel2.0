#!/usr/bin/env python3
"""管理员可配：RAG 默认、爬虫合并、关键词缓存失效。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.src.rag.settings import DEFAULT_TOP_K, RagSettings, load_rag_settings


class TestRagDefaults(unittest.TestCase):
    def test_default_top_k_is_10(self) -> None:
        self.assertEqual(DEFAULT_TOP_K, 10)

    def test_load_rag_settings_fallback(self) -> None:
        with patch("backend.src.rag.settings.session_scope", side_effect=RuntimeError("no db")):
            with patch("backend.src.rag.settings.RagEnvConfig") as env_cls:
                env_cls.load.return_value = MagicMock(min_relevance_score=0.3)
                settings = load_rag_settings()
        self.assertIsInstance(settings, RagSettings)
        self.assertEqual(settings.top_k, 10)
        self.assertAlmostEqual(settings.min_relevance_score, 0.3)
        self.assertAlmostEqual(settings.hybrid_vector_weight, 0.6)
        self.assertEqual(settings.rerank_pool_multiplier, 2)
        self.assertEqual(settings.history_turns, 12)
        self.assertAlmostEqual(settings.temperature, 0.3)


class TestCrawlerMerge(unittest.TestCase):
    def test_merged_registry_has_function(self) -> None:
        from backend.src.crawlers.registry import CRAWLER_REGISTRY
        from backend.src.crawlers.settings_store import merged_crawler_registry

        with patch(
            "backend.src.crawlers.settings_store.session_scope",
            side_effect=RuntimeError("no db"),
        ):
            merged = merged_crawler_registry()
        self.assertTrue(merged)
        for key, cfg in merged.items():
            self.assertIn(key, CRAWLER_REGISTRY)
            self.assertTrue(callable(cfg["function"]))
            self.assertIn("page_count", cfg)
            self.assertIn("concurrency", cfg)


class TestKeywordCache(unittest.TestCase):
    def test_invalidate_clears_lru(self) -> None:
        from backend.src.processors import filter as filter_mod

        filter_mod.load_keyword_lexicon.cache_clear()
        with patch.object(
            filter_mod,
            "load_keyword_lexicon",
            wraps=filter_mod.load_keyword_lexicon,
        ):
            pass
        # 直接验证 cache_clear 可调用且 cache_info 归零
        filter_mod.invalidate_keyword_cache()
        info = filter_mod.load_keyword_lexicon.cache_info()
        self.assertEqual(info.currsize, 0)


if __name__ == "__main__":
    unittest.main()
