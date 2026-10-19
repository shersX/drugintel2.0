"""RAG 运行时配置（单行）。"""

from __future__ import annotations

from sqlalchemy import Float, Integer
from sqlalchemy.orm import Mapped, mapped_column

from backend.src.models.base import Base


class RagConfig(Base):
    __tablename__ = "rag_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    top_k: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    min_relevance_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.25)
