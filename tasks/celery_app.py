"""Celery 应用与定时任务。"""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_init

from backend.src.core.config import RedisEnvConfig

redis_url = RedisEnvConfig.load().url
celery_app = Celery("drugintel", broker=redis_url, backend=redis_url)
celery_app.conf.timezone = "Asia/Shanghai"


@worker_init.connect
def _ensure_schema_on_worker(**_kwargs):
    """在主进程、fork 之前跑一次。

    勿放在 worker_process_init：ensure_schema（含实体词典种子）过慢，
    Celery 会等不到子进程 UP 后 SIGKILL，表现为采集永远起不来。
    """
    from backend.src.crawl.schedule import abandon_orphan_runs
    from backend.src.db.schema import ensure_schema

    ensure_schema()
    try:
        abandon_orphan_runs(
            "Worker 启动：作废未完成的采集轮次",
            cooperative_cancel=False,
        )
    except Exception:
        # worker 仍可启动；卡死状态可稍后由 API 或手动 abandon 清理
        pass


celery_app.conf.beat_schedule = {
    "check-alerts-hourly": {
        "task": "tasks.alert_tasks.check_new_news_alerts",
        "schedule": crontab(minute=0),
    },
    "crawl-tick-every-minute": {
        "task": "tasks.crawl_tasks.crawl_tick",
        "schedule": crontab(),
    },
    "pipeline-tick-every-minute": {
        "task": "tasks.pipeline_tasks.pipeline_tick",
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


@celery_app.task(name="tasks.pipeline_tasks.pipeline_tick")
def pipeline_tick() -> dict:
    from backend.src.pipeline_intel.schedule import mark_pipeline_tick_fired, should_run_pipeline_tick

    if not should_run_pipeline_tick():
        return {"status": "idle"}
    mark_pipeline_tick_fired()
    celery_app.send_task(
        "tasks.pipeline_tasks.run_pipeline_intel",
        kwargs={"force": False},
    )
    return {"status": "enqueued"}


@celery_app.task(name="tasks.pipeline_tasks.run_pipeline_intel")
def run_pipeline_intel(force: bool = False) -> dict:
    import asyncio

    from backend.src.pipeline_intel.service import run_pipeline_sync

    return asyncio.run(run_pipeline_sync(force=force))


@celery_app.task(
    name="tasks.forecast_tasks.generate_event_forecast",
    bind=True,
    max_retries=20,
)
def generate_event_forecast(self, event_id: int) -> dict:
    """异步生成事件研报；受 ANALYST_MAX_CONCURRENCY 限制。"""
    import os

    from sqlalchemy import func, select

    from backend.src.agents.analyst import run_event_forecast_job
    from backend.src.db.session import session_scope
    from backend.src.models.event import Event

    try:
        limit = max(1, int(os.getenv("ANALYST_MAX_CONCURRENCY", "2")))
    except ValueError:
        limit = 2

    with session_scope() as session:
        running = session.scalar(
            select(func.count())
            .select_from(Event)
            .where(Event.forecast_status == "running")
        ) or 0
        # 本任务尚未置 running；若已达上限则延后
        if int(running) >= limit:
            raise self.retry(countdown=15)

    return run_event_forecast_job(int(event_id))
