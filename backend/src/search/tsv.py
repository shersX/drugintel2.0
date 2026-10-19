"""news.search_tsv 构建与回填。"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from sqlalchemy import CHAR, cast, select, text
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from sqlalchemy.sql.elements import ColumnElement

from backend.src.core.logger import get_logger
from backend.src.search.tokenize import tokens_to_ts_text

logger = get_logger("search.tsv")


def make_search_tsv_expr(
    title: str,
    abstract: Optional[str] = None,
    content: Optional[str] = None,
) -> ColumnElement[Any]:
    """生成带 A/B/C 权重的 tsvector SQL 表达式。"""
    title_t = tokens_to_ts_text(title or "")
    abstract_t = tokens_to_ts_text(abstract or "")
    content_t = tokens_to_ts_text(content or "")
    return (
        func.setweight(func.to_tsvector("simple", title_t), cast("A", CHAR(1)))
        .op("||")(func.setweight(func.to_tsvector("simple", abstract_t), cast("B", CHAR(1))))
        .op("||")(func.setweight(func.to_tsvector("simple", content_t), cast("C", CHAR(1))))
    )


def search_tsv_from_item(item: Mapping[str, Any]) -> ColumnElement[Any]:
    return make_search_tsv_expr(
        str(item.get("title") or ""),
        str(item.get("abstract") or ""),
        str(item.get("full_text") or item.get("content") or ""),
    )


def _update_row_search_tsv(
    session: Session,
    news_id: int,
    title: str,
    abstract: str,
    content: str,
) -> None:
    """用原生 SQL 更新单行，避免 ORM 表达式类型问题。"""
    session.execute(
        text(
            """
            UPDATE news
            SET search_tsv =
                setweight(to_tsvector('simple', :title_t), 'A') ||
                setweight(to_tsvector('simple', :abstract_t), 'B') ||
                setweight(to_tsvector('simple', :content_t), 'C')
            WHERE id = :id
            """
        ),
        {
            "id": news_id,
            "title_t": tokens_to_ts_text(title or ""),
            "abstract_t": tokens_to_ts_text(abstract or ""),
            "content_t": tokens_to_ts_text(content or ""),
        },
    )


def backfill_search_tsv(session: Session, *, batch_size: int = 200) -> int:
    """为 search_tsv 为空的新闻回填；返回更新条数。"""
    from backend.src.models.news import News

    updated = 0
    while True:
        rows = list(
            session.scalars(
                select(News)
                .where(News.search_tsv.is_(None))
                .order_by(News.id)
                .limit(batch_size)
            ).all()
        )
        if not rows:
            break
        for row in rows:
            _update_row_search_tsv(
                session,
                row.id,
                row.title or "",
                row.abstract or "",
                row.content or "",
            )
            updated += 1
        session.flush()
        logger.info("search_tsv 回填进度 +%s（累计 %s）", len(rows), updated)
        if len(rows) < batch_size:
            break
    return updated
