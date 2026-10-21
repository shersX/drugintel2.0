"""SMTP 运行时配置（单行）。"""

from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.src.models.base import Base


class SmtpConfig(Base):
    __tablename__ = "smtp_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    host: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    port: Mapped[int] = mapped_column(Integer, nullable=False, default=587)
    user: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    password: Mapped[str] = mapped_column(Text, nullable=False, default="")
    from_addr: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    use_tls: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
