"""混合检索：余弦向量 + BM25，RRF 融合。"""

from __future__ import annotations

import os
from typing import Dict, List, Tuple

from sqlalchemy.orm import Session

from backend.src.models.news import News
from backend.src.search.bm25 import bm25_search
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


def _hybrid_weights() -> Tuple[float, float]:
    """优先 rag_config；失败则 HYBRID_* 环境变量。rrf_k 固定由 rrf_fuse 默认 60。"""
    try:
        from backend.src.rag.settings import load_rag_settings

        s = load_rag_settings()
        return s.hybrid_vector_weight, s.hybrid_bm25_weight
    except Exception:
        pass
    vector_w = float(os.getenv("HYBRID_VECTOR_WEIGHT", "0.6"))
    bm25_w = float(os.getenv("HYBRID_BM25_WEIGHT", "0.4"))
    total = vector_w + bm25_w
    if total <= 0:
        return 0.6, 0.4
    return vector_w / total, bm25_w / total


def hybrid_search(
    session: Session,
    query: str,
    query_embedding: List[float],
    *,
    top_k: int = 10,
    vector_weight: float | None = None,
    text_weight: float | None = None,
) -> List[Tuple[News, float]]:
    """
    余弦相似度（摘要 1024 维）+ BM25，RRF 融合。
    text_weight 兼容旧参数名，含义为 BM25 权重。
    """
    default_v, default_b = _hybrid_weights()
    vw = default_v if vector_weight is None else float(vector_weight)
    bw = default_b if text_weight is None else float(text_weight)
    vector_hits = vector_search(session, query_embedding, top_k=top_k * 2)
    bm25_hits = bm25_search(session, query, top_k=top_k * 2)
    fused = rrf_fuse(
        [vector_hits, bm25_hits],
        weights=[vw, bw],
    )
    return fused[:top_k]
