"""事件簇表 ORM。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional


from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.models.base import Base


class Event(Base):
    __tablename__ = "event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    centroid_embedding = mapped_column(Vector(), nullable=True)
    news_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    representative_news_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    products: Mapped[Optional[list]] = mapped_column(JSONB, nullable=False, default=list)
    orgs: Mapped[Optional[list]] = mapped_column(JSONB, nullable=False, default=list)
    story_types: Mapped[Optional[list]] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    ci_risk_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    burst_prob: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    score_components: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    forecast_report: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    forecast_generated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    forecast_evidence_meta: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSONB, nullable=True
    )
    forecast_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="idle"
    )
    forecast_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    news_items: Mapped[List["News"]] = relationship(  # noqa: F821
        "News",
        back_populates="event",
        foreign_keys="News.event_id",
    )
