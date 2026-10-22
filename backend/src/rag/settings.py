"""RAG 配置读写（DB 优先，环境变量回退）。"""

from __future__ import annotations

import os
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
DEFAULT_VECTOR_WEIGHT = 0.6
DEFAULT_RERANK_MULT = 2
DEFAULT_HISTORY_TURNS = 12
DEFAULT_TEMPERATURE = 0.3


@dataclass(frozen=True)
class RagSettings:
    top_k: int
    min_relevance_score: float
    hybrid_vector_weight: float
    rerank_pool_multiplier: int
    history_turns: int
    temperature: float

    @property
    def hybrid_bm25_weight(self) -> float:
        return max(0.0, 1.0 - self.hybrid_vector_weight)


def _clamp_top_k(v: int) -> int:
    return max(1, min(50, int(v)))


def _clamp_score(v: float) -> float:
    score = float(v)
    if score < 0:
        return 0.0
    if score > 1:
        return 1.0
    return score


def _clamp_weight(v: float) -> float:
    return _clamp_score(v)


def _clamp_mult(v: int) -> int:
    return max(1, min(5, int(v)))


def _clamp_history(v: int) -> int:
    return max(1, min(40, int(v)))


def _clamp_temperature(v: float) -> float:
    t = float(v)
    if t < 0:
        return 0.0
    if t > 2:
        return 2.0
    return t


def _env_vector_weight() -> float:
    raw = os.getenv("HYBRID_VECTOR_WEIGHT")
    if raw is None or str(raw).strip() == "":
        return DEFAULT_VECTOR_WEIGHT
    try:
        return _clamp_weight(float(raw))
    except ValueError:
        return DEFAULT_VECTOR_WEIGHT


def get_or_create_rag_config(session: Session) -> RagConfig:
    row = session.scalar(select(RagConfig).order_by(RagConfig.id.asc()).limit(1))
    if row is None:
        env = RagEnvConfig.load()
        row = RagConfig(
            top_k=DEFAULT_TOP_K,
            min_relevance_score=float(env.min_relevance_score or DEFAULT_MIN_SCORE),
            hybrid_vector_weight=_env_vector_weight(),
            rerank_pool_multiplier=DEFAULT_RERANK_MULT,
            history_turns=DEFAULT_HISTORY_TURNS,
            temperature=DEFAULT_TEMPERATURE,
        )
        session.add(row)
        session.flush()
        return row
    # 旧行缺列时由 ORM/迁移补默认；此处再兜底一次
    if getattr(row, "hybrid_vector_weight", None) is None:
        row.hybrid_vector_weight = _env_vector_weight()
    if getattr(row, "rerank_pool_multiplier", None) is None:
        row.rerank_pool_multiplier = DEFAULT_RERANK_MULT
    if getattr(row, "history_turns", None) is None:
        row.history_turns = DEFAULT_HISTORY_TURNS
    if getattr(row, "temperature", None) is None:
        row.temperature = DEFAULT_TEMPERATURE
    return row


def load_rag_settings() -> RagSettings:
    try:
        with session_scope() as session:
            row = get_or_create_rag_config(session)
            return RagSettings(
                top_k=_clamp_top_k(row.top_k or DEFAULT_TOP_K),
                min_relevance_score=_clamp_score(
                    row.min_relevance_score
                    if row.min_relevance_score is not None
                    else DEFAULT_MIN_SCORE
                ),
                hybrid_vector_weight=_clamp_weight(
                    row.hybrid_vector_weight
                    if row.hybrid_vector_weight is not None
                    else _env_vector_weight()
                ),
                rerank_pool_multiplier=_clamp_mult(
                    row.rerank_pool_multiplier or DEFAULT_RERANK_MULT
                ),
                history_turns=_clamp_history(row.history_turns or DEFAULT_HISTORY_TURNS),
                temperature=_clamp_temperature(
                    row.temperature if row.temperature is not None else DEFAULT_TEMPERATURE
                ),
            )
    except Exception as exc:
        logger.warning("读取 rag_config 失败，回退默认/环境变量: %s", exc)
        env = RagEnvConfig.load()
        return RagSettings(
            top_k=DEFAULT_TOP_K,
            min_relevance_score=_clamp_score(env.min_relevance_score or DEFAULT_MIN_SCORE),
            hybrid_vector_weight=_env_vector_weight(),
            rerank_pool_multiplier=DEFAULT_RERANK_MULT,
            history_turns=DEFAULT_HISTORY_TURNS,
            temperature=DEFAULT_TEMPERATURE,
        )


def update_rag_settings(
    session: Session,
    *,
    top_k: int,
    min_relevance_score: float,
    hybrid_vector_weight: float = DEFAULT_VECTOR_WEIGHT,
    rerank_pool_multiplier: int = DEFAULT_RERANK_MULT,
    history_turns: int = DEFAULT_HISTORY_TURNS,
    temperature: float = DEFAULT_TEMPERATURE,
) -> RagConfig:
    row = get_or_create_rag_config(session)
    row.top_k = _clamp_top_k(top_k)
    row.min_relevance_score = _clamp_score(min_relevance_score)
    row.hybrid_vector_weight = _clamp_weight(hybrid_vector_weight)
    row.rerank_pool_multiplier = _clamp_mult(rerank_pool_multiplier)
    row.history_turns = _clamp_history(history_turns)
    row.temperature = _clamp_temperature(temperature)
    session.flush()
    return row


def rag_config_to_dict(row: RagConfig) -> dict:
    vw = _clamp_weight(
        row.hybrid_vector_weight
        if getattr(row, "hybrid_vector_weight", None) is not None
        else DEFAULT_VECTOR_WEIGHT
    )
    return {
        "top_k": int(row.top_k),
        "min_relevance_score": float(row.min_relevance_score),
        "hybrid_vector_weight": vw,
        "hybrid_bm25_weight": round(1.0 - vw, 4),
        "rerank_pool_multiplier": int(
            getattr(row, "rerank_pool_multiplier", None) or DEFAULT_RERANK_MULT
        ),
        "history_turns": int(getattr(row, "history_turns", None) or DEFAULT_HISTORY_TURNS),
        "temperature": float(
            row.temperature
            if getattr(row, "temperature", None) is not None
            else DEFAULT_TEMPERATURE
        ),
    }
