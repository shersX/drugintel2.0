"""新闻 CRUD：入库 raw_data、查询已有标题。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Mapping, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from backend.src.core.logger import get_logger
from backend.src.models.news import News

logger = get_logger("db.crud.news")


def _parse_publish_time(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def fetch_existing_titles(session: Session, titles: Sequence[str]) -> List[str]:
    """批量查询库中已存在的标题（用于去重）。"""
    cleaned = [t for t in titles if t]
    if not cleaned:
        return []
    rows = session.scalars(select(News.title).where(News.title.in_(cleaned))).all()
    return list(rows)


def item_to_news_kwargs(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "title": str(item.get("title") or "")[:500],
        "content": str(item.get("full_text") or item.get("content") or ""),
        "abstract": item.get("abstract"),
        "publish_time": _parse_publish_time(item.get("publish_time")),
        "source": (item.get("source") or None),
        "detail_url": (item.get("detail_url") or None),
        "crawler": (item.get("crawler") or None),
        "matched_keywords": item.get("matched_keywords"),
        "embedding": item.get("embedding"),
        "is_representative": False,
        "event_id": None,
    }


def upsert_news_items(session: Session, items: Sequence[Mapping[str, Any]]) -> int:
    """
    按 detail_url 冲突跳过写入；无 URL 则直接 insert。
    返回成功写入条数（含新插入）。
    """
    inserted = 0
    for item in items:
        if not item.get("embedding"):
            logger.warning("跳过无向量新闻 title=%s", str(item.get("title") or "")[:40])
            continue
        kwargs = item_to_news_kwargs(item)
        url = kwargs.get("detail_url")
        if url:
            stmt = (
                insert(News)
                .values(**kwargs)
                .on_conflict_do_nothing(index_elements=["detail_url"])
            )
            result = session.execute(stmt)
            # rowcount: 1 inserted, 0 conflict skip
            if result.rowcount:
                inserted += 1
        else:
            session.add(News(**kwargs))
            inserted += 1
    session.flush()
    logger.info("入库新闻 写入=%s 输入=%s", inserted, len(items))
    return inserted
