"""实体词典与用户关注列表。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.src.models.base import Base


class EntityLexicon(Base):
    __tablename__ = "entity_lexicon"
    __table_args__ = (UniqueConstraint("entity_type", "canonical", name="uq_entity_type_canonical"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    canonical: Mapped[str] = mapped_column(String(200), nullable=False)
    aliases: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="llm")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", index=True)
    merged_into_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("entity_lexicon.id", ondelete="SET NULL"), nullable=True
    )
    seen_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class EntityWatchlist(Base):
    __tablename__ = "entity_watchlist"
    __table_args__ = (UniqueConstraint("user_id", "entity_id", name="uq_entity_watch_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("entity_lexicon.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
