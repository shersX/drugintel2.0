"""幂等建表：扩展、表、向量索引，以及默认停止的采集配置。"""

from __future__ import annotations

from sqlalchemy import select, text

from backend.src.core.logger import get_logger
from backend.src.db.session import (
    create_vector_indexes,
    enable_pgvector,
    get_engine,
    rebuild_vector_columns,
    session_scope,
    vector_column_dim,
)
from backend.src.models import Base
from backend.src.models.crawl import CrawlConfig

logger = get_logger("db.schema")

_SEED_LOCK = 84123001


def ensure_schema() -> None:
    """启动时调用。重复执行不会改已有数据，也不会把采集标成运行中。"""
    engine = get_engine()
    logger.info("连接数据库: %s", engine.url.render_as_string(hide_password=True))
    enable_pgvector(engine)
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE crawler_task ADD COLUMN IF NOT EXISTS log_text TEXT"))
    _ensure_llm_profile_columns(engine)
    _ensure_default_vector_dim(engine)
    try:
        create_vector_indexes(engine)
    except RuntimeError as exc:
        logger.warning("%s（表为空时部分环境可稍后重试）", exc)
    _seed_crawl_config()
    logger.info("数据库结构已就绪")


def _ensure_llm_profile_columns(engine) -> None:
    """已有库补上嵌入、重排各自的地址和密钥，并从原来的共用字段回填。"""
    with engine.begin() as conn:
        if conn.execute(text("SELECT to_regclass('public.llm_profile')")).scalar() is None:
            return
        for name, ddl in (
            ("embedding_base_url", "VARCHAR(300)"),
            ("embedding_api_key", "TEXT"),
            ("embedding_dim", "INTEGER"),
            ("reranker_base_url", "VARCHAR(300)"),
            ("reranker_api_key", "TEXT"),
        ):
            conn.execute(text(f"ALTER TABLE llm_profile ADD COLUMN IF NOT EXISTS {name} {ddl}"))
        conn.execute(
            text(
                """
                UPDATE llm_profile
                SET embedding_base_url = base_url
                WHERE embedding_base_url IS NULL OR btrim(embedding_base_url) = ''
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE llm_profile
                SET embedding_api_key = api_key
                WHERE embedding_api_key IS NULL OR btrim(embedding_api_key) = ''
                """
            )
        )
        conn.execute(text("UPDATE llm_profile SET embedding_dim = 1024 WHERE embedding_dim IS NULL"))
        conn.execute(
            text(
                """
                UPDATE llm_profile
                SET reranker_base_url = base_url
                WHERE reranker_base_url IS NULL OR btrim(reranker_base_url) = ''
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE llm_profile
                SET reranker_api_key = api_key
                WHERE reranker_api_key IS NULL OR btrim(reranker_api_key) = ''
                """
            )
        )
        for name, default in (
            ("embedding_base_url", "''"),
            ("embedding_api_key", "''"),
            ("reranker_base_url", "''"),
            ("reranker_api_key", "''"),
        ):
            conn.execute(text(f"ALTER TABLE llm_profile ALTER COLUMN {name} SET DEFAULT {default}"))
            conn.execute(text(f"ALTER TABLE llm_profile ALTER COLUMN {name} SET NOT NULL"))
        conn.execute(text("ALTER TABLE llm_profile ALTER COLUMN embedding_dim SET DEFAULT 1024"))
        conn.execute(text("ALTER TABLE llm_profile ALTER COLUMN embedding_dim SET NOT NULL"))


def _ensure_default_vector_dim(engine, dim: int = 1024) -> None:
    """新库的向量列还没限定宽度时，设成 1024。已经有宽度的列保持不动。"""
    with engine.begin() as conn:
        if vector_column_dim(conn) is not None:
            return
        has_news = conn.execute(
            text("SELECT 1 FROM news WHERE embedding IS NOT NULL LIMIT 1")
        ).first()
        has_event = conn.execute(
            text("SELECT 1 FROM event WHERE centroid_embedding IS NOT NULL LIMIT 1")
        ).first()
        if has_news or has_event:
            return
        rebuild_vector_columns(dim, conn)


def _seed_crawl_config() -> None:
    with session_scope() as session:
        session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _SEED_LOCK})
        existing = session.scalar(select(CrawlConfig).limit(1))
        if existing is None:
            session.add(
                CrawlConfig(
                    running=False,
                    schedule_mode="hourly",
                    daily_time=None,
                    crawler_keys=[],
                )
            )
            logger.info("已写入默认采集配置（未启动）")
