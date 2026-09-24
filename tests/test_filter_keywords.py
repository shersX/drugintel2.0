#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""关键词过滤模块单元测试（不联网）。"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.src.processors.filter import (
    KeywordMatcher,
    filter_news_items,
    filter_results_by_keywords,
    load_keyword_lexicon,
    load_keywords_config,
)


def test_load_keywords_not_empty() -> None:
    cfg = load_keywords_config()
    assert "PD-1" in cfg or "辉瑞" in cfg
    lex = load_keyword_lexicon()
    assert lex.category_by_canonical.get("辉瑞") == "公司"
    assert lex.category_by_canonical.get("PD-1") == "靶点"


def test_matcher_chinese_substring() -> None:
    lex = load_keyword_lexicon()
    m = KeywordMatcher(lex.keyword_map)
    hits = m.match_text("该公司为辉瑞制药在华合作伙伴")
    assert "辉瑞" in hits


def test_matcher_ascii_mixed_pd1() -> None:
    lex = load_keyword_lexicon()
    m = KeywordMatcher(lex.keyword_map)
    assert "PD-1" in m.match_text("We study anti PD-1 combination therapy")
    assert "PD-1" in m.match_text("CD279 expression reported")


def test_filter_news_items_keeps_hits_only() -> None:
    lex = load_keyword_lexicon()
    m = KeywordMatcher(lex.keyword_map)
    items = [
        {"title": "无命中", "full_text": "hello world"},
        {"title": "命中礼来", "full_text": "Eli Lilly announced"},
    ]
    out = filter_news_items(
        items,
        matcher=m,
        keywords_config=lex.keyword_map,
        category_by_canonical=lex.category_by_canonical,
    )
    assert len(out) == 1
    assert out[0]["title"] == "命中礼来"
    assert "礼来" in out[0]["matched_keywords"]
    assert any(h["canonical"] == "礼来" and h["category"] == "公司" for h in out[0]["matched_keyword_hits"])


def test_filter_results_bioon_keeps_all() -> None:
    lex = load_keyword_lexicon()
    m = KeywordMatcher(lex.keyword_map)
    results = {
        "bioon": [
            {"title": "a", "full_text": "no keyword here"},
            {"title": "b", "full_text": "Pfizer news"},
        ],
        "prnewswire": [
            {"title": "x", "full_text": "nothing"},
            {"title": "y", "full_text": "Pfizer Inc. press"},
        ],
    }
    out = filter_results_by_keywords(results, matcher=m, keywords_config=lex.keyword_map)
    assert len(out["bioon"]) == 2
    assert out["bioon"][0]["matched_keywords"] == []
    assert "辉瑞" in out["bioon"][1]["matched_keywords"]
    assert len(out["prnewswire"]) == 1


if __name__ == "__main__":
    test_load_keywords_not_empty()
    test_matcher_chinese_substring()
    test_matcher_ascii_mixed_pd1()
    test_filter_news_items_keeps_hits_only()
    test_filter_results_bioon_keeps_all()
    print("filter keyword tests: OK")
