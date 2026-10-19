"""全文 / BM25 检索入口（兼容旧 import 名 fulltext_search）。"""

from __future__ import annotations

from typing import List, Tuple

from sqlalchemy.orm import Session

from backend.src.models.news import News
from backend.src.search.bm25 import bm25_search


def fulltext_search(
    session: Session,
    query: str,
    *,
    top_k: int = 10,
) -> List[Tuple[News, float]]:
    """BM25 检索（内部实现见 bm25_search）。"""
    return bm25_search(session, query, top_k=top_k)
