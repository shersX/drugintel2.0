"""Pydantic 请求/响应模型。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    query: str
    session_id: Optional[str] = None
    top_k: int = 5


class WatchlistCreate(BaseModel):
    user_id: int = 1
    entity_type: str = Field(..., description="drug/company/keyword")
    entity_name: str
    email: Optional[str] = None
    enabled: bool = True


class ReportExportRequest(BaseModel):
    question: str
    answer: str
    sources: List[Dict[str, Any]] = []
    fmt: str = "pdf"


class CrawlStartRequest(BaseModel):
    schedule_mode: str
    daily_time: Optional[str] = None
    crawler_keys: List[str] = []


class LlmProfileWrite(BaseModel):
    name: str
    api_key: Optional[str] = None
    base_url: str
    chat_model: str
    embedding_api_key: Optional[str] = None
    embedding_base_url: str
    embedding_model: str
    embedding_dim: int = 1024
    reranker_api_key: Optional[str] = None
    reranker_base_url: str
    reranker_model: str
    rebuild: bool = False


class LlmProfileTest(BaseModel):
    base_url: str
    api_key: Optional[str] = None
    profile_id: Optional[int] = None
    slot: str = "chat"
