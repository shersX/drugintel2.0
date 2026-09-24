"""混合检索：向量 + 全文，RRF 融合。"""

from __future__ import annotations

from typing import Dict, List, Tuple

from sqlalchemy.orm import Session

from backend.src.models.news import News
from backend.src.search.fulltext import fulltext_search
from backend.src.search.vector import vector_search


def rrf_fuse(
    ranked_lists: List[List[Tuple[News, float]]],
    *,
    k: int = 60,
    weights: List[float] | None = None,
) -> List[Tuple[News, float]]:
    """
    Reciprocal Rank Fusion。
    score(d) = Σ w_i / (k + rank_i(d))
    """
    if weights is None:
        weights = [1.0] * len(ranked_lists)
    scores: Dict[int, float] = {}
    docs: Dict[int, News] = {}
    for w, ranked in zip(weights, ranked_lists):
        for rank, (news, _raw) in enumerate(ranked, start=1):
            docs[news.id] = news
            scores[news.id] = scores.get(news.id, 0.0) + w / (k + rank)
    ordered = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [(docs[i], s) for i, s in ordered]


def hybrid_search(
    session: Session,
    query: str,
    query_embedding: List[float],
    *,
    top_k: int = 10,
    vector_weight: float = 0.6,
    text_weight: float = 0.4,
) -> List[Tuple[News, float]]:
    vector_hits = vector_search(session, query_embedding, top_k=top_k * 2)
    text_hits = fulltext_search(session, query, top_k=top_k * 2)
    fused = rrf_fuse(
        [vector_hits, text_hits],
        weights=[vector_weight, text_weight],
    )
    return fused[:top_k]
