"""环境变量与运行时配置。"""
import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class LLMEnvConfig:
    api_key: str
    base_url: str
    model: str
    timeout_sec: float
    max_retries: int

    @staticmethod
    def load() -> "LLMEnvConfig":
        return LLMEnvConfig(
            api_key=os.getenv("SILICONFLOW_API_KEY", "").strip(),
            base_url=os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
            .strip()
            .rstrip("/"),
            model=os.getenv("SILICONFLOW_MODEL", "deepseek-ai/DeepSeek-V4-Flash"),
            timeout_sec=float(os.getenv("LLM_TIMEOUT_SEC", "90")),
            max_retries=int(os.getenv("LLM_MAX_RETRIES", "3")),
        )


@dataclass(frozen=True)
class EmbeddingEnvConfig:
    model: str
    max_concurrency: int
    reranker_model: str

    @staticmethod
    def load() -> "EmbeddingEnvConfig":
        return EmbeddingEnvConfig(
            model=os.getenv("SILICONFLOW_EMBEDDING_MODEL", "BAAI/bge-m3").strip(),
            max_concurrency=int(os.getenv("EMBEDDING_MAX_CONCURRENCY", "5")),
            reranker_model=os.getenv(
                "SILICONFLOW_RERANKER_MODEL", "BAAI/bge-reranker-v2-m3"
            ).strip(),
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
