"""新闻表 ORM（raw_data）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.models.base import Base, TimestampMixin


class News(Base, TimestampMixin):
    __tablename__ = "news"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    abstract: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    publish_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    detail_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, unique=True)
    crawler: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    matched_keywords: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    embedding = mapped_column(Vector(1024), nullable=True)
    is_representative: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    event_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("event.id", ondelete="SET NULL"), nullable=True, index=True
    )

    event = relationship("Event", back_populates="news_items", foreign_keys=[event_id])
