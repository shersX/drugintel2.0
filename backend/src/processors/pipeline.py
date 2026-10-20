"""数据处理流水线：分段落库 + 进度回调 + 积压补跑。"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable, Dict, List, Mapping, MutableMapping, Optional, Sequence

from backend.src.core.logger import get_logger
from backend.src.crawlers.scrapling_support import mark_seen_urls, plain_full_text
from backend.src.db.crud.news import (
    PROCESS_FAILED,
    PROCESS_READY,
    fetch_existing_titles,
    fetch_pending_news_items,
    mark_news_rejected,
    update_news_enrichment,
    upsert_raw_news_items,
)
from backend.src.db.session import session_scope
from backend.src.processors.deduplicator import deduplicate_by_title
from backend.src.processors.embedding import embed_items
from backend.src.processors.filter import filter_results_by_keywords
from backend.src.processors.relevance import isrelated_for_item
from backend.src.processors.summarizer import summarize_items

logger = get_logger("processors.pipeline")

ProgressCb = Optional[Callable[[Dict[str, Any]], None]]
REPROCESS_LIMIT = 50


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


def _emit(progress: ProgressCb, **fields: Any) -> None:
    if progress is None:
        return
    try:
        progress(fields)
    except Exception:
        logger.exception("进度回调失败")


def _mark_seen_by_crawler(items: Sequence[Mapping[str, Any]], urls: Sequence[str]) -> None:
    by_crawler: Dict[str, List[str]] = defaultdict(list)
    url_set = {u for u in urls if u}
    for item in items:
        url = str(item.get("detail_url") or "").strip()
        if url not in url_set:
            continue
        key = str(item.get("crawler") or "").strip().lower()
        if key:
            by_crawler[key].append(url)
    for key, group in by_crawler.items():
        mark_seen_urls(key, group)


async def _enrich_items(
    items: List[MutableMapping],
    *,
    progress: ProgressCb = None,
    skip_summary: bool = False,
    skip_embedding: bool = False,
    run_relevance: bool = True,
) -> Dict[str, Any]:
    """相关性 → 摘要 → 向量 → 更新库状态。items 应已是 raw（或待补跑）。"""
    stats: Dict[str, Any] = {"input": len(items)}
    if not items:
        return stats

    work = list(items)
    if run_relevance:
        _emit(progress, stage="relevance", label="相关性判断", items_in=len(work))
        related = await isrelated_for_item(work)
        related_urls = {str(i.get("detail_url") or "") for i in related if i.get("detail_url")}
        rejected_urls = [
            str(i.get("detail_url") or "")
            for i in work
            if i.get("detail_url") and str(i.get("detail_url")) not in related_urls
        ]
        if rejected_urls:
            with session_scope() as session:
                n = mark_news_rejected(session, rejected_urls)
                stats["rejected"] = n
        work = list(related)
        stats["after_relevance"] = len(work)
        _emit(
            progress,
            stage="relevance",
            label="相关性完成",
            items_in=stats["input"],
            items_out=len(work),
            detail=f"保留 {len(work)}，拒绝 {len(rejected_urls)}",
        )
    else:
        stats["after_relevance"] = len(work)

    if not work:
        return stats

    _emit(progress, stage="summary", label="生成摘要", items_in=len(work))
    if skip_summary:
        for item in work:
            item.setdefault(
                "abstract",
                (item.get("description") or plain_full_text(item.get("full_text"))[:200]),
            )
        summarized = list(work)
    else:
        summarized = await summarize_items(work)
    stats["after_summary"] = len(summarized)
    _emit(progress, stage="summary", label="摘要完成", items_out=len(summarized))

    _emit(progress, stage="embedding", label="生成向量", items_in=len(summarized))
    if skip_embedding:
        embedded = list(summarized)
    else:
        embedded = await embed_items(summarized)
    ready = [i for i in embedded if i.get("embedding")]
    failed = [i for i in embedded if not i.get("embedding")]
    stats["after_embedding"] = len(ready)
    stats["embed_failed"] = len(failed)

    with session_scope() as session:
        if ready:
            stats["ready_updated"] = update_news_enrichment(
                session, ready, status=PROCESS_READY
            )
        if failed:
            stats["failed_updated"] = update_news_enrichment(
                session, failed, status=PROCESS_FAILED
            )
    _emit(
        progress,
        stage="embedding",
        label="向量完成",
        items_out=len(ready),
        detail=f"ready {len(ready)}，failed {len(failed)}",
    )
    return stats


async def reprocess_pending_news(
    *,
    limit: int = REPROCESS_LIMIT,
    progress: ProgressCb = None,
) -> Dict[str, Any]:
    """补跑积压 raw/failed：相关性 → 摘要 → 向量。"""
    with session_scope() as session:
        pending = fetch_pending_news_items(session, limit=limit)
    if not pending:
        return {"pending": 0}
    _emit(
        progress,
        stage="reprocess",
        label="补跑积压",
        items_in=len(pending),
        detail=f"捞取 {len(pending)} 条 raw/failed",
    )
    stats = await _enrich_items(pending, progress=progress, run_relevance=True)
    stats["pending"] = len(pending)
    return stats


async def run_processing_pipeline(
    crawler_results: Mapping[str, Sequence[MutableMapping]],
    *,
    persist: bool = True,
    skip_summary: bool = False,
    skip_embedding: bool = False,
    progress: ProgressCb = None,
    reprocess_limit: int = REPROCESS_LIMIT,
) -> Dict[str, Any]:
    """
    分阶段：关键词 → 有效性 → 去重 → raw 落库 →（先补跑积压）→ 相关性 → 摘要 → 向量 → ready。
    """
    stats: Dict[str, Any] = {}

    # 先消化积压，避免永远空着
    if persist and reprocess_limit > 0:
        try:
            stats["reprocess"] = await reprocess_pending_news(
                limit=reprocess_limit, progress=progress
            )
        except Exception as exc:
            logger.exception("积压补跑失败: %s", exc)
            stats["reprocess_error"] = str(exc)

    _emit(progress, stage="filtering", label="关键词过滤")
    filtered = filter_results_by_keywords(crawler_results)
    flat = flatten_crawler_results(filtered)
    stats["after_keyword_filter"] = len(flat)

    valid = filter_valid_items(flat)
    stats["after_valid"] = len(valid)
    if not valid:
        logger.warning("无有效新闻，流水线结束")
        _emit(progress, stage="filtering", label="无有效新闻", items_out=0)
        return {"stats": stats, "items": []}

    existing_titles: List[str] = []
    if persist:
        try:
            with session_scope() as session:
                titles = [str(i.get("title") or "") for i in valid]
                existing_titles = fetch_existing_titles(session, titles)
        except Exception as e:
            logger.warning("查询库内标题失败，仅做批内去重: %s", e)

    deduped = deduplicate_by_title(valid, existing_titles=existing_titles)
    stats["after_dedup"] = len(deduped)
    _emit(
        progress,
        stage="filtering",
        label="去重完成",
        items_in=len(valid),
        items_out=len(deduped),
    )
    if not deduped:
        logger.warning("去重后无新闻，流水线结束")
        return {"stats": stats, "items": []}

    if persist:
        _emit(progress, stage="persist", label="落库原文", items_in=len(deduped))
        with session_scope() as session:
            raw_result = upsert_raw_news_items(session, deduped)
        stats["raw_inserted"] = raw_result.get("inserted", 0)
        saved_urls = raw_result.get("saved_urls") or []
        _mark_seen_by_crawler(deduped, saved_urls)
        _emit(
            progress,
            stage="persist",
            label="原文已落库",
            raw_inserted=stats["raw_inserted"],
            detail=f"新写入 {stats['raw_inserted']} 条",
        )
        # 只对本轮新写入或仍待处理的 URL 做 enrich：从 deduped 里筛 saved_urls 对应项
        # 以及全部 deduped（含冲突但仍为 raw/failed 的）——用 saved_urls 集合
        url_set = set(saved_urls)
        to_enrich = [
            i for i in deduped if str(i.get("detail_url") or "") in url_set
        ]
        # 无 URL 的新行无法按 url 更新，仍尝试 enrich 内存对象后无法写回——跳过无 url
        if not to_enrich:
            # 全部冲突且已是 ready：无事可做
            logger.info("本轮无待 enrich 条目（可能均已 ready）")
            return {"stats": stats, "items": []}
        enrich_stats = await _enrich_items(
            to_enrich,
            progress=progress,
            skip_summary=skip_summary,
            skip_embedding=skip_embedding,
            run_relevance=True,
        )
        stats.update({f"enrich_{k}": v for k, v in enrich_stats.items()})
    else:
        # 不落库：走旧式内存链路（测试用）
        related = await isrelated_for_item(deduped)
        stats["after_relevance"] = len(related)
        if skip_summary:
            for item in related:
                item.setdefault(
                    "abstract",
                    (item.get("description") or plain_full_text(item.get("full_text"))[:200]),
                )
            summarized = list(related)
        else:
            summarized = await summarize_items(related)
        stats["after_summary"] = len(summarized)
        if skip_embedding:
            embedded = list(summarized)
        else:
            embedded = await embed_items(summarized)
        stats["after_embedding"] = sum(1 for i in embedded if i.get("embedding"))
        stats["inserted"] = 0
        logger.info("流水线完成(无落库) stats=%s", stats)
        return {"stats": stats, "items": embedded}

    stats["inserted"] = stats.get("raw_inserted", 0)
    logger.info("流水线完成 stats=%s", stats)
    try:
        from backend.src.monitor.health import record_pipeline

        record_pipeline(stats)
    except Exception:
        pass
    return {"stats": stats, "items": []}
