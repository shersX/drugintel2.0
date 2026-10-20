"""采集调度配置与每一轮运行记录。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.src.models.base import Base


class CrawlConfig(Base):
    """单行配置。running 为 false 时定时任务不采集。"""

    __tablename__ = "crawl_config"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    running: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    schedule_mode: Mapped[str] = mapped_column(String(20), default="hourly", nullable=False)
    daily_time: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    crawler_keys: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    armed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class CrawlRun(Base):
    """一轮采集（手动启动或到点调度）。"""

    __tablename__ = "crawl_run"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    trigger: Mapped[str] = mapped_column(String(20), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pipeline_stats: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    cluster_stats: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    progress: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
