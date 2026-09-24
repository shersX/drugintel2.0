"""简单全文检索（标题/摘要/正文 ILIKE，后续可换 tsvector）。"""

from __future__ import annotations

from typing import List, Tuple

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from backend.src.models.news import News


def fulltext_search(
    session: Session,
    query: str,
    *,
    top_k: int = 10,
) -> List[Tuple[News, float]]:
    """
    基于子串匹配的召回；分数按字段权重粗排（标题命中 > 摘要 > 正文）。
    """
    q = (query or "").strip()
    if not q:
        return []
    pattern = f"%{q}%"
    rows = session.scalars(
        select(News)
        .where(
            or_(
                News.title.ilike(pattern),
                News.abstract.ilike(pattern),
                News.content.ilike(pattern),
            )
        )
        .limit(max(top_k * 3, 30))
    ).all()

    scored: List[Tuple[News, float]] = []
    q_lower = q.lower()
    for news in rows:
        score = 0.0
        title = (news.title or "").lower()
        abstract = (news.abstract or "").lower()
        content = (news.content or "").lower()
        if q_lower in title:
            score += 3.0
        if q_lower in abstract:
            score += 2.0
        if q_lower in content:
            score += 1.0
        if score > 0:
            scored.append((news, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]
