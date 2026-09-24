#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LLM 相关性判断（可注入 client，不依赖真实联网）。"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import List, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.src.processors.relevance import (
    annotate_relevance_for_items,
    check_relevance_async,
    parse_relevance_reply,
)


class FakeLLM:
    def __init__(self, reply: str) -> None:
        self.reply = reply

    async def chat_completion(
        self,
        messages: List[Mapping[str, str]],
        *,
        temperature: float = 0.0,
        max_tokens: int = 32,
    ) -> str:
        return self.reply


def test_parse_relevance_reply() -> None:
    assert parse_relevance_reply("是") is True
    assert parse_relevance_reply("否") is False
    assert parse_relevance_reply("不是") is False
    assert parse_relevance_reply("是的\n其它") is True
    assert parse_relevance_reply("yes") is True
    assert parse_relevance_reply("no") is False


async def _test_check_async() -> None:
    fake = FakeLLM("是")
    ok = await check_relevance_async(
        "某药临床结果",
        "Phase III trial for diabetes",
        client=fake,
    )
    assert ok is True


def test_annotate_relevance() -> None:
    fake = FakeLLM("否")
    items = [
        {
            "title": "体育新闻",
            "description": "",
            "full_text": "足球比赛结果",
        }
    ]
    out = asyncio.run(annotate_relevance_for_items(items, client=fake))
    assert len(out) == 1
    assert out[0]["relevance_ok"] is False


if __name__ == "__main__":
    test_parse_relevance_reply()
    asyncio.run(_test_check_async())
    test_annotate_relevance()
    print("relevance tests: OK")
