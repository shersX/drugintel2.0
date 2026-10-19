#!/usr/bin/env python3
"""BM25 打分与分词单测。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.src.search.bm25 import bm25_score_document
from backend.src.search.hybrid import rrf_fuse
from backend.src.search.tokenize import tokenize, tokens_to_ts_text, tokens_to_tsquery_parts


class TestTokenize(unittest.TestCase):
    def test_chinese_drug_name(self) -> None:
        tokens = tokenize("司美格鲁肽最新进展")
        self.assertTrue(tokens)
        joined = " ".join(tokens)
        self.assertIn("司美格鲁肽", joined)

    def test_ts_text_and_query(self) -> None:
        text = tokens_to_ts_text("KRAS G12C 抑制剂")
        self.assertTrue(text)
        parts = tokens_to_tsquery_parts("KRAS G12C")
        self.assertTrue(parts)
        self.assertTrue(any("kras" in p.lower() for p in parts))


class TestBM25Score(unittest.TestCase):
    def test_relevant_doc_ranks_higher(self) -> None:
        query = ["司美格鲁肽", "临床"]
        doc_hit = tokenize("司美格鲁肽三期临床数据公布")
        doc_miss = tokenize("今日股市行情与宏观经济")
        df = {"司美格鲁肽": 1, "临床": 2, "数据": 5, "今日": 10}
        score_hit = bm25_score_document(
            query, doc_hit, n_docs=100, avgdl=8.0, df_map=df
        )
        score_miss = bm25_score_document(
            query, doc_miss, n_docs=100, avgdl=8.0, df_map=df
        )
        self.assertGreater(score_hit, score_miss)
        self.assertGreater(score_hit, 0.0)

    def test_empty_returns_zero(self) -> None:
        self.assertEqual(
            bm25_score_document([], ["a"], n_docs=1, avgdl=1.0, df_map={}),
            0.0,
        )


class TestHybridRRF(unittest.TestCase):
    def test_bm25_and_vector_fuse(self) -> None:
        a = SimpleNamespace(id=1)
        b = SimpleNamespace(id=2)
        c = SimpleNamespace(id=3)
        vector_hits = [(a, 0.9), (b, 0.7)]
        bm25_hits = [(b, 12.0), (c, 8.0)]
        fused = rrf_fuse(
            [vector_hits, bm25_hits],  # type: ignore[list-item]
            weights=[0.6, 0.4],
        )
        ids = [n.id for n, _ in fused]
        self.assertEqual(ids[0], 2)
        self.assertIn(1, ids)
        self.assertIn(3, ids)


if __name__ == "__main__":
    unittest.main()
