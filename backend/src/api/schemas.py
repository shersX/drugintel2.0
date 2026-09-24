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
