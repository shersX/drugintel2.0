"""事件聚类算法（任务 4）：相似度、链式聚类、增量分配。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Sequence, Tuple

import numpy as np

from backend.src.core.logger import get_logger

logger = get_logger("clustering.clusterer")


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    va = np.asarray(a, dtype=np.float64)
    vb = np.asarray(b, dtype=np.float64)
    na = np.linalg.norm(va)
    nb = np.linalg.norm(vb)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))


def mean_centroid(embeddings: Sequence[Sequence[float]]) -> List[float]:
    if not embeddings:
        return []
    arr = np.asarray(embeddings, dtype=np.float64)
    centroid = arr.mean(axis=0)
    norm = np.linalg.norm(centroid)
    if norm > 0:
        centroid = centroid / norm
    return centroid.tolist()


def update_centroid_weighted(
    centroid: Sequence[float],
    new_embedding: Sequence[float],
    *,
    alpha: float = 0.1,
) -> List[float]:
    """增量更新中心向量：centroid = (1-α)·c + α·x，再 L2 归一化。"""
    c = np.asarray(centroid, dtype=np.float64)
    x = np.asarray(new_embedding, dtype=np.float64)
    updated = (1.0 - alpha) * c + alpha * x
    norm = np.linalg.norm(updated)
    if norm > 0:
        updated = updated / norm
    return updated.tolist()


@dataclass
class NewsPoint:
    """聚类用轻量新闻点（不绑 ORM）。"""

    id: int
    embedding: List[float]
    title: str = ""
    abstract: Optional[str] = None
    publish_time: Optional[datetime] = None


@dataclass
class EventDraft:
    """内存中的事件簇草稿。"""

    seed_id: int
    news_ids: List[int] = field(default_factory=list)
    embeddings: List[List[float]] = field(default_factory=list)
    seed_embedding: List[float] = field(default_factory=list)

    def centroid(self) -> List[float]:
        return mean_centroid(self.embeddings)


class EventClusterer:
    """
    基于多阈值的链式聚类（批处理）。

    - ≥ threshold_high：直接并入（相对种子）
    - ≥ threshold_mid：再与当前簇中心比较，≥ mid 则并入
    - 否则跳过，留给后续种子
    """

    def __init__(
        self,
        threshold_high: float = 0.85,
        threshold_mid: float = 0.75,
        threshold_low: float = 0.65,
    ):
        self.threshold_high = threshold_high
        self.threshold_mid = threshold_mid
        self.threshold_low = threshold_low

    def cluster(self, news_list: Sequence[NewsPoint]) -> List[EventDraft]:
        unassigned = [n for n in news_list if n.embedding]
        events: List[EventDraft] = []

        while unassigned:
            seed = unassigned.pop(0)
            draft = EventDraft(
                seed_id=seed.id,
                news_ids=[seed.id],
                embeddings=[list(seed.embedding)],
                seed_embedding=list(seed.embedding),
            )
            i = 0
            while i < len(unassigned):
                news = unassigned[i]
                sim_seed = cosine_similarity(seed.embedding, news.embedding)
                if sim_seed >= self.threshold_high:
                    draft.news_ids.append(news.id)
                    draft.embeddings.append(list(news.embedding))
                    unassigned.pop(i)
                elif sim_seed >= self.threshold_mid:
                    centroid = draft.centroid()
                    if cosine_similarity(centroid, news.embedding) >= self.threshold_mid:
                        draft.news_ids.append(news.id)
                        draft.embeddings.append(list(news.embedding))
                        unassigned.pop(i)
                    else:
                        i += 1
                else:
                    i += 1
            events.append(draft)

        logger.info(
            "链式聚类 输入=%s 事件数=%s",
            len(news_list),
            len(events),
        )
        return events


class IncrementalClusterer:
    """增量：将单条新闻分配到已有事件（多阈值 + 种子约束）。"""

    def __init__(
        self,
        threshold_high: float = 0.85,
        threshold_mid: float = 0.75,
    ):
        self.threshold_high = threshold_high
        self.threshold_mid = threshold_mid

    def assign(
        self,
        embedding: Sequence[float],
        events: Sequence[Tuple[int, Sequence[float], Optional[Sequence[float]]]],
    ) -> Optional[int]:
        """
        Args:
            embedding: 新闻向量
            events: (event_id, centroid, seed_embedding) 列表
        Returns:
            命中的 event_id；无一则 None
        """
        best_id: Optional[int] = None
        best_sim = -1.0
        best_seed: Optional[Sequence[float]] = None

        for event_id, centroid, seed in events:
            if not centroid:
                continue
            sim = cosine_similarity(embedding, centroid)
            if sim > best_sim:
                best_sim = sim
                best_id = event_id
                best_seed = seed

        if best_id is None:
            return None
        if best_sim >= self.threshold_high:
            return best_id
        if best_sim >= self.threshold_mid:
            if best_seed is None:
                return best_id
            if cosine_similarity(embedding, best_seed) >= self.threshold_mid:
                return best_id
            return None
        return None
