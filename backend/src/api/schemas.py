"""Pydantic 请求/响应模型。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    query: str
    session_id: Optional[str] = None
    conversation_id: Optional[str] = None
    top_k: Optional[int] = None  # 已废弃：服务端以管理员 rag_config 为准
    news_id: Optional[int] = None  # 页面上下文：强制注入该新闻为资料首位


class RagConfigUpdate(BaseModel):
    top_k: int = Field(10, ge=1, le=50)
    min_relevance_score: float = Field(0.25, ge=0.0, le=1.0)


class CrawlerSettingUpdate(BaseModel):
    enabled: bool = True
    page_count: int = Field(1, ge=1, le=50)
    concurrency: int = Field(2, ge=1, le=20)
    fetch_details: bool = True


class FilterKeywordCreate(BaseModel):
    category: str
    canonical: str = Field(..., min_length=1, max_length=200)
    aliases: List[str] = []


class FilterKeywordUpdate(BaseModel):
    category: Optional[str] = None
    canonical: Optional[str] = Field(None, min_length=1, max_length=200)
    aliases: Optional[List[str]] = None


class KeywordReimportRequest(BaseModel):
    confirm_overwrite: bool = False


class ConversationRename(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)


class WatchlistCreate(BaseModel):
    user_id: int = 1
    entity_type: str = Field(..., description="drug/company/keyword")
    entity_name: str
    email: Optional[str] = None
    enabled: bool = True


class SmtpConfigUpdate(BaseModel):
    host: str = ""
    port: int = Field(587, ge=1, le=65535)
    user: str = ""
    password: Optional[str] = None  # 留空不改
    from_addr: str = ""
    use_tls: bool = True
    enabled: bool = True


class SmtpTestRequest(BaseModel):
    to_email: str = Field(..., min_length=3, max_length=200)


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


class LoginRequest(BaseModel):
    email: str
    password: str


class ProfileUpdate(BaseModel):
    display_name: Optional[str] = None
    old_password: Optional[str] = None
    new_password: Optional[str] = None


class UserCreate(BaseModel):
    email: str
    display_name: str = ""
    password: str
    role: str = "user"
    daily_chat_limit: int = 50


class PasswordReset(BaseModel):
    password: str


class ChatLimitUpdate(BaseModel):
    daily_chat_limit: int
