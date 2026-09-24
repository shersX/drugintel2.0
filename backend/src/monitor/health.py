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

    # vector index / embedding coverage
    try:
        with session_scope() as session:
            total = session.scalar(select(func.count()).select_from(News)) or 0
            with_emb = (
                session.scalar(
                    select(func.count()).select_from(News).where(News.embedding.is_not(None))
                )
                or 0
            )
        checks["checks"]["vector_index"] = {
            "status": "ok",
            "news_total": int(total),
            "news_with_embedding": int(with_emb),
        }
    except Exception as e:
        checks["ok"] = False
        checks["checks"]["vector_index"] = {"status": "error", "error": str(e)}

    return checks
