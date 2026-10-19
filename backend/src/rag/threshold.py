"""检索结果相关性阈值过滤。"""

from __future__ import annotations

from typing import List, Sequence, Tuple, TypeVar

from backend.src.core.logger import get_logger
from backend.src.models.news import News

logger = get_logger("rag.threshold")

T = TypeVar("T")


def filter_by_relevance(
    hits: Sequence[Tuple[News, float]],
    *,
    min_score: float | None = None,
) -> List[Tuple[News, float]]:
    """
    保留 score >= min_score 的结果。
    若全部低于阈值，返回空列表（调用方不应再展示来源）。
    min_score <= 0 时关闭过滤。
    """
    if min_score is None:
        from backend.src.rag.settings import load_rag_settings

        threshold = load_rag_settings().min_relevance_score
    else:
        threshold = float(min_score)
    if not hits:
        return []
    if threshold <= 0:
        return list(hits)

    kept = [(news, score) for news, score in hits if float(score) >= threshold]
    if not kept:
        best = max(float(s) for _, s in hits)
        logger.info(
            "检索结果均低于阈值，已清空来源 threshold=%.4f best=%.4f count=%s",
            threshold,
            best,
            len(hits),
        )
    elif len(kept) < len(hits):
        logger.info(
            "相关性过滤保留 %s/%s 条 threshold=%.4f",
            len(kept),
            len(hits),
            threshold,
        )
    return kept
