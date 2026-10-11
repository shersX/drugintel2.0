"""前端可保存的多套 OpenAI 兼容模型接口。"""

from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.src.models.base import Base


class LlmProfile(Base):
    __tablename__ = "llm_profile"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    api_key: Mapped[str] = mapped_column(Text, nullable=False, default="")
    base_url: Mapped[str] = mapped_column(String(300), nullable=False)
    chat_model: Mapped[str] = mapped_column(String(200), nullable=False)
    embedding_api_key: Mapped[str] = mapped_column(Text, nullable=False, default="")
    embedding_base_url: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    embedding_model: Mapped[str] = mapped_column(String(200), nullable=False)
    embedding_dim: Mapped[int] = mapped_column(Integer, nullable=False, default=1024)
    reranker_api_key: Mapped[str] = mapped_column(Text, nullable=False, default="")
    reranker_base_url: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    reranker_model: Mapped[str] = mapped_column(String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
