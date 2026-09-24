"""事件聚类服务：增量归属 + 批处理建簇 + 写库。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.src.clustering.clusterer import (
    EventClusterer,
    IncrementalClusterer,
    NewsPoint,
    update_centroid_weighted,
)
from backend.src.clustering.representative import (
    select_representative_news,
    should_replace_representative,
)
from backend.src.core.logger import get_logger
from backend.src.db.crud.event import (
    create_event,
    fetch_unassigned_news,
    list_events_with_centroids,
)
from backend.src.db.session import session_scope
from backend.src.models.event import Event
from backend.src.models.news import News

logger = get_logger("clustering.service")


def _news_to_point(news: News) -> NewsPoint:
    emb = news.embedding
    if emb is None:
        raise ValueError(f"news {news.id} 无 embedding")
    return NewsPoint(
        id=news.id,
        embedding=[float(x) for x in emb],
        title=news.title or "",
        abstract=news.abstract,
        publish_time=news.publish_time,
    )


def _seed_embedding_for_event(session: Session, event: Event) -> Optional[List[float]]:
    if event.representative_news_id:
        rep = session.get(News, event.representative_news_id)
        if rep is not None and rep.embedding is not None:
            return [float(x) for x in rep.embedding]
    member = session.scalars(
        select(News).where(News.event_id == event.id).where(News.embedding.is_not(None)).limit(1)
    ).first()
    if member is not None and member.embedding is not None:
        return [float(x) for x in member.embedding]
    return None


def _clear_representative_flags(session: Session, event_id: int) -> None:
    rows = session.scalars(select(News).where(News.event_id == event_id)).all()
    for news in rows:
        news.is_representative = False


def _apply_representative(session: Session, event: Event, rep: News) -> None:
    _clear_representative_flags(session, event.id)
    event.representative_news_id = rep.id
    event.title = (rep.title or event.title or "")[:500]
    event.summary = rep.abstract
    rep.is_representative = True


def _attach_to_existing_event(
    session: Session,
    event: Event,
    news: News,
    *,
    alpha: float = 0.1,
) -> None:
    news.event_id = event.id
    news.is_representative = False
    event.news_count = int(event.news_count or 0) + 1
    if event.centroid_embedding is not None and news.embedding is not None:
        event.centroid_embedding = update_centroid_weighted(
            event.centroid_embedding,
            news.embedding,
            alpha=alpha,
        )

    if event.representative_news_id:
        current = session.get(News, event.representative_news_id)
        if current is not None and should_replace_representative(
            _news_to_point(current), _news_to_point(news)
        ):
            _apply_representative(session, event, news)
    else:
        _apply_representative(session, event, news)


def _persist_new_draft(
    session: Session,
    news_by_id: Dict[int, News],
    draft_news_ids: Sequence[int],
    centroid: Sequence[float],
) -> Event:
    members = [
        _news_to_point(news_by_id[nid])
        for nid in draft_news_ids
        if nid in news_by_id
    ]
    rep_point = select_representative_news(members)
    if rep_point is None:
        raise RuntimeError("无法为新事件选择代表新闻")
    rep_news = news_by_id[rep_point.id]
    event = create_event(
        session,
        title=rep_news.title or "",
        summary=rep_news.abstract,
        centroid_embedding=centroid,
        news_count=len(draft_news_ids),
        representative_news_id=rep_news.id,
    )
    for nid in draft_news_ids:
        row = news_by_id.get(nid)
        if row is None:
            continue
        row.event_id = event.id
        row.is_representative = nid == rep_news.id
    return event


def cluster_unassigned_in_session(
    session: Session,
    *,
    threshold_high: float = 0.85,
    threshold_mid: float = 0.75,
    alpha: float = 0.1,
) -> Dict[str, Any]:
    """
    对 event_id 为空的新闻执行：
    1) 尝试增量并入已有事件
    2) 剩余新闻做链式聚类并新建事件
    """
    unassigned = fetch_unassigned_news(session)
    stats: Dict[str, Any] = {
        "unassigned": len(unassigned),
        "attached_existing": 0,
        "new_events": 0,
        "clustered_news": 0,
    }
    if not unassigned:
        logger.info("无待聚类新闻")
        return stats

    incremental = IncrementalClusterer(
        threshold_high=threshold_high,
        threshold_mid=threshold_mid,
    )
    existing = list_events_with_centroids(session)
    snapshots: List[Tuple[int, List[float], Optional[List[float]]]] = []
    event_map: Dict[int, Event] = {}
    for event in existing:
        event_map[event.id] = event
        centroid = [float(x) for x in event.centroid_embedding] if event.centroid_embedding is not None else []
        if not centroid:
            continue
        snapshots.append((event.id, centroid, _seed_embedding_for_event(session, event)))

    remaining: List[News] = []
    for news in unassigned:
        point = _news_to_point(news)
        eid = incremental.assign(point.embedding, snapshots)
        if eid is None:
            remaining.append(news)
            continue
        event = event_map.get(eid) or session.get(Event, eid)
        if event is None:
            remaining.append(news)
            continue
        _attach_to_existing_event(session, event, news, alpha=alpha)
        stats["attached_existing"] += 1
        # 刷新快照中心
        if event.centroid_embedding is not None:
            new_c = [float(x) for x in event.centroid_embedding]
            snapshots = [
                (i, new_c if i == eid else c, s if i != eid else _seed_embedding_for_event(session, event))
                for i, c, s in snapshots
            ]

    if remaining:
        batcher = EventClusterer(
            threshold_high=threshold_high,
            threshold_mid=threshold_mid,
        )
        points = [_news_to_point(n) for n in remaining]
        news_by_id = {n.id: n for n in remaining}
        drafts = batcher.cluster(points)
        for draft in drafts:
            _persist_new_draft(session, news_by_id, draft.news_ids, draft.centroid())
            stats["new_events"] += 1
            stats["clustered_news"] += len(draft.news_ids)

    session.flush()
    logger.info("聚类完成 stats=%s", stats)
    try:
        from backend.src.monitor.health import record_cluster

        record_cluster(stats)
    except Exception:
        pass
    return stats


def run_clustering(
    *,
    threshold_high: float = 0.85,
    threshold_mid: float = 0.75,
    alpha: float = 0.1,
) -> Dict[str, Any]:
    """打开会话并执行聚类。"""
    with session_scope() as session:
        return cluster_unassigned_in_session(
            session,
            threshold_high=threshold_high,
            threshold_mid=threshold_mid,
            alpha=alpha,
        )
