"""数据处理流水线编排（任务 2.6）。"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Sequence

from backend.src.core.logger import get_logger
from backend.src.db.crud.news import fetch_existing_titles, upsert_news_items
from backend.src.db.session import session_scope
from backend.src.processors.deduplicator import deduplicate_by_title
from backend.src.processors.embedding import embed_items
from backend.src.processors.filter import filter_results_by_keywords
from backend.src.processors.relevance import isrelated_for_item
from backend.src.processors.summarizer import summarize_items

logger = get_logger("processors.pipeline")


def flatten_crawler_results(
    crawler_results: Mapping[str, Sequence[MutableMapping]],
) -> List[MutableMapping]:
    items: List[MutableMapping] = []
    for news_list in (crawler_results or {}).values():
        for item in news_list or []:
            if isinstance(item, MutableMapping):
                items.append(item)
    return items


def filter_valid_items(items: Sequence[MutableMapping]) -> List[MutableMapping]:
    """保留同时具备 full_text 与 publish_time 的新闻。"""
    return [
        item
        for item in items
        if item.get("full_text") and item.get("publish_time")
    ]


async def run_processing_pipeline(
    crawler_results: Mapping[str, Sequence[MutableMapping]],
    *,
    persist: bool = True,
    skip_summary: bool = False,
    skip_embedding: bool = False,
) -> Dict[str, Any]:
    """
    完整处理链路：
    关键词过滤 → 扁平化 → 有效性 → LLM 相关性 → 标题去重 → 摘要 → 向量 → 入库

    Returns:
        统计与最终 items（含 abstract / embedding）
    """
    stats: Dict[str, Any] = {}

    filtered = filter_results_by_keywords(crawler_results)
    flat = flatten_crawler_results(filtered)
    stats["after_keyword_filter"] = len(flat)

    valid = filter_valid_items(flat)
    stats["after_valid"] = len(valid)
    if not valid:
        logger.warning("无有效新闻，流水线结束")
        return {"stats": stats, "items": []}

    related = await isrelated_for_item(valid)
    stats["after_relevance"] = len(related)

    existing_titles: List[str] = []
    if persist:
        try:
            with session_scope() as session:
                titles = [str(i.get("title") or "") for i in related]
                existing_titles = fetch_existing_titles(session, titles)
        except Exception as e:
            logger.warning("查询库内标题失败，仅做批内去重: %s", e)

    deduped = deduplicate_by_title(related, existing_titles=existing_titles)
    stats["after_dedup"] = len(deduped)

    if skip_summary:
        for item in deduped:
            item.setdefault(
                "abstract",
                (item.get("description") or str(item.get("full_text") or "")[:200]),
            )
        summarized = list(deduped)
    else:
        summarized = await summarize_items(deduped)
    stats["after_summary"] = len(summarized)

    if skip_embedding:
        embedded = list(summarized)
    else:
        embedded = await embed_items(summarized)
    stats["after_embedding"] = sum(1 for i in embedded if i.get("embedding"))

    inserted = 0
    if persist and embedded:
        try:
            with session_scope() as session:
                inserted = upsert_news_items(session, embedded)
        except Exception as e:
            logger.error("入库失败: %s", e)
            raise
    stats["inserted"] = inserted

    logger.info("流水线完成 stats=%s", stats)
    try:
        from backend.src.monitor.health import record_pipeline

        record_pipeline(stats)
    except Exception:
        pass
    return {"stats": stats, "items": embedded}
