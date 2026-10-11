"""Celery 应用与定时任务。"""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_process_init

from backend.src.core.config import RedisEnvConfig

redis_url = RedisEnvConfig.load().url
celery_app = Celery("drugintel", broker=redis_url, backend=redis_url)
celery_app.conf.timezone = "Asia/Shanghai"


@worker_process_init.connect
def _ensure_schema_on_worker(**_kwargs):
    from backend.src.db.schema import ensure_schema

    ensure_schema()


celery_app.conf.beat_schedule = {
    "check-alerts-hourly": {
        "task": "tasks.alert_tasks.check_new_news_alerts",
        "schedule": crontab(minute=0),
    },
    "crawl-tick-every-minute": {
        "task": "tasks.crawl_tasks.crawl_tick",
        "schedule": crontab(),
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


@celery_app.task(name="tasks.crawl_tasks.crawl_tick")
def crawl_tick() -> dict:
    from backend.src.crawl.schedule import tick

    return tick()


@celery_app.task(name="tasks.crawl_tasks.run_crawl_pipeline")
def run_crawl_pipeline(trigger: str = "manual") -> dict:
    from backend.src.crawl.schedule import run_pipeline

    return run_pipeline(trigger)
