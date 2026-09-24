"""代表新闻选择（任务 4.3）。"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Sequence

from backend.src.clustering.clusterer import NewsPoint, cosine_similarity, mean_centroid


def select_representative_news(members: Sequence[NewsPoint]) -> Optional[NewsPoint]:
    """
    选择最接近簇中心向量的新闻作为代表。

    若相似度并列，取 publish_time 更新的一条；再并列取 id 更大者。
    """
    valid = [m for m in members if m.embedding]
    if not valid:
        return None
    if len(valid) == 1:
        return valid[0]

    centroid = mean_centroid([m.embedding for m in valid])
    best: Optional[NewsPoint] = None
    best_sim = -1.0
    best_time: Optional[datetime] = None

    for news in valid:
        sim = cosine_similarity(centroid, news.embedding)
        pt = news.publish_time
        if sim > best_sim + 1e-12:
            best = news
            best_sim = sim
            best_time = pt
        elif abs(sim - best_sim) <= 1e-12:
            if best is None:
                best = news
                best_time = pt
            elif pt and (best_time is None or pt > best_time):
                best = news
                best_time = pt
            elif pt == best_time and news.id > (best.id if best else -1):
                best = news
                best_time = pt
    return best


def should_replace_representative(
    current: NewsPoint,
    candidate: NewsPoint,
) -> bool:
    """增量场景：候选发布时间更新则更换代表（与 PRD 一致）。"""
    if candidate.publish_time is None:
        return False
    if current.publish_time is None:
        return True
    return candidate.publish_time > current.publish_time
