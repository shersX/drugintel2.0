#!/usr/bin/env python3
"""为存量新闻回填 search_tsv：uv run python scripts/backfill_search_tsv.py"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.src.db.schema import ensure_schema
from backend.src.db.session import session_scope
from backend.src.search.bm25 import invalidate_bm25_stats
from backend.src.search.tsv import backfill_search_tsv


def main() -> None:
    ensure_schema()
    with session_scope() as session:
        n = backfill_search_tsv(session)
    invalidate_bm25_stats()
    print(f"search_tsv 回填完成: {n}")


if __name__ == "__main__":
    main()
