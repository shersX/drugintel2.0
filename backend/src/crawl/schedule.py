"""采集调度：默认停止，前端启动后立刻跑第一轮，再按每小时或每天时刻持续执行。"""

from __future__ import annotations

import asyncio
import re
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import select

from backend.src.core.config import RedisEnvConfig, llm_readiness
from backend.src.core.logger import get_logger
from backend.src.crawlers.registry import CRAWLER_REGISTRY
from backend.src.db.session import session_scope
from backend.src.models.crawl import CrawlConfig, CrawlRun
from backend.src.models.entities import CrawlerTask

logger = get_logger("crawl.schedule")

SH = ZoneInfo("Asia/Shanghai")
LOCK_KEY = "drugintel:crawl:lock"
LOCK_TTL_SEC = 2 * 60 * 60
# 单源爬取+重试上限；超时后记失败并放行其它源
CRAWLER_TIMEOUT_SEC = 10 * 60
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


def _validate(
    mode: str,
    daily_time: Optional[str],
    crawler_keys: List[str],
    *,
    interval_minutes: Optional[int] = None,
) -> List[str]:
    if mode not in {"manual", "interval", "hourly", "daily"}:
        raise CrawlConfigError("节奏需为手动 / 间隔 / 每小时 / 每天")
    if mode == "daily":
        if not daily_time:
            raise CrawlConfigError("每天采集需要选择时刻")
        parse_daily_time(daily_time)
    if mode == "interval":
        mins = int(interval_minutes or 0)
        if mins < 15:
            raise CrawlConfigError("间隔采集至少 15 分钟")
    # 与监控页可选列表一致：仅新闻爬虫；去掉未知或已禁用源
    try:
        from backend.src.crawlers.settings_store import list_crawler_settings

        with session_scope() as session:
            enabled = {
                item["crawler_key"]
                for item in list_crawler_settings(session)
                if item.get("enabled", True) and item.get("kind", "news") == "news"
            }
    except Exception:
        enabled = {
            key
            for key, meta in CRAWLER_REGISTRY.items()
            if meta.get("enabled", True) and meta.get("kind", "news") == "news"
        }
    keys: List[str] = []
    for key in crawler_keys or []:
        name = str(key).strip()
        meta = CRAWLER_REGISTRY.get(name)
        if meta is None:
            raise CrawlConfigError(f"未知爬虫：{name}")
        if meta.get("kind", "news") != "news":
            continue
        if name not in enabled:
            continue
        if name not in keys:
            keys.append(name)
    if not keys:
        raise CrawlConfigError("至少选择一个已启用的新闻爬虫")
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


def renew_lock(token: str) -> bool:
    """进度心跳：仅当锁仍属本轮时续期。"""
    client = _redis()
    if client.get(LOCK_KEY) != token:
        return False
    client.expire(LOCK_KEY, LOCK_TTL_SEC)
    return True


def update_run_progress(run_id: int, fields: Dict[str, Any], *, lock_token: Optional[str] = None) -> None:
    """短事务写入 CrawlRun.progress，并可续期采集锁。

    支持：
    - 顶层字段（兼容旧进度条）
    - fields["round"] 字典合并进 progress.round，并镜像 stage/label 等到顶层
    - fields["by_crawler"] 为 {key: partial} 时按源合并
    """
    if lock_token:
        try:
            renew_lock(lock_token)
        except Exception:
            logger.warning("续期采集锁失败 run_id=%s", run_id)
    with session_scope() as session:
        run = session.get(CrawlRun, run_id)
        if run is None:
            return
        current = dict(run.progress or {})
        payload = {k: v for k, v in fields.items() if v is not None}

        round_patch = payload.pop("round", None)
        by_patch = payload.pop("by_crawler", None)

        if isinstance(round_patch, dict):
            round_data = dict(current.get("round") or {})
            round_data.update({k: v for k, v in round_patch.items() if v is not None})
            current["round"] = round_data
            for key in ("stage", "label", "detail", "crawlers_done", "crawlers_total"):
                if key in round_data:
                    current[key] = round_data[key]

        if isinstance(by_patch, dict):
            by_crawler = dict(current.get("by_crawler") or {})
            for key, partial in by_patch.items():
                if not isinstance(partial, dict):
                    continue
                prev = dict(by_crawler.get(str(key)) or {})
                prev.update({k: v for k, v in partial.items() if v is not None})
                prev["updated_at"] = now_sh().isoformat()
                by_crawler[str(key)] = prev
            current["by_crawler"] = by_crawler

        current.update(payload)
        current["updated_at"] = now_sh().isoformat()
        run.progress = current


