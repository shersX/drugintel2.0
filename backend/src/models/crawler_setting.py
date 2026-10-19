"""爬虫注册表运行参数（按 crawler_key 一行）。"""

from __future__ import annotations

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.src.models.base import Base


class CrawlerSetting(Base):
    __tablename__ = "crawler_setting"

    crawler_key: Mapped[str] = mapped_column(String(50), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    concurrency: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    fetch_details: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
