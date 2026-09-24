"""公司 / 药物 / Watchlist / 爬虫任务等辅助表。"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.src.models.base import Base, TimestampMixin


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    name_en: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)


class Drug(Base):
    __tablename__ = "drugs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    generic_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    mechanism_of_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    indication: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class DrugDevelopmentEvent(Base):
    __tablename__ = "drug_development_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    drug_id: Mapped[int] = mapped_column(Integer, ForeignKey("drugs.id"), nullable=False)
    company_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("companies.id"), nullable=True
    )
    development_stage: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    indication: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    update_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)


class Watchlist(Base, TimestampMixin):
    __tablename__ = "watchlist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class CrawlerTask(Base):
    __tablename__ = "crawler_task"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    crawler_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    start_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    total_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    success_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
