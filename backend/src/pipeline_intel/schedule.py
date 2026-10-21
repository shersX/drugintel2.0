"""管线独立调度配置。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import select

from backend.src.crawlers.registry import pipeline_crawler_keys
from backend.src.db.session import session_scope
from backend.src.models.pipeline import PipelineCrawlConfig

SHANGHAI = ZoneInfo("Asia/Shanghai")

_VALID_MODES = {"manual", "interval", "daily", "weekly"}


def _get_or_create(session) -> PipelineCrawlConfig:
    row = session.scalar(select(PipelineCrawlConfig).limit(1))
    if row is None:
        row = PipelineCrawlConfig(
            running=False,
            schedule_mode="manual",
            crawler_keys=pipeline_crawler_keys(),
            source_url="https://www.simcere.com/kxcx/yggx.aspx",
        )
        session.add(row)
        session.flush()
    return row


def get_pipeline_crawl_config() -> Dict[str, Any]:
    with session_scope() as session:
        row = _get_or_create(session)
        return _public(row)


def _public(row: PipelineCrawlConfig) -> Dict[str, Any]:
    return {
        "running": bool(row.running),
        "schedule_mode": row.schedule_mode or "manual",
        "interval_minutes": row.interval_minutes,
        "daily_time": row.daily_time,
        "weekly_day": row.weekly_day,
        "crawler_keys": list(row.crawler_keys or []),
        "source_url": row.source_url,
        "armed_at": row.armed_at.isoformat() if row.armed_at else None,
        "available_keys": pipeline_crawler_keys(),
    }


def update_pipeline_crawl_config(
    *,
    running: Optional[bool] = None,
    schedule_mode: Optional[str] = None,
    interval_minutes: Optional[int] = None,
    daily_time: Optional[str] = None,
    weekly_day: Optional[int] = None,
    crawler_keys: Optional[List[str]] = None,
    source_url: Optional[str] = None,
) -> Dict[str, Any]:
    with session_scope() as session:
        row = _get_or_create(session)
        if schedule_mode is not None:
            mode = schedule_mode.strip().lower()
            if mode not in _VALID_MODES:
                raise ValueError(f"不支持的 schedule_mode: {schedule_mode}")
            row.schedule_mode = mode
        if interval_minutes is not None:
            mins = int(interval_minutes)
            if mins < 15:
                raise ValueError("interval_minutes 建议至少 15（视觉调用成本）")
            row.interval_minutes = mins
        if daily_time is not None:
            row.daily_time = daily_time.strip() or None
        if weekly_day is not None:
            day = int(weekly_day)
            if day < 0 or day > 6:
                raise ValueError("weekly_day 需为 0–6（周一=0 或按本地约定）")
            row.weekly_day = day
        if crawler_keys is not None:
            allowed = set(pipeline_crawler_keys())
            keys = [k for k in crawler_keys if k in allowed]
            row.crawler_keys = keys
        if source_url is not None:
            row.source_url = source_url.strip() or None
        if running is not None:
            row.running = bool(running)
            if row.running:
                row.armed_at = datetime.now(tz=SHANGHAI)
            else:
                row.armed_at = None
        session.flush()
        return _public(row)


def should_run_pipeline_tick(now: Optional[datetime] = None) -> bool:
    """Celery beat 调用：当前是否应触发一轮管线同步。"""
    now = now or datetime.now(tz=SHANGHAI)
    if now.tzinfo is None:
        now = now.replace(tzinfo=SHANGHAI)
    else:
        now = now.astimezone(SHANGHAI)

    with session_scope() as session:
        row = _get_or_create(session)
        if not row.running:
            return False
        mode = (row.schedule_mode or "manual").lower()
        if mode == "manual":
            return False
        armed = row.armed_at
        if armed is not None and armed.tzinfo is None:
            armed = armed.replace(tzinfo=SHANGHAI)
        elif armed is not None:
            armed = armed.astimezone(SHANGHAI)

        if mode == "interval":
            mins = int(row.interval_minutes or 60)
            if armed is None:
                return True
            return now - armed >= timedelta(minutes=mins)
        if mode == "daily":
            target = (row.daily_time or "08:00").strip()
            hh, mm = _parse_hm(target)
            if now.hour == hh and now.minute == mm:
                if armed and armed.date() == now.date() and armed.hour == hh:
                    return False
                return True
            return False
        if mode == "weekly":
            day = int(row.weekly_day if row.weekly_day is not None else 0)
            # Python: Monday=0
            if now.weekday() != day:
                return False
            target = (row.daily_time or "08:00").strip()
            hh, mm = _parse_hm(target)
            if now.hour == hh and now.minute == mm:
                if armed and armed.date() == now.date():
                    return False
                return True
            return False
    return False


def mark_pipeline_tick_fired() -> None:
    with session_scope() as session:
        row = _get_or_create(session)
        row.armed_at = datetime.now(tz=SHANGHAI)
        session.flush()


def _parse_hm(value: str) -> tuple[int, int]:
    parts = value.split(":")
    return int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