def abandon_orphan_runs(reason: str = "进程中断，本轮已作废") -> Dict[str, Any]:
    """将卡住的 status=running 轮次标为 aborted，并清 Redis 采集锁。

    不改 CrawlConfig.running（定时意图保留）。
    """
    msg = (reason or "进程中断，本轮已作废").strip()[:4000]
    now = now_sh()
    abandoned_ids: List[int] = []
    with session_scope() as session:
        rows = session.scalars(
            select(CrawlRun).where(CrawlRun.status == "running")
        ).all()
        for run in rows:
            run.status = "aborted"
            run.finished_at = now
            run.error = msg
            progress = dict(run.progress or {})
            progress.update(
                {
                    "stage": "failed",
                    "label": "本轮已中断",
                    "detail": msg,
                    "updated_at": now.isoformat(),
                }
            )
            run.progress = progress
            abandoned_ids.append(int(run.id))
    try:
        _redis().delete(LOCK_KEY)
    except Exception:
        logger.warning("清除采集锁失败", exc_info=True)
    if abandoned_ids:
        logger.warning("已作废卡住的采集轮次 ids=%s reason=%s", abandoned_ids, msg)
    return {"abandoned": len(abandoned_ids), "ids": abandoned_ids}


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
                "kind": item.get("kind", "news"),
                "enabled": True,
            }
            for item in items
            if item.get("enabled", True) and item.get("kind", "news") == "news"
        ]
    except Exception:
        return [
            {
                "key": key,
                "name": str(meta.get("name") or key),
                "kind": meta.get("kind", "news"),
                "enabled": True,
            }
            for key, meta in CRAWLER_REGISTRY.items()
            if meta.get("enabled", True) and meta.get("kind", "news") == "news"
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
        "progress": run.progress,
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
            "interval_minutes": cfg.interval_minutes,
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
        ready = llm_readiness()
        active = bool(last and last.status == "running")
        return {
            "running": cfg.running,
            "schedule_mode": cfg.schedule_mode,
            "daily_time": cfg.daily_time,
            "interval_minutes": cfg.interval_minutes,
            "crawler_keys": list(cfg.crawler_keys or []),
            "armed_at": _iso(cfg.armed_at),
            "active": active,
            "last_run": _run_dict(last),
            "progress": (last.progress if last else None),
            "next_run_at": _iso(next_at),
            "crawlers": _latest_tasks(session),
            "available": _available(),
            "llm_ready": ready["ready"],
            "llm_message": ready["message"],
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


def start_schedule(
    mode: str,
    daily_time: Optional[str],
    crawler_keys: List[str],
    *,
    interval_minutes: Optional[int] = None,
) -> Dict[str, Any]:
    ready = llm_readiness()
    if not ready["ready"]:
        raise CrawlConfigError(ready["message"] or "尚未配置 LLM，请先到「模型配置」设置")
    keys = _validate(mode, daily_time, crawler_keys, interval_minutes=interval_minutes)
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
        if mode == "interval":
            cfg.interval_minutes = int(interval_minutes or 60)
        cfg.crawler_keys = keys
        cfg.armed_at = now_sh()
    # manual / 首次启动立即跑一轮；纯定时等待 tick
    if mode != "manual":
        try:
            _enqueue("manual")
        except CrawlConfigError:
            with session_scope() as session:
                cfg = _get_or_create(session)
                cfg.running = False
            raise
    else:
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
    mode = cfg.schedule_mode or "hourly"
    if mode == "manual":
        return False
    if mode == "hourly":
        return hourly_due(
            last.started_at if last else None,
            last.status if last else None,
            now,
        )
    if mode == "interval":
        mins = int(cfg.interval_minutes or 60)
        ref = last.started_at if last else cfg.armed_at
        if ref is None:
            return True
        if getattr(ref, "tzinfo", None) is None:
            ref = ref.replace(tzinfo=now.tzinfo)
        return (now - ref).total_seconds() >= mins * 60
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
        payload = asyncio.run(_execute(keys, run_id=run_id, lock_token=token))
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
            try:
                update_run_progress(
                    run_id,
                    {"stage": "failed", "label": "本轮异常", "detail": str(exc)[:500]},
                    lock_token=token,
                )
            except Exception:
                pass
            _finish(run_id, "failed", str(exc))
        return {"status": "failed", "error": str(exc)}
    finally:
        try:
            release_lock(token)
        except Exception:
            logger.exception("释放采集锁失败")


async def _execute(
    keys: List[str],
    *,
    run_id: Optional[int] = None,
    lock_token: Optional[str] = None,
) -> Dict[str, Any]:
    """并发爬取；每源完成即 pipeline；全部终态后统一聚类。"""
    from backend.src.clustering.service import run_clustering
    from backend.src.crawlers.registry import (
        MAX_RETRY_ATTEMPTS,
        _run_crawler_with_retry,
        format_crawler_error,
    )
    from backend.src.crawlers.settings_store import merged_crawler_registry
    from backend.src.monitor.health import record_crawler_task
    from backend.src.processors.pipeline import run_processing_pipeline

    merged = merged_crawler_registry()
    configs = {
        key: merged[key]
        for key in keys
        if key in merged
        and merged[key].get("enabled", True)
        and merged[key].get("kind", "news") == "news"
        and merged[key].get("function") is not None
    }
    if not configs:
        return {"status": "failed", "error": "没有可运行的爬虫"}

    total = len(configs)

    def _progress(fields: Dict[str, Any]) -> None:
        if run_id is None:
            return
        update_run_progress(run_id, fields, lock_token=lock_token)

    def _set_crawler(key: str, partial: Dict[str, Any], *, done: Optional[int] = None) -> None:
        round_patch: Dict[str, Any] = {
            "stage": "running",
            "label": "采集中",
            "crawlers_total": total,
        }
        if done is not None:
            round_patch["crawlers_done"] = done
            round_patch["detail"] = f"已完成 {done}/{total}"
        _progress({"round": round_patch, "by_crawler": {key: partial}})

    started = now_sh()
    initial_by = {
        key: {"stage": "crawling", "label": "爬取中"}
        for key in configs
    }
    _progress(
        {
            "round": {
                "stage": "running",
                "label": "采集中",
                "crawlers_done": 0,
                "crawlers_total": total,
                "detail": "开始并发爬取",
            },
            "by_crawler": initial_by,
            "stage": "running",
            "label": "采集中",
            "crawlers_done": 0,
            "crawlers_total": total,
        }
    )

    task_map: Dict[asyncio.Task, str] = {}
    for name, config in configs.items():
        crawler_func = config["function"]
        task_kwargs = {
            "page_count": int(config.get("page_count", 1) or 1),
            "fetch_details": bool(config.get("fetch_details", True)),
            "concurrency": int(config.get("concurrency", 5) or 5),
        }
        task = asyncio.create_task(
            asyncio.wait_for(
                _run_crawler_with_retry(
                    crawler_key=name,
                    crawler_func=crawler_func,
                    kwargs=task_kwargs,
                ),
                timeout=CRAWLER_TIMEOUT_SEC,
            )
        )
        task_map[task] = name

    failures: Dict[str, str] = {}
    pipeline_stats_all: List[Dict[str, Any]] = []
    done_count = 0
    pending: set[asyncio.Task] = set(task_map.keys())

    while pending:
        done_set, pending = await asyncio.wait(
            pending, return_when=asyncio.FIRST_COMPLETED
        )
        for task in done_set:
            name = task_map[task]
            display = CRAWLER_REGISTRY.get(name, {}).get("name") or name
            finished_at = now_sh()
            items: List[Any] = []
            err: Optional[str] = None
            log_text = ""

            try:
                result = task.result()
            except asyncio.TimeoutError:
                err = f"单源超时（{CRAWLER_TIMEOUT_SEC // 60} 分钟）"
                logger.error("爬虫 %s %s", name, err)
            except Exception as exc:
                err = format_crawler_error(exc)
                logger.error("爬虫 %s 执行失败: %s", name, err)
            else:
                crawler_data, crawl_exc, log_text = result
                if crawl_exc is not None:
                    err = format_crawler_error(crawl_exc)
                    logger.error(
                        "爬虫 %s 重试 %s 次后仍失败: %s",
                        name,
                        MAX_RETRY_ATTEMPTS,
                        err,
                    )
                else:
                    items = list(crawler_data or [])

            done_count += 1
            record_crawler_task(
                crawler_name=name,
                status="failed" if err else "success",
                total_count=len(items),
                success_count=0 if err else len(items),
                error_message=err,
                log_text=log_text or None,
                start_time=started,
                end_time=finished_at,
            )

            if err:
                failures[name] = err
                _set_crawler(
                    name,
                    {"stage": "failed", "label": "失败", "detail": err[:500]},
                    done=done_count,
                )
                continue

            _set_crawler(
                name,
                {
                    "stage": "filtering",
                    "label": "处理中",
                    "detail": f"{display} 爬取 {len(items)} 条",
                    "items_in": len(items),
                },
                done=done_count,
            )

            def _crawler_progress(fields: Dict[str, Any], *, _key: str = name) -> None:
                patch = {
                    "stage": fields.get("stage") or "filtering",
                    "label": fields.get("label") or "处理中",
                }
                for k in ("detail", "items_in", "items_out", "raw_inserted"):
                    if fields.get(k) is not None:
                        patch[k] = fields[k]
                _set_crawler(_key, patch)

            try:
                outcome = await run_processing_pipeline(
                    {name: items},
                    persist=True,
                    progress=_crawler_progress,
                )
                stats = outcome.get("stats") or {}
                pipeline_stats_all.append({"crawler": name, **stats})
                _set_crawler(
                    name,
                    {
                        "stage": "done",
                        "label": "处理完成",
                        "detail": f"落库 {stats.get('raw_inserted', 0)} 条",
                        "raw_inserted": stats.get("raw_inserted", 0),
                    },
                    done=done_count,
                )
            except Exception as exc:
                logger.exception("爬虫 %s 后处理失败", name)
                msg = str(exc)[:500]
                failures[name] = f"后处理失败：{msg}"
                _set_crawler(
                    name,
                    {"stage": "failed", "label": "后处理失败", "detail": msg},
                    done=done_count,
                )

    if len(failures) == total:
        summary = "；".join(f"{key}: {msg}" for key, msg in failures.items())
        _progress(
            {
                "round": {"stage": "failed", "label": "全部失败", "detail": summary},
                "stage": "failed",
                "label": "全部失败",
                "detail": summary,
            }
        )
        return {"status": "failed", "error": f"全部爬虫失败：{summary}"}

    _progress(
        {
            "round": {
                "stage": "clustering",
                "label": "聚类中",
                "crawlers_done": total,
                "crawlers_total": total,
                "detail": "整轮统一聚类",
            },
            "stage": "clustering",
            "label": "聚类中",
        }
    )
    cluster_stats = run_clustering()
    _progress(
        {
            "round": {
                "stage": "done",
                "label": "本轮完成",
                "crawlers_done": total,
                "crawlers_total": total,
            },
            "stage": "done",
            "label": "本轮完成",
        }
    )
    note = None
    if failures:
        note = "部分爬虫失败：" + "；".join(f"{key}: {msg}" for key, msg in failures.items())
    merged_pipeline: Dict[str, Any] = {"by_crawler": pipeline_stats_all}
    if pipeline_stats_all:
        merged_pipeline["raw_inserted"] = sum(
            int(s.get("raw_inserted") or 0) for s in pipeline_stats_all
        )
    return {
        "status": "success",
        "error": note,
        "pipeline": merged_pipeline,
        "cluster": cluster_stats,
    }
