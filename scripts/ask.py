#!/usr/bin/env python3
"""命令行问答联调：uv run python scripts/ask.py "司美格鲁肽最新进展" """

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.src.rag.qa import ask


async def main() -> None:
    query = " ".join(sys.argv[1:]).strip() or "最近有哪些医药新闻？"
    result = await ask(query)
    print(f"意图: {result.intent.intent.value} ({result.intent.confidence})")
    print("--- 回答 ---")
    print(result.answer)
    print("--- 来源 ---")
    for s in result.sources:
        print(f"  [{s['id']}] {s['title'][:80]} (score={s['score']:.3f})")


if __name__ == "__main__":
    asyncio.run(main())
