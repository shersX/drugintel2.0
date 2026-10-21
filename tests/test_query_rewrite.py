#!/usr/bin/env python3
"""query_rewrite JSON 解析与回退。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.src.rag.query_rewrite import RewriteResult, _parse_rewrite_json, rewrite_query


class TestParseRewrite(unittest.TestCase):
    def test_parse_ok(self) -> None:
        raw = '{"search_query":"诺和诺德 GLP-1 三期","need_clarify":false,"clarify_question":null,"confidence":0.8}'
        result = _parse_rewrite_json(raw, fallback_query="它怎么样")
        self.assertEqual(result.search_query, "诺和诺德 GLP-1 三期")
        self.assertFalse(result.need_clarify)
        self.assertIsNone(result.clarify_question)

    def test_parse_clarify(self) -> None:
        raw = '{"search_query":"那个药","need_clarify":true,"clarify_question":"您指的是哪款药物？","confidence":0.4}'
        result = _parse_rewrite_json(raw, fallback_query="那个药")
        self.assertTrue(result.need_clarify)
        self.assertIn("药物", result.clarify_question or "")

    def test_parse_invalid_fallback(self) -> None:
        result = _parse_rewrite_json("not json", fallback_query="原句")
        self.assertEqual(result.search_query, "原句")
        self.assertFalse(result.need_clarify)


class TestRewriteFallback(unittest.IsolatedAsyncioTestCase):
    async def test_llm_failure_falls_back(self) -> None:
        with patch("backend.src.rag.query_rewrite.SiliconFlowClient") as cls:
            client = cls.from_env.return_value
            client.chat_completion = AsyncMock(side_effect=RuntimeError("boom"))
            result = await rewrite_query("GLP-1 新闻", client=client)
        self.assertIsInstance(result, RewriteResult)
        self.assertEqual(result.search_query, "GLP-1 新闻")
        self.assertFalse(result.need_clarify)


if __name__ == "__main__":
    unittest.main()
