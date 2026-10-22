"""核心统计指标。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List

from sqlalchemy import Date, cast, func, select
from sqlalchemy.orm import Session

from backend.src.models.event import Event
from backend.src.models.news import News
from backend.src.models.pipeline import PipelineAsset


def overview_stats(session: Session) -> Dict[str, Any]:
    # 列表 / RAG / 聚类只消费 ready；概览指标与之对齐
    ready = News.process_status == "ready"
    news_count = session.scalar(select(func.count()).select_from(News).where(ready)) or 0
    event_count = session.scalar(select(func.count()).select_from(Event)) or 0
    with_emb = (
        session.scalar(
            select(func.count())
            .select_from(News)
            .where(ready, News.embedding.is_not(None))
        )
        or 0
    )
    unassigned = (
        session.scalar(
            select(func.count())
            .select_from(News)
            .where(ready, News.event_id.is_(None))
        )
        or 0
    )
    asset_count = (
        session.scalar(
            select(func.count())
            .select_from(PipelineAsset)
            .where(PipelineAsset.status == "active")
        )
        or 0
    )
    return {
        "news_count": int(news_count),
        "event_count": int(event_count),
        "news_with_embedding": int(with_emb),
        "unassigned_news": int(unassigned),
        "pipeline_asset_count": int(asset_count),
    }


def development_stage_stats(session: Session) -> List[Dict[str, Any]]:
    from backend.src.pipeline_intel.normalize import stage_label

    rows = session.execute(
        select(PipelineAsset.current_stage, func.count())
        .where(PipelineAsset.status == "active")
        .group_by(PipelineAsset.current_stage)
        .order_by(func.count().desc())
    ).all()
    return [
        {
            "stage": r[0] or "unknown",
            "label": stage_label(r[0] or "unknown"),
            "count": int(r[1]),
        }
        for r in rows
    ]


def news_trend_stats(session: Session, *, days: int = 14) -> List[Dict[str, Any]]:
    since = datetime.utcnow() - timedelta(days=days)
    day_col = cast(News.publish_time, Date)
    rows = session.execute(
        select(day_col, func.count())
        .where(News.publish_time.is_not(None))
        .where(News.publish_time >= since)
        .group_by(day_col)
        .order_by(day_col.asc())
    ).all()
    return [{"date": str(r[0]), "count": int(r[1])} for r in rows]


def hot_keywords_stats(session: Session, *, limit: int = 20) -> List[Dict[str, Any]]:
    rows = session.scalars(
        select(News.matched_keywords).where(News.matched_keywords.is_not(None)).limit(500)
    ).all()
    counter: Dict[str, int] = {}
    for mk in rows:
        if not isinstance(mk, dict):
            continue
        for _cat, value in mk.items():
            if not value:
                continue
            for term in str(value).split(","):
                term = term.strip()
                if term:
                    counter[term] = counter.get(term, 0) + 1
    ordered = sorted(counter.items(), key=lambda x: x[1], reverse=True)[:limit]
    return [{"keyword": k, "count": v} for k, v in ordered]
