"""新闻 CRUD：分阶段入库（raw → enrich → ready）与查询。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Mapping, Optional, Sequence
from zoneinfo import ZoneInfo

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from backend.src.core.logger import get_logger
from backend.src.models.news import News

logger = get_logger("db.crud.news")

PROCESS_RAW = "raw"
PROCESS_REJECTED = "rejected"
PROCESS_FAILED = "failed"
PROCESS_READY = "ready"

# 爬虫约定：国内源直接给北京墙钟；美网源经 et_to_beijing 转成北京墙钟后再入库。
_SHANGHAI = ZoneInfo("Asia/Shanghai")


def format_publish_time_cn(value: Optional[datetime]) -> Optional[str]:
    """API / 展示用：统一输出北京时间到分钟。"""
    if value is None:
        return None
    if value.tzinfo is None:
        moment = value.replace(tzinfo=_SHANGHAI)
    else:
        moment = value.astimezone(_SHANGHAI)
    return moment.strftime("%Y-%m-%d %H:%M")


def _parse_publish_time(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=_SHANGHAI)
        return value
    text = str(value).strip()
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=_SHANGHAI)
        except ValueError:
            continue
    try:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        return moment.replace(tzinfo=_SHANGHAI)
    return moment


def fetch_existing_titles(session: Session, titles: Sequence[str]) -> List[str]:
    """批量查询库中已存在的标题（用于去重）。"""
    cleaned = [t for t in titles if t]
    if not cleaned:
        return []
    rows = session.scalars(select(News.title).where(News.title.in_(cleaned))).all()
    return list(rows)


def item_to_news_kwargs(
    item: Mapping[str, Any],
    *,
    process_status: str = PROCESS_READY,
) -> dict[str, Any]:
    from backend.src.search.tsv import search_tsv_from_item

    content_html = item.get("content_html")
    if content_html is not None:
        content_html = str(content_html).strip() or None
    return {
        "title": str(item.get("title") or "")[:500],
        "content": str(item.get("full_text") or item.get("content") or ""),
        "content_html": content_html,
        "abstract": item.get("abstract"),
        "publish_time": _parse_publish_time(item.get("publish_time")),
        "source": (item.get("source") or None),
        "detail_url": (item.get("detail_url") or None),
        "crawler": (item.get("crawler") or None),
        "matched_keywords": item.get("matched_keywords"),
        "embedding": item.get("embedding"),
        "search_tsv": search_tsv_from_item(item),
        "process_status": process_status,
        "is_representative": False,
        "event_id": None,
    }


def upsert_raw_news_items(session: Session, items: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """
    早期落库：允许无 abstract/embedding，状态 raw。
    同 URL 已存在则跳过插入；返回新写入条数与成功落库的 URL（供已见标记）。
    """
    inserted = 0
    saved_urls: List[str] = []
    for item in items:
        kwargs = item_to_news_kwargs(item, process_status=PROCESS_RAW)
        # raw 阶段不应带向量
        kwargs["embedding"] = None
        kwargs["abstract"] = kwargs.get("abstract")  # 通常为空
        url = kwargs.get("detail_url")
        if url:
            stmt = (
                insert(News)
                .values(**kwargs)
                .on_conflict_do_nothing(index_elements=["detail_url"])
            )
            result = session.execute(stmt)
            if result.rowcount:
                inserted += 1
                saved_urls.append(str(url))
            else:
                # 已存在：若仍是 raw/failed，记下 URL 以便补跑与已见对齐
                existing = session.scalar(select(News).where(News.detail_url == url).limit(1))
                if existing is not None and existing.process_status in {
                    PROCESS_RAW,
                    PROCESS_FAILED,
                }:
                    saved_urls.append(str(url))
        else:
            session.add(News(**kwargs))
            inserted += 1
    session.flush()
    if inserted:
        try:
            from backend.src.search.bm25 import invalidate_bm25_stats

            invalidate_bm25_stats()
        except Exception:
            pass
    logger.info("raw 入库 新写=%s 输入=%s 可标记已见=%s", inserted, len(items), len(saved_urls))
    return {"inserted": inserted, "saved_urls": saved_urls}


def mark_news_rejected(session: Session, detail_urls: Sequence[str]) -> int:
    urls = [u for u in detail_urls if u]
    if not urls:
        return 0
    result = session.execute(
        update(News)
        .where(News.detail_url.in_(urls))
        .where(News.process_status.in_([PROCESS_RAW, PROCESS_FAILED]))
        .values(process_status=PROCESS_REJECTED)
    )
    session.flush()
    return int(result.rowcount or 0)


def update_news_enrichment(
    session: Session,
    items: Sequence[Mapping[str, Any]],
    *,
    status: str,
) -> int:
    """按 detail_url 更新 abstract/embedding 与 process_status。"""
    from backend.src.search.tsv import _update_row_search_tsv

    updated = 0
    for item in items:
        url = (item.get("detail_url") or "").strip()
        if not url:
            continue
        row = session.scalar(select(News).where(News.detail_url == url).limit(1))
        if row is None:
            continue
        row.process_status = status
        if "abstract" in item:
            row.abstract = item.get("abstract")
        if "embedding" in item:
            row.embedding = item.get("embedding")
        try:
            _update_row_search_tsv(
                session,
                row.id,
                row.title or "",
                row.abstract or "",
                row.content or "",
            )
        except Exception:
            logger.warning("刷新 search_tsv 失败 id=%s", row.id)
        updated += 1
    session.flush()
    if updated:
        try:
            from backend.src.search.bm25 import invalidate_bm25_stats

            invalidate_bm25_stats()
        except Exception:
            pass
    logger.info("enrich 更新=%s status=%s", updated, status)
    return updated


def fetch_pending_news_items(session: Session, *, limit: int = 50) -> List[dict[str, Any]]:
    """捞取待补跑的 raw/failed，转成 pipeline item 结构。"""
    rows = list(
        session.scalars(
            select(News)
            .where(News.process_status.in_([PROCESS_RAW, PROCESS_FAILED]))
            .where(News.content.is_not(None))
            .where(News.content != "")
            .order_by(News.id.asc())
            .limit(max(1, limit))
        ).all()
    )
    items: List[dict[str, Any]] = []
    for row in rows:
        items.append(
            {
                "id": row.id,
                "title": row.title or "",
                "full_text": row.content or "",
                "content": row.content or "",
                "content_html": row.content_html,
                "abstract": row.abstract,
                "publish_time": row.publish_time,
                "source": row.source,
                "detail_url": row.detail_url,
                "crawler": row.crawler,
                "matched_keywords": row.matched_keywords,
                "process_status": row.process_status,
            }
        )
    return items


def news_ready_filter():
    """SQLAlchemy 条件：对外可见新闻。"""
    return News.process_status == PROCESS_READY


def upsert_news_items(session: Session, items: Sequence[Mapping[str, Any]]) -> int:
    """
    兼容旧路径：要求有 embedding，写入 ready。
    新流水线请优先用 upsert_raw_news_items + update_news_enrichment。
    """
    inserted = 0
    for item in items:
        if not item.get("embedding"):
            logger.warning("跳过无向量新闻 title=%s", str(item.get("title") or "")[:40])
            continue
        kwargs = item_to_news_kwargs(item, process_status=PROCESS_READY)
        url = kwargs.get("detail_url")
        if url:
            stmt = (
                insert(News)
                .values(**kwargs)
                .on_conflict_do_nothing(index_elements=["detail_url"])
            )
            result = session.execute(stmt)
            if result.rowcount:
                inserted += 1
        else:
            session.add(News(**kwargs))
            inserted += 1
    session.flush()
    if inserted:
        try:
            from backend.src.search.bm25 import invalidate_bm25_stats

            invalidate_bm25_stats()
        except Exception:
            pass
    logger.info("入库新闻 写入=%s 输入=%s", inserted, len(items))
    return inserted
