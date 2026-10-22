"""研发管线：资产、变更、交易、页面快照、独立调度配置。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.src.models.base import Base


class PipelineAsset(Base):
    __tablename__ = "pipeline_asset"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "drug_id",
            "indication",
            "region",
            name="uq_pipeline_asset_identity",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id"), nullable=False, index=True
    )
    drug_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("drugs.id"), nullable=False, index=True
    )
    indication: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    therapeutic_area: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    target: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, index=True)
    modality: Mapped[str] = mapped_column(String(40), nullable=False, default="unknown", index=True)
    current_stage: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown")
    region: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    review_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="auto", index=True
    )
    # 人工锁定字段名列表，如 ["target","current_stage"]；crawl upsert 跳过覆盖
    manual_fields: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class PipelinePageSnapshot(Base):
    __tablename__ = "pipeline_page_snapshot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("companies.id"), nullable=True, index=True
    )
    source_url: Mapped[str] = mapped_column(String(500), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    image_paths: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    image_hashes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    raw_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extract_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    model_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PipelineChange(Base):
    __tablename__ = "pipeline_change"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("pipeline_asset.id", ondelete="SET NULL"), nullable=True, index=True
    )
    field: Mapped[str] = mapped_column(String(50), nullable=False)
    old_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    change_kind: Mapped[str] = mapped_column(String(20), nullable=False, default="updated")
    # crawl=抓取对账；manual=人工校对
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="crawl", index=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    snapshot_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("pipeline_page_snapshot.id", ondelete="SET NULL"), nullable=True
    )
    prev_snapshot_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("pipeline_page_snapshot.id", ondelete="SET NULL"), nullable=True
    )
    notified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    drug_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    company_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    indication: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)


class PipelineDeal(Base):
    """交易/合作：来自新闻溯源（非视觉抽取）。"""

    __tablename__ = "pipeline_deal"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    news_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("news.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("companies.id"), nullable=True, index=True
    )
    drug_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("drugs.id"), nullable=True, index=True
    )
    asset_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("pipeline_asset.id", ondelete="SET NULL"), nullable=True
    )
    deal_type: Mapped[str] = mapped_column(String(50), nullable=False, default="collaboration")
    counterparty: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    announced_on: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    raw: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    dedupe_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class PipelineCrawlConfig(Base):
    """管线采集单行配置，与新闻 crawl_config 平行。"""

    __tablename__ = "pipeline_crawl_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    running: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    schedule_mode: Mapped[str] = mapped_column(String(20), default="manual", nullable=False)
    interval_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    daily_time: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    weekly_day: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    crawler_keys: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    armed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
