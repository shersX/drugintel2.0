"""事件聚类服务：StreamingClusterer（产品优先 + 弱实体余弦三档）+ 风险分。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Set

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.src.clustering.clusterer import NewsPoint
from backend.src.clustering.representative import (
    select_representative_news,
    should_replace_representative,
)
from backend.src.clustering.streaming import Article, EventCluster, StreamingClusterer
from backend.src.core.logger import get_logger
from backend.src.db.crud.event import create_event, fetch_unassigned_news
from backend.src.db.session import session_scope
from backend.src.models.event import Event
from backend.src.models.news import News
from backend.src.scoring.ci_risk import compute_ci_risk_score

logger = get_logger("clustering.service")


def _ts(value: Optional[datetime]) -> float:
    if value is None:
        return datetime.now(timezone.utc).timestamp()
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc).timestamp()
    return value.timestamp()


def _as_set(values: Optional[Sequence[str]]) -> Set[str]:
    return {str(x).strip().lower() for x in (values or []) if str(x).strip()}


def _news_to_article(news: News) -> Article:
    emb = news.embedding
    if emb is None:
        raise ValueError(f"news {news.id} 无 embedding")
    return Article(
        id=str(news.id),
        text=news.title or "",
        timestamp=_ts(news.publish_time),
        embedding=np.asarray([float(x) for x in emb], dtype=np.float64),
        drug_entities=_as_set(news.drugs),
        org_entities=_as_set(news.orgs),
        event_type=(news.story_type or "other"),
        product_entities=_as_set(news.products),
    )


def _news_point(news: News) -> NewsPoint:
    return NewsPoint(
        id=news.id,
        embedding=[float(x) for x in news.embedding],
        title=news.title or "",
        abstract=news.abstract,
        publish_time=news.publish_time,
    )


def _clear_representative_flags(session: Session, event_id: int) -> None:
    for news in session.scalars(select(News).where(News.event_id == event_id)).all():
        news.is_representative = False


def _apply_representative(session: Session, event: Event, rep: News) -> None:
    _clear_representative_flags(session, event.id)
    event.representative_news_id = rep.id
    event.title = (rep.title or event.title or "")[:500]
    event.summary = rep.abstract
    rep.is_representative = True


def _centroid(members: Sequence[News]) -> List[float]:
    mats = [
        np.asarray(m.embedding, dtype=np.float64)
        for m in members
        if m.embedding is not None
    ]
    if not mats:
        return []
    return [float(x) for x in np.mean(np.stack(mats, axis=0), axis=0)]


def _aggregate_event_fields(session: Session, event: Event) -> None:
    members = list(session.scalars(select(News).where(News.event_id == event.id)).all())
    products: List[str] = []
    orgs: List[str] = []
    story_types: List[str] = []
    seen_p: Set[str] = set()
    seen_o: Set[str] = set()
    seen_t: Set[str] = set()
    for m in members:
        for p in m.products or []:
            if p not in seen_p:
                seen_p.add(p)
                products.append(p)
        for o in m.orgs or []:
            if o not in seen_o:
                seen_o.add(o)
                orgs.append(o)
        st = m.story_type or "other"
        if st not in seen_t:
            seen_t.add(st)
            story_types.append(st)
    event.products = products
    event.orgs = orgs
    event.story_types = story_types
    event.news_count = len(members)

    growth = 0.0
    if len(members) >= 2:
        times = sorted(_ts(m.publish_time) for m in members)
        span_days = max(1.0, (times[-1] - times[0]) / 86400.0)
        early = sum(1 for t in times if t <= times[0] + span_days * 0.5)
        late = len(times) - early
        growth = (late - early) / max(1.0, early)

    scored = compute_ci_risk_score(
        story_types=story_types or ["other"],
        news_count=len(members),
        recent_growth=growth,
        has_product=bool(products),
        has_org=bool(orgs),
        burst_prob=event.burst_prob,
    )
    event.ci_risk_score = scored["ci_risk_score"]
    event.score_components = scored["score_components"]
    if event.centroid_embedding is None or True:
        cent = _centroid(members)
        if cent:
            event.centroid_embedding = cent


def _seed_clusterer(session: Session, clusterer: StreamingClusterer) -> Dict[int, Event]:
    event_map: Dict[int, Event] = {}
    existing = list(
        session.scalars(
            select(Event)
            .where(Event.centroid_embedding.is_not(None))
            .where(Event.status == "active")
        ).all()
    )
    max_id = 0
    for event in existing:
        members = list(
            session.scalars(
                select(News)
                .where(News.event_id == event.id)
                .where(News.embedding.is_not(None))
            ).all()
        )
        if not members:
            continue
        arts = [_news_to_article(m) for m in members]
        c = EventCluster(
            id=event.id,
            created_at=min(a.timestamp for a in arts),
            updated_at=max(a.timestamp for a in arts),
            status=event.status or "active",
        )
        c.members = arts
        c.update_medoids()
        clusterer.clusters.append(c)
        event_map[event.id] = event
        max_id = max(max_id, event.id)
    clusterer._cid = max_id
    return event_map


def cluster_unassigned_in_session(session: Session) -> Dict[str, Any]:
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

    clusterer = StreamingClusterer()
    event_map = _seed_clusterer(session, clusterer)
    existing_ids = set(event_map.keys())
    news_by_id = {n.id: n for n in unassigned}
    unassigned_ids = set(news_by_id.keys())

    for news in unassigned:
        clusterer.ingest(_news_to_article(news))

    touched: Set[int] = set()
    for c in clusterer.clusters:
        member_ids = [int(m.id) for m in c.members if str(m.id).isdigit()]
        new_ids = [i for i in member_ids if i in unassigned_ids]
        if not new_ids:
            continue

        if c.id in existing_ids:
            event = event_map[c.id]
            for nid in new_ids:
                news = news_by_id[nid]
                news.event_id = event.id
                news.is_representative = False
                if event.representative_news_id:
                    current = session.get(News, event.representative_news_id)
                    if current is not None and current.embedding is not None:
                        if should_replace_representative(_news_point(current), _news_point(news)):
                            _apply_representative(session, event, news)
                else:
                    _apply_representative(session, event, news)
                stats["attached_existing"] += 1
                stats["clustered_news"] += 1
            touched.add(event.id)
        else:
            members = [news_by_id[i] for i in new_ids]
            points = [_news_point(m) for m in members if m.embedding is not None]
            rep_point = select_representative_news(points)
            rep = news_by_id[rep_point.id] if rep_point else members[0]
            event = create_event(
                session,
                title=rep.title or "",
                summary=rep.abstract,
                centroid_embedding=_centroid(members),
                news_count=len(members),
                representative_news_id=rep.id,
                event_type=rep.story_type or "other",
            )
            for m in members:
                m.event_id = event.id
                m.is_representative = m.id == rep.id
            event_map[event.id] = event
            touched.add(event.id)
            stats["new_events"] += 1
            stats["clustered_news"] += len(members)

    session.flush()
    for eid in touched:
        event = event_map.get(eid) or session.get(Event, eid)
        if event is not None:
            _aggregate_event_fields(session, event)
    session.flush()

    # 簇级综合摘要（失败则保留代表篇 abstract）
    try:
        from backend.src.scoring.event_brief import refresh_summaries_for_events

        n_sum = refresh_summaries_for_events(session, list(touched))
        stats["event_summaries"] = n_sum
    except Exception as exc:
        logger.warning("事件综合摘要批次失败: %s", exc)

    logger.info("聚类完成 stats=%s", stats)
    try:
        from backend.src.monitor.health import record_cluster

        record_cluster(stats)
    except Exception:
        pass
    return stats


def run_clustering() -> Dict[str, Any]:
    with session_scope() as session:
        # 聚类前先跑别名智能合并，使 product/org canonical 尽早对齐
        try:
            from backend.src.entities.alias_resolve import resolve_entity_aliases

            alias_stats = resolve_entity_aliases(session, limit=50, use_embedding=True)
            logger.info("聚类前别名解析: %s", alias_stats)
        except Exception as exc:
            logger.warning("聚类前别名解析跳过: %s", exc)
        return cluster_unassigned_in_session(session)


def rescore_events() -> Dict[str, Any]:
    with session_scope() as session:
        rows = list(session.scalars(select(Event)).all())
        for event in rows:
            _aggregate_event_fields(session, event)
        session.flush()
        return {"scored": len(rows)}
