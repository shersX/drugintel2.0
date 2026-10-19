"""RAG 配置读写（DB 优先，环境变量回退）。"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.src.core.config import RagEnvConfig
from backend.src.core.logger import get_logger
from backend.src.db.session import session_scope
from backend.src.models.rag_config import RagConfig

logger = get_logger("rag.settings")

DEFAULT_TOP_K = 10
DEFAULT_MIN_SCORE = 0.25


@dataclass(frozen=True)
class RagSettings:
    top_k: int
    min_relevance_score: float


def get_or_create_rag_config(session: Session) -> RagConfig:
    row = session.scalar(select(RagConfig).order_by(RagConfig.id.asc()).limit(1))
    if row is None:
        env = RagEnvConfig.load()
        row = RagConfig(
            top_k=DEFAULT_TOP_K,
            min_relevance_score=float(env.min_relevance_score or DEFAULT_MIN_SCORE),
        )
        session.add(row)
        session.flush()
    return row


def load_rag_settings() -> RagSettings:
    try:
        with session_scope() as session:
            row = get_or_create_rag_config(session)
            top_k = max(1, min(50, int(row.top_k or DEFAULT_TOP_K)))
            score = float(row.min_relevance_score)
            if score < 0:
                score = 0.0
            if score > 1:
                score = 1.0
            return RagSettings(top_k=top_k, min_relevance_score=score)
    except Exception as exc:
        logger.warning("读取 rag_config 失败，回退环境变量: %s", exc)
        env = RagEnvConfig.load()
        return RagSettings(
            top_k=DEFAULT_TOP_K,
            min_relevance_score=float(env.min_relevance_score or DEFAULT_MIN_SCORE),
        )


def update_rag_settings(
    session: Session,
    *,
    top_k: int,
    min_relevance_score: float,
) -> RagConfig:
    row = get_or_create_rag_config(session)
    row.top_k = max(1, min(50, int(top_k)))
    score = float(min_relevance_score)
    row.min_relevance_score = 0.0 if score < 0 else (1.0 if score > 1 else score)
    session.flush()
    return row


def rag_config_to_dict(row: RagConfig) -> dict:
    return {
        "top_k": int(row.top_k),
        "min_relevance_score": float(row.min_relevance_score),
    }
