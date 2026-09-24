"""Celery 应用与定时任务。"""

from __future__ import annotations

import asyncio
from datetime import datetime

from celery import Celery
from celery.schedules import crontab

from backend.src.core.config import RedisEnvConfig

redis_url = RedisEnvConfig.load().url
celery_app = Celery("drugintel", broker=redis_url, backend=redis_url)
celery_app.conf.timezone = "Asia/Shanghai"
celery_app.conf.beat_schedule = {
    "check-alerts-hourly": {
        "task": "tasks.alert_tasks.check_new_news_alerts",
        "schedule": crontab(minute=0),
    },
}


@celery_app.task(name="tasks.alert_tasks.check_new_news_alerts")
def check_new_news_alerts() -> dict:
    from sqlalchemy import select

    from backend.src.alerts.matcher import process_alerts_for_news
    from backend.src.db.session import session_scope
    from backend.src.models.news import News

    with session_scope() as session:
        rows = session.scalars(
            select(News).order_by(News.id.desc()).limit(50)
        ).all()
        return process_alerts_for_news(session, rows)


@celery_app.task(name="tasks.crawl_tasks.run_crawl_pipeline")
def run_crawl_pipeline() -> dict:
    from backend.src.crawlers.registry import CRAWLER_REGISTRY, run_all_crawlers
    from backend.src.monitor.health import record_crawler_task
    from backend.src.processors.pipeline import run_processing_pipeline

    async def _run():
        start = datetime.utcnow()
        results = await run_all_crawlers(crawler_configs=CRAWLER_REGISTRY)
        for name, items in results.items():
            record_crawler_task(
                crawler_name=name,
                status="success",
                total_count=len(items or []),
                success_count=len(items or []),
                start_time=start,
                end_time=datetime.utcnow(),
            )
        outcome = await run_processing_pipeline(results, persist=True)
        return outcome["stats"]

    return asyncio.run(_run())
