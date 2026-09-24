"""事件 CRUD。"""

from __future__ import annotations

from typing import List, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.src.models.event import Event
from backend.src.models.news import News


def list_events_with_centroids(session: Session) -> List[Event]:
    return list(
        session.scalars(
            select(Event).where(Event.centroid_embedding.is_not(None))
        ).all()
    )


def get_event(session: Session, event_id: int) -> Optional[Event]:
    return session.get(Event, event_id)


def create_event(
    session: Session,
    *,
    title: str,
    summary: Optional[str],
    centroid_embedding: Sequence[float],
    news_count: int,
    representative_news_id: Optional[int],
    event_type: Optional[str] = None,
) -> Event:
    event = Event(
        title=title[:500],
        summary=summary,
        centroid_embedding=list(centroid_embedding),
        news_count=news_count,
        representative_news_id=representative_news_id,
        event_type=event_type,
    )
    session.add(event)
    session.flush()
    return event


def fetch_unassigned_news(session: Session) -> List[News]:
    return list(
        session.scalars(
            select(News)
            .where(News.event_id.is_(None))
            .where(News.embedding.is_not(None))
            .order_by(News.publish_time.asc().nulls_last(), News.id.asc())
        ).all()
    )


def fetch_news_by_ids(session: Session, ids: Sequence[int]) -> List[News]:
    if not ids:
        return []
    rows = session.scalars(select(News).where(News.id.in_(list(ids)))).all()
    by_id = {n.id: n for n in rows}
    return [by_id[i] for i in ids if i in by_id]
