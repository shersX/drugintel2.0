"""采集调度：默认停止，前端启动后立刻跑第一轮，再按每小时或每天时刻持续执行。"""

from __future__ import annotations

import asyncio
import re
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import select

from backend.src.core.config import RedisEnvConfig
from backend.src.core.logger import get_logger
from backend.src.crawlers.registry import CRAWLER_REGISTRY
from backend.src.db.session import session_scope
from backend.src.models.crawl import CrawlConfig, CrawlRun
from backend.src.models.entities import CrawlerTask

logger = get_logger("crawl.schedule")

SH = ZoneInfo("Asia/Shanghai")
LOCK_KEY = "drugintel:crawl:lock"
LOCK_TTL_SEC = 2 * 60 * 60
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
_RELEASE_LUA = """
if redis.call("get", KEYS[1]) == ARGV[1] then
  return redis.call("del", KEYS[1])
else
  return 0
end
"""


class CrawlConfigError(ValueError):
    """前端可展示的配置或投递错误。"""


def now_sh() -> datetime:
    return datetime.now(SH)


def _as_sh(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=SH)
    return value.astimezone(SH)


def _iso(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return _as_sh(value).isoformat()


def parse_daily_time(value: str) -> tuple[int, int]:
    raw = (value or "").strip()
    if len(raw) >= 5:
        raw = raw[:5]
    match = _TIME_RE.match(raw)
    if match is None:
        raise CrawlConfigError("每天的时刻需要是 HH:MM")
    return int(match.group(1)), int(match.group(2))


def _slot(now: datetime, daily_time: str) -> datetime:
    hour, minute = parse_daily_time(daily_time)
    return now.replace(hour=hour, minute=minute, second=0, microsecond=0)


def hourly_due(
    last_started: Optional[datetime],
    last_status: Optional[str],
    now: datetime,
) -> bool:
    if last_status == "running":
        return False
    if last_started is None:
        return True
    return now - _as_sh(last_started) >= timedelta(hours=1)


def daily_due(
    now: datetime,
    armed_at: Optional[datetime],
    daily_time: Optional[str],
    scheduled_today: bool,
) -> bool:
    if armed_at is None or not daily_time:
        return False
    slot = _slot(now, daily_time)
    if now < slot:
        return False
    if _as_sh(armed_at) > slot:
        return False
    if scheduled_today:
        return False
    return True


def compute_next_run(
    *,
    mode: str,
    daily_time: Optional[str],
    armed_at: Optional[datetime],
    last_started: Optional[datetime],
    scheduled_today: bool,
    now: datetime,
) -> Optional[datetime]:
    if mode == "hourly":
        if last_started is None:
            return None
        return _as_sh(last_started) + timedelta(hours=1)
    if not daily_time or armed_at is None:
        return None
    slot = _slot(now, daily_time)
    armed = _as_sh(armed_at)
    if armed > slot:
        return slot + timedelta(days=1)
    if not scheduled_today:
        return slot if slot >= now else now
    return slot + timedelta(days=1)


def _validate(mode: str, daily_time: Optional[str], crawler_keys: List[str]) -> List[str]:
    if mode not in {"hourly", "daily"}:
        raise CrawlConfigError("节奏只能是每小时或每天")
    if mode == "daily":
        if not daily_time:
            raise CrawlConfigError("每天采集需要选择时刻")
        parse_daily_time(daily_time)
    keys: List[str] = []
    for key in crawler_keys or []:
        name = str(key).strip()
        if name not in CRAWLER_REGISTRY:
            raise CrawlConfigError(f"未知爬虫：{name}")
        if name not in keys:
            keys.append(name)
    if not keys:
        raise CrawlConfigError("至少选择一个爬虫")
    return keys


def _get_or_create(session) -> CrawlConfig:
    row = session.scalar(select(CrawlConfig).order_by(CrawlConfig.id.asc()).limit(1))
    if row is None:
        row = CrawlConfig(running=False, schedule_mode="hourly", crawler_keys=[])
        session.add(row)
        session.flush()
    return row


def _latest_run(session) -> Optional[CrawlRun]:
    return session.scalar(select(CrawlRun).order_by(CrawlRun.id.desc()).limit(1))


def _scheduled_today(session, now: datetime) -> bool:
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    found = session.scalar(
        select(CrawlRun.id)
        .where(CrawlRun.trigger == "schedule")
        .where(CrawlRun.started_at >= start)
        .where(CrawlRun.started_at < end)
        .limit(1)
    )
    return found is not None


def _redis():
    import redis

    return redis.Redis.from_url(RedisEnvConfig.load().url, decode_responses=True)


def acquire_lock() -> Optional[str]:
    token = uuid.uuid4().hex
    ok = _redis().set(LOCK_KEY, token, nx=True, ex=LOCK_TTL_SEC)
    if not ok:
        return None
    return token


def release_lock(token: str) -> None:
    _redis().eval(_RELEASE_LUA, 1, LOCK_KEY, token)


def _available() -> List[Dict[str, Any]]:
    """可选爬虫列表：合并 DB 后仅返回 enabled=true 的源。"""
    try:
        from backend.src.crawlers.settings_store import list_crawler_settings

        with session_scope() as session:
            items = list_crawler_settings(session)
        return [
            {
                "key": item["crawler_key"],
                "name": item["name"],
                "enabled": True,
            }
            for item in items
            if item.get("enabled", True)
        ]
    except Exception:
        return [
            {
                "key": key,
                "name": str(meta.get("name") or key),
                "enabled": True,
            }
            for key, meta in CRAWLER_REGISTRY.items()
            if meta.get("enabled", True)
        ]


def _run_dict(run: Optional[CrawlRun]) -> Optional[Dict[str, Any]]:
    if run is None:
        return None
    return {
        "id": run.id,
        "status": run.status,
        "trigger": run.trigger,
        "started_at": _iso(run.started_at),
        "finished_at": _iso(run.finished_at),
        "error": run.error,
        "pipeline_stats": run.pipeline_stats,
        "cluster_stats": run.cluster_stats,
    }


def _latest_tasks(session) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for key, meta in CRAWLER_REGISTRY.items():
        task = session.scalar(
            select(CrawlerTask)
            .where(CrawlerTask.crawler_name == key)
            .order_by(CrawlerTask.id.desc())
            .limit(1)
        )
        items.append(
            {
                "key": key,
                "name": str(meta.get("name") or key),
                "status": task.status if task else None,
                "total_count": task.total_count if task else 0,
                "success_count": task.success_count if task else 0,
                "error_message": task.error_message if task else None,
                "log_text": task.log_text if task else None,
                "start_time": _iso(task.start_time) if task and task.start_time else None,
                "end_time": _iso(task.end_time) if task and task.end_time else None,
            }
        )
    return items


def config_payload() -> Dict[str, Any]:
    with session_scope() as session:
        cfg = _get_or_create(session)
        return {
            "running": cfg.running,
            "schedule_mode": cfg.schedule_mode,
            "daily_time": cfg.daily_time,
            "crawler_keys": list(cfg.crawler_keys or []),
            "armed_at": _iso(cfg.armed_at),
            "available": _available(),
        }


def status_payload() -> Dict[str, Any]:
    now = now_sh()
    with session_scope() as session:
        cfg = _get_or_create(session)
        last = _latest_run(session)
        scheduled_today = _scheduled_today(session, now)
        next_at = None
        if cfg.running:
            next_at = compute_next_run(
                mode=cfg.schedule_mode,
                daily_time=cfg.daily_time,
                armed_at=cfg.armed_at,
                last_started=last.started_at if last else None,
                scheduled_today=scheduled_today,
                now=now,
            )
        return {
            "running": cfg.running,
            "schedule_mode": cfg.schedule_mode,
            "daily_time": cfg.daily_time,
            "crawler_keys": list(cfg.crawler_keys or []),
            "armed_at": _iso(cfg.armed_at),
            "active": bool(last and last.status == "running"),
            "last_run": _run_dict(last),
            "next_run_at": _iso(next_at),
            "crawlers": _latest_tasks(session),
            "available": _available(),
        }


def _enqueue(trigger: str) -> None:
    try:
        from tasks.celery_app import celery_app

        celery_app.send_task(
            "tasks.crawl_tasks.run_crawl_pipeline",
            kwargs={"trigger": trigger},
        )
    except Exception as exc:
        raise CrawlConfigError(f"无法投递采集任务，请确认 Redis 与 worker 已启动：{exc}") from exc


def start_schedule(mode: str, daily_time: Optional[str], crawler_keys: List[str]) -> Dict[str, Any]:
    keys = _validate(mode, daily_time, crawler_keys)
    with session_scope() as session:
        cfg = _get_or_create(session)
        if cfg.running:
            raise CrawlConfigError("采集已在运行，请先停止再修改")
        cfg.running = True
        cfg.schedule_mode = mode
        if mode == "daily" and daily_time:
            hour, minute = parse_daily_time(daily_time)
            cfg.daily_time = f"{hour:02d}:{minute:02d}"
        else:
            cfg.daily_time = None
        cfg.crawler_keys = keys
        cfg.armed_at = now_sh()
    try:
        _enqueue("manual")
    except CrawlConfigError:
        with session_scope() as session:
            cfg = _get_or_create(session)
            cfg.running = False
        raise
    return status_payload()


def stop_schedule() -> Dict[str, Any]:
    with session_scope() as session:
        cfg = _get_or_create(session)
        cfg.running = False
    return status_payload()


def _is_due(session, cfg: CrawlConfig, now: datetime) -> bool:
    last = _latest_run(session)
    if cfg.schedule_mode == "hourly":
        return hourly_due(
            last.started_at if last else None,
            last.status if last else None,
            now,
        )
    return daily_due(
        now,
        cfg.armed_at,
        cfg.daily_time,
        _scheduled_today(session, now),
    )


def tick() -> Dict[str, Any]:
    """Beat 每分钟调用。未启动时直接返回，不写记录。"""
    try:
        now = now_sh()
        with session_scope() as session:
            cfg = _get_or_create(session)
            if not cfg.running:
                return {"status": "idle"}
            due = _is_due(session, cfg, now)
        if not due:
            return {"status": "wait"}
        return run_pipeline("schedule")
    except Exception:
        logger.exception("采集 tick 失败")
        return {"status": "error"}


def _finish(
    run_id: int,
    status: str,
    error: Optional[str] = None,
    pipeline: Optional[dict] = None,
    cluster: Optional[dict] = None,
) -> None:
    with session_scope() as session:
        run = session.get(CrawlRun, run_id)
        if run is None:
            return
        run.status = status
        run.finished_at = now_sh()
        run.error = (error or None)
        if run.error:
            run.error = run.error[:4000]
        run.pipeline_stats = pipeline
        run.cluster_stats = cluster


def run_pipeline(trigger: str) -> Dict[str, Any]:
    try:
        token = acquire_lock()
    except Exception as exc:
        logger.exception("获取采集锁失败")
        return {"status": "error", "error": str(exc)}
    if token is None:
        return {"status": "busy"}
    run_id: Optional[int] = None
    try:
        with session_scope() as session:
            cfg = _get_or_create(session)
            if not cfg.running:
                return {"status": "stopped"}
            keys = [str(key) for key in (cfg.crawler_keys or [])]
            run = CrawlRun(status="running", trigger=trigger, started_at=now_sh())
            session.add(run)
            session.flush()
            run_id = int(run.id)
        payload = asyncio.run(_execute(keys))
        _finish(
            run_id,
            payload["status"],
            payload.get("error"),
            payload.get("pipeline"),
            payload.get("cluster"),
        )
        return payload
    except Exception as exc:
        logger.exception("采集轮次失败")
        if run_id is not None:
            _finish(run_id, "failed", str(exc))
        return {"status": "failed", "error": str(exc)}
    finally:
        try:
            release_lock(token)
        except Exception:
            logger.exception("释放采集锁失败")


async def _execute(keys: List[str]) -> Dict[str, Any]:
    from backend.src.clustering.service import run_clustering
    from backend.src.crawlers.registry import run_all_crawlers
    from backend.src.monitor.health import record_crawler_task
    from backend.src.processors.pipeline import run_processing_pipeline

    from backend.src.crawlers.settings_store import merged_crawler_registry

    merged = merged_crawler_registry()
    configs = {key: merged[key] for key in keys if key in merged}
    if not configs:
        return {"status": "failed", "error": "没有可运行的爬虫"}

    started = now_sh()
    batch = await run_all_crawlers(crawler_configs=configs)
    finished = now_sh()
    failures = getattr(batch, "failures", {}) or {}
    logs = getattr(batch, "logs", {}) or {}
    for key in configs:
        err = failures.get(key)
        items = batch.get(key) or []
        record_crawler_task(
            crawler_name=key,
            status="failed" if err else "success",
            total_count=len(items),
            success_count=0 if err else len(items),
            error_message=err,
            log_text=logs.get(key) or None,
            start_time=started,
            end_time=finished,
        )

    if len(failures) == len(configs):
        summary = "；".join(f"{key}: {msg}" for key, msg in failures.items())
        return {"status": "failed", "error": f"全部爬虫失败：{summary}"}

    outcome = await run_processing_pipeline(batch, persist=True)
    cluster_stats = run_clustering()
    note = None
    if failures:
        note = "部分爬虫失败：" + "；".join(f"{key}: {msg}" for key, msg in failures.items())
    return {
        "status": "success",
        "error": note,
        "pipeline": outcome.get("stats"),
        "cluster": cluster_stats,
    }
