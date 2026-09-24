"""向量检索（pgvector 余弦距离）。"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from backend.src.models.news import News


def vector_search(
    session: Session,
    query_embedding: Sequence[float],
    *,
    top_k: int = 10,
    threshold: float = 0.0,
) -> List[Tuple[News, float]]:
    """
    返回 (News, similarity) 列表，similarity = 1 - cosine_distance。
    """
    if not query_embedding:
        return []
    # pgvector: <=> 为余弦距离
    emb_literal = "[" + ",".join(str(float(x)) for x in query_embedding) + "]"
    sql = text(
        """
        SELECT id,
               1 - (embedding <=> CAST(:emb AS vector)) AS similarity
        FROM news
        WHERE embedding IS NOT NULL
          AND 1 - (embedding <=> CAST(:emb AS vector)) > :threshold
        ORDER BY embedding <=> CAST(:emb AS vector)
        LIMIT :top_k
        """
    )
    rows = session.execute(
        sql,
        {"emb": emb_literal, "threshold": threshold, "top_k": top_k},
    ).all()
    if not rows:
        return []
    ids = [int(r[0]) for r in rows]
    sim_map = {int(r[0]): float(r[1]) for r in rows}
    news_rows = session.scalars(select(News).where(News.id.in_(ids))).all()
    by_id = {n.id: n for n in news_rows}
    return [(by_id[i], sim_map[i]) for i in ids if i in by_id]
