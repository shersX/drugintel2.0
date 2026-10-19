"""环境变量与运行时配置。启用中的 llm_profile 优先于环境变量。"""
import os
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Optional

from dotenv import load_dotenv

from backend.src.core.keystore import open_secret
from backend.src.core.logger import get_logger

load_dotenv()

logger = get_logger("core.config")


def _env_text(name: str, fallback: str = "") -> str:
    value = os.getenv(name, "").strip()
    return value or fallback


def _active_llm_profile() -> Optional[SimpleNamespace]:
    """复制字段后离开会话，避免调用方拿到过期 ORM 对象。"""
    try:
        from sqlalchemy import select

        from backend.src.db.session import session_scope
        from backend.src.models.llm_profile import LlmProfile

        with session_scope() as session:
            row = session.scalar(
                select(LlmProfile).where(LlmProfile.is_active.is_(True)).limit(1)
            )
            if row is None:
                return None
            return SimpleNamespace(
                api_key=open_secret(row.api_key),
                base_url=(row.base_url or "").strip().rstrip("/"),
                chat_model=(row.chat_model or "").strip(),
                embedding_api_key=open_secret(row.embedding_api_key),
                embedding_base_url=(row.embedding_base_url or "").strip().rstrip("/"),
                embedding_model=(row.embedding_model or "").strip(),
                embedding_dim=int(row.embedding_dim or 0),
                reranker_api_key=open_secret(row.reranker_api_key),
                reranker_base_url=(row.reranker_base_url or "").strip().rstrip("/"),
                reranker_model=(row.reranker_model or "").strip(),
            )
    except Exception as exc:
        logger.warning("读取启用中的模型配置失败，改用环境变量: %s", exc)
        return None


@dataclass(frozen=True)
class LLMEnvConfig:
    api_key: str
    base_url: str
    model: str
    timeout_sec: float
    max_retries: int

    @staticmethod
    def _from_env() -> "LLMEnvConfig":
        return LLMEnvConfig(
            api_key=os.getenv("SILICONFLOW_API_KEY", "").strip(),
            base_url=os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
            .strip()
            .rstrip("/"),
            model=os.getenv("SILICONFLOW_MODEL", "deepseek-ai/DeepSeek-V4-Flash"),
            timeout_sec=float(os.getenv("LLM_TIMEOUT_SEC", "90")),
            max_retries=int(os.getenv("LLM_MAX_RETRIES", "3")),
        )

    @staticmethod
    def load() -> "LLMEnvConfig":
        env = LLMEnvConfig._from_env()
        row = _active_llm_profile()
        if row is None:
            return env
        return LLMEnvConfig(
            api_key=row.api_key,
            base_url=row.base_url or env.base_url,
            model=row.chat_model or env.model,
            timeout_sec=env.timeout_sec,
            max_retries=env.max_retries,
        )


@dataclass(frozen=True)
class EmbeddingEnvConfig:
    api_key: str
    base_url: str
    model: str
    dim: int
    max_concurrency: int
    reranker_api_key: str
    reranker_base_url: str
    reranker_model: str

    @staticmethod
    def _from_env() -> "EmbeddingEnvConfig":
        chat_key = os.getenv("SILICONFLOW_API_KEY", "").strip()
        chat_url = (
            os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
            .strip()
            .rstrip("/")
        )
        return EmbeddingEnvConfig(
            api_key=_env_text("SILICONFLOW_EMBEDDING_API_KEY", chat_key),
            base_url=_env_text("SILICONFLOW_EMBEDDING_BASE_URL", chat_url).rstrip("/"),
            model=os.getenv("SILICONFLOW_EMBEDDING_MODEL", "BAAI/bge-m3").strip(),
            dim=int(os.getenv("SILICONFLOW_EMBEDDING_DIM", "1024")),
            max_concurrency=int(os.getenv("EMBEDDING_MAX_CONCURRENCY", "5")),
            reranker_api_key=_env_text("SILICONFLOW_RERANKER_API_KEY", chat_key),
            reranker_base_url=_env_text("SILICONFLOW_RERANKER_BASE_URL", chat_url).rstrip("/"),
            reranker_model=os.getenv(
                "SILICONFLOW_RERANKER_MODEL", "BAAI/bge-reranker-v2-m3"
            ).strip(),
        )

    @staticmethod
    def load() -> "EmbeddingEnvConfig":
        env = EmbeddingEnvConfig._from_env()
        row = _active_llm_profile()
        if row is None:
            return env
        return EmbeddingEnvConfig(
            api_key=row.embedding_api_key or env.api_key,
            base_url=row.embedding_base_url or env.base_url,
            model=row.embedding_model or env.model,
            dim=row.embedding_dim or env.dim,
            max_concurrency=env.max_concurrency,
            reranker_api_key=row.reranker_api_key or env.reranker_api_key,
            reranker_base_url=row.reranker_base_url or env.reranker_base_url,
            reranker_model=row.reranker_model or env.reranker_model,
        )


@dataclass(frozen=True)
class RagEnvConfig:
    """RAG 检索后过滤阈值等。"""

    min_relevance_score: float

    @staticmethod
    def load() -> "RagEnvConfig":
        # 作用于重排后的 relevance_score（通常约 0~1）；设为 0 可关闭过滤
        return RagEnvConfig(
            min_relevance_score=float(os.getenv("RAG_MIN_RELEVANCE_SCORE", "0.25")),
        )


@dataclass(frozen=True)
class DatabaseEnvConfig:
    url: str

    @staticmethod
    def load() -> "DatabaseEnvConfig":
        default = "postgresql+psycopg://user:password@127.0.0.1:5433/drugintel"
        return DatabaseEnvConfig(url=os.getenv("DATABASE_URL", default).strip())


@dataclass(frozen=True)
class RedisEnvConfig:
    url: str

    @staticmethod
    def load() -> "RedisEnvConfig":
        return RedisEnvConfig(
            url=os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0").strip()
        )


@dataclass(frozen=True)
class SmtpEnvConfig:
    host: str
    port: int
    user: str
    password: str
    from_addr: str
    use_tls: bool

    @staticmethod
    def load() -> "SmtpEnvConfig":
        return SmtpEnvConfig(
            host=os.getenv("SMTP_HOST", "").strip(),
            port=int(os.getenv("SMTP_PORT", "587")),
            user=os.getenv("SMTP_USER", "").strip(),
            password=os.getenv("SMTP_PASSWORD", "").strip(),
            from_addr=os.getenv("SMTP_FROM", os.getenv("SMTP_USER", "")).strip(),
            use_tls=os.getenv("SMTP_TLS", "1").strip() not in {"0", "false", "False"},
        )
