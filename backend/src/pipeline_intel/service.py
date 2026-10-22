"""管线同步编排：抓图 → snapshot → 视觉抽取 → upsert → 通知。"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from backend.src.core.config import vision_readiness
from backend.src.core.logger import get_logger
from backend.src.db.session import session_scope
from backend.src.models.pipeline import PipelineCrawlConfig, PipelinePageSnapshot
from backend.src.monitor.health import record_crawler_task

logger = get_logger("pipeline_intel.service")

_LOCK = threading.Lock()
_RUNNING = False


def is_pipeline_sync_running() -> bool:
    return _RUNNING


def _extract_has_content(snap: Optional[PipelinePageSnapshot]) -> bool:
    """空抽取不算成功基线，避免挡住换模型后的重跑。"""
    if snap is None:
        return False
    payload = snap.extract_json or {}
    assets = payload.get("assets") if isinstance(payload, dict) else None
    return bool(assets)


def _prev_success_snapshot(
    session, company_id: Optional[int] = None
) -> Optional[PipelinePageSnapshot]:
    stmt = (
        select(PipelinePageSnapshot)
        .where(PipelinePageSnapshot.status == "extracted")
        .order_by(PipelinePageSnapshot.id.desc())
        .limit(20)
    )
    if company_id is not None:
        stmt = stmt.where(PipelinePageSnapshot.company_id == company_id)
    for row in session.scalars(stmt).all():
        if _extract_has_content(row):
            return row
    return None


def _hashes_unchanged(prev: Optional[PipelinePageSnapshot], hashes: List[str]) -> bool:
    if prev is None:
        return False
    old = list(prev.image_hashes or [])
    return bool(hashes) and sorted(old) == sorted(hashes)


async def run_pipeline_sync(*, force: bool = False, source_url: Optional[str] = None) -> Dict[str, Any]:
    """执行一轮管线同步。force=True 时即使图片 hash 未变也重跑视觉。"""
    global _RUNNING
    ready = vision_readiness()
    if not ready.get("ready"):
        raise RuntimeError(ready.get("message") or "视觉模型未配置")

    if not _LOCK.acquire(blocking=False):
        raise RuntimeError("管线同步正在进行中，请稍后再试")
    _RUNNING = True
    started = datetime.now(timezone.utc)
    log_lines: List[str] = []

    def log(msg: str) -> None:
        logger.info(msg)
        log_lines.append(msg)

    try:
        from backend.src.crawlers.simcere_pipeline import (
            COMPANY_NAME,
            COMPANY_NAME_EN,
            DEFAULT_SOURCE_URL,
            crawl_simcere_pipeline,
        )
        from backend.src.pipeline_intel.extract import extract_from_images
        from backend.src.pipeline_intel.news_deals import sync_deals_from_news
        from backend.src.pipeline_intel.notify import notify_pipeline_changes
        from backend.src.pipeline_intel.upsert import apply_extract

        with session_scope() as session:
            cfg = session.scalar(select(PipelineCrawlConfig).limit(1))
            url = (
                (source_url or "").strip()
                or (cfg.source_url if cfg else None)
                or DEFAULT_SOURCE_URL
            )

        log(f"开始抓取管线页: {url}")
        crawl = await crawl_simcere_pipeline(source_url=url)
        image_paths = list(crawl.get("image_paths") or [])
        image_hashes = list(crawl.get("image_hashes") or [])
        if not image_paths:
            raise RuntimeError(
                f"未抓到管线大图，请检查来源 URL 是否为管线示意图页：{url}"
            )

        with session_scope() as session:
            prev = _prev_success_snapshot(session)
            skip_vision = (not force) and _hashes_unchanged(prev, image_hashes)
            snap = PipelinePageSnapshot(
                source_url=crawl["source_url"],
                fetched_at=datetime.now(timezone.utc),
                image_paths=image_paths,
                image_hashes=image_hashes,
                raw_html=crawl.get("raw_html"),
                status="pending",
            )
            session.add(snap)
            session.flush()
            snap_id = snap.id
            prev_id = prev.id if prev else None
            is_baseline = prev is None

            if skip_vision:
                snap.status = "skipped_unchanged"
                deal_stats = sync_deals_from_news(session)
                session.flush()
                log(f"图片 hash 未变，跳过视觉抽取；新闻交易同步 created={deal_stats.get('created', 0)}")
                record_crawler_task(
                    crawler_name="simcere_pipeline",
                    start_time=started,
                    end_time=datetime.now(timezone.utc),
                    status="success",
                    total_count=len(image_paths),
                    success_count=len(image_paths),
                    log_text="\n".join(log_lines[-80:]),
                )
                return {
                    "ok": True,
                    "skipped": True,
                    "reason": "unchanged",
                    "snapshot_id": snap_id,
                    "image_count": len(image_paths),
                    "news_deals": deal_stats,
                }

        log(f"调用视觉模型分析 {len(image_paths)} 张图")
        try:
            extracted = await extract_from_images(image_paths)
        except Exception as exc:
            with session_scope() as session:
                snap = session.get(PipelinePageSnapshot, snap_id)
                if snap:
                    snap.status = "extract_failed"
                    snap.error = str(exc)[:2000]
            record_crawler_task(
                crawler_name="simcere_pipeline",
                start_time=started,
                end_time=datetime.now(timezone.utc),
                status="failed",
                total_count=len(image_paths),
                success_count=0,
                error_message=str(exc)[:500],
                log_text="\n".join(log_lines[-80:]),
            )
            raise

        with session_scope() as session:
            snap = session.get(PipelinePageSnapshot, snap_id)
            assert snap is not None
            assets = extracted.get("assets") or []
            snap.extract_json = {"assets": assets}
            snap.model_name = extracted.get("model_name")
            # 空结果标 extracted_empty，不参与 hash 跳过基线
            snap.status = "extracted" if assets else "extracted_empty"
            session.flush()

            result = apply_extract(
                session,
                company_name=COMPANY_NAME,
                company_name_en=COMPANY_NAME_EN,
                source_url=crawl["source_url"],
                extract=snap.extract_json,
                snapshot_id=snap_id,
                prev_snapshot_id=prev_id,
                is_baseline=is_baseline,
            )
            if snap.company_id is None:
                snap.company_id = result.get("company_id")
            deal_stats = sync_deals_from_news(session)
            result["deals"] = deal_stats.get("created", 0)
            notify_stats = notify_pipeline_changes(session, result.get("change_ids") or [])
            session.flush()

        log(
            f"入库完成 created={result['created']} updated={result['updated']} "
            f"removed={result['removed']} news_deals={result['deals']} notify={notify_stats}"
        )
        record_crawler_task(
            crawler_name="simcere_pipeline",
            start_time=started,
            end_time=datetime.now(timezone.utc),
            status="success",
            total_count=len(image_paths),
            success_count=len(extracted.get("assets") or []),
            log_text="\n".join(log_lines[-80:]),
        )
        return {
            "ok": True,
            "skipped": False,
            "snapshot_id": snap_id,
            "image_count": len(image_paths),
            "stats": result,
            "notify": notify_stats,
            "is_baseline": is_baseline,
        }
    except Exception as exc:
        log(f"管线同步失败: {exc}")
        record_crawler_task(
            crawler_name="simcere_pipeline",
            start_time=started,
            end_time=datetime.now(timezone.utc),
            status="failed",
            total_count=0,
            success_count=0,
            error_message=str(exc)[:500],
            log_text="\n".join(log_lines[-80:]),
        )
        raise
    finally:
        _RUNNING = False
        _LOCK.release()
