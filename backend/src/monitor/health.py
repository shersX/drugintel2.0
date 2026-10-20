"""轻量级监控与健康检查。"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import func, select, text

from backend.src.core.config import RedisEnvConfig
from backend.src.core.logger import get_logger
from backend.src.db.session import get_engine, session_scope
from backend.src.models.entities import CrawlerTask
from backend.src.models.news import News

logger = get_logger("monitor")

_PROCESS_STATE: Dict[str, Any] = {
    "last_pipeline_at": None,
    "last_pipeline_stats": None,
    "last_cluster_at": None,
    "last_cluster_stats": None,
}


def record_pipeline(stats: Dict[str, Any]) -> None:
    _PROCESS_STATE["last_pipeline_at"] = datetime.utcnow().isoformat()
    _PROCESS_STATE["last_pipeline_stats"] = stats


def record_cluster(stats: Dict[str, Any]) -> None:
    _PROCESS_STATE["last_cluster_at"] = datetime.utcnow().isoformat()
    _PROCESS_STATE["last_cluster_stats"] = stats


def record_crawler_task(
    *,
    crawler_name: str,
    status: str,
    total_count: int = 0,
    success_count: int = 0,
    error_message: Optional[str] = None,
    log_text: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> int:
    with session_scope() as session:
        row = CrawlerTask(
            crawler_name=crawler_name,
            status=status,
            total_count=total_count,
            success_count=success_count,
            error_message=error_message,
            log_text=log_text,
            start_time=start_time or datetime.utcnow(),
            end_time=end_time or datetime.utcnow(),
        )
        session.add(row)
        session.flush()
        return int(row.id)


def recent_crawler_tasks(limit: int = 20) -> list[Dict[str, Any]]:
    with session_scope() as session:
        rows = session.scalars(
            select(CrawlerTask).order_by(CrawlerTask.id.desc()).limit(limit)
        ).all()
        return [
            {
                "id": r.id,
                "crawler_name": r.crawler_name,
                "status": r.status,
                "total_count": r.total_count,
                "success_count": r.success_count,
                "error_message": r.error_message,
                "start_time": str(r.start_time) if r.start_time else None,
                "end_time": str(r.end_time) if r.end_time else None,
            }
            for r in rows
        ]


def processing_status() -> Dict[str, Any]:
    """优先读最近一轮 crawl_run，这样 worker 里的结果能出现在 API 进程。"""
    try:
        from backend.src.models.crawl import CrawlRun

        with session_scope() as session:
            run = session.scalar(select(CrawlRun).order_by(CrawlRun.id.desc()).limit(1))
            if run is not None:
                stamp = run.finished_at or run.started_at
                stamp_s = stamp.isoformat() if stamp else None
                return {
                    "last_pipeline_at": stamp_s if run.pipeline_stats else None,
                    "last_pipeline_stats": run.pipeline_stats,
                    "last_cluster_at": stamp_s if run.cluster_stats else None,
                    "last_cluster_stats": run.cluster_stats,
                }
    except Exception as exc:
        logger.warning("读取采集轮次失败，回退进程内状态: %s", exc)
    return dict(_PROCESS_STATE)


def health_check() -> Dict[str, Any]:
    checks: Dict[str, Any] = {"ok": True, "checks": {}}

    # DB
    t0 = time.time()
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            ext = conn.execute(
                text("SELECT extname FROM pg_extension WHERE extname='vector'")
            ).scalar()
        checks["checks"]["database"] = {
            "status": "ok",
            "latency_ms": int((time.time() - t0) * 1000),
            "pgvector": bool(ext),
        }
    except Exception as e:
        checks["ok"] = False
        checks["checks"]["database"] = {"status": "error", "error": str(e)}

    # Redis
    try:
        import redis

        r = redis.Redis.from_url(RedisEnvConfig.load().url, decode_responses=True)
        r.ping()
        checks["checks"]["redis"] = {"status": "ok"}
    except Exception as e:
        checks["checks"]["redis"] = {"status": "degraded", "error": str(e)}

    # vector coverage：仅统计应向量化的稿件（排除 rejected）
    try:
        with session_scope() as session:
            eligible = News.process_status != "rejected"
            total = session.scalar(select(func.count()).select_from(News).where(eligible)) or 0
            with_emb = (
                session.scalar(
                    select(func.count())
                    .select_from(News)
                    .where(eligible, News.embedding.is_not(None))
                )
                or 0
            )
            rejected = (
                session.scalar(
                    select(func.count())
                    .select_from(News)
                    .where(News.process_status == "rejected")
                )
                or 0
            )
        checks["checks"]["vector_index"] = {
            "status": "ok",
            "news_total": int(total),
            "news_with_embedding": int(with_emb),
            "news_rejected": int(rejected),
        }
    except Exception as e:
        checks["ok"] = False
        checks["checks"]["vector_index"] = {"status": "error", "error": str(e)}

    return checks
