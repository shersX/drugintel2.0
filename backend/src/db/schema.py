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
        conn.execute(text("ALTER TABLE news ADD COLUMN IF NOT EXISTS content_html TEXT"))
        conn.execute(text("ALTER TABLE crawl_run ADD COLUMN IF NOT EXISTS progress JSONB"))
        conn.execute(
            text(
                "ALTER TABLE news ADD COLUMN IF NOT EXISTS process_status VARCHAR(20) "
                "NOT NULL DEFAULT 'ready'"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_news_process_status ON news (process_status)"
            )
        )
    _backfill_news_process_status(engine)
    _ensure_llm_profile_columns(engine)
    _ensure_pipeline_schema(engine)
    _ensure_company_name_zh_column(engine)
    _ensure_crawl_config_columns(engine)
    _encrypt_llm_profile_keys()
    _ensure_default_vector_dim(engine)
    _fix_naive_publish_time_as_shanghai(engine)
    _split_html_content_into_content_html(engine)
    _ensure_search_tsv(engine)
    try:
        create_vector_indexes(engine)
    except RuntimeError as exc:
        logger.warning("%s（表为空时部分环境可稍后重试）", exc)
    _seed_crawl_config()
    _seed_pipeline_crawl_config()
    _seed_simcere_company()
    _seed_company_name_zh()
    _seed_rag_and_crawler_settings()
    _seed_smtp_config()
    _seed_filter_keywords()
    _seed_pipeline_demo_assets()
    from backend.src.auth.service import bind_watchlist_owners, ensure_first_admin

    ensure_first_admin()
    bind_watchlist_owners()
    logger.info("数据库结构已就绪")


def _ensure_llm_profile_columns(engine) -> None:
    """已有库补上嵌入、重排、视觉各自的地址和密钥，并从原来的共用字段回填。"""
    with engine.begin() as conn:
        if conn.execute(text("SELECT to_regclass('public.llm_profile')")).scalar() is None:
            return
        for name, ddl in (
            ("embedding_base_url", "VARCHAR(300)"),
            ("embedding_api_key", "TEXT"),
            ("embedding_dim", "INTEGER"),
            ("reranker_base_url", "VARCHAR(300)"),
            ("reranker_api_key", "TEXT"),
            ("vision_base_url", "VARCHAR(300)"),
            ("vision_api_key", "TEXT"),
            ("vision_model", "VARCHAR(200)"),
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
        conn.execute(
            text(
                """
                UPDATE llm_profile
                SET vision_base_url = base_url
                WHERE vision_base_url IS NULL OR btrim(vision_base_url) = ''
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE llm_profile
                SET vision_api_key = api_key
                WHERE vision_api_key IS NULL OR btrim(vision_api_key) = ''
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE llm_profile
                SET vision_model = ''
                WHERE vision_model IS NULL
                """
            )
        )
        for name, default in (
            ("embedding_base_url", "''"),
            ("embedding_api_key", "''"),
            ("reranker_base_url", "''"),
            ("reranker_api_key", "''"),
            ("vision_base_url", "''"),
            ("vision_api_key", "''"),
            ("vision_model", "''"),
        ):
            conn.execute(text(f"ALTER TABLE llm_profile ALTER COLUMN {name} SET DEFAULT {default}"))
            conn.execute(text(f"ALTER TABLE llm_profile ALTER COLUMN {name} SET NOT NULL"))
        conn.execute(text("ALTER TABLE llm_profile ALTER COLUMN embedding_dim SET DEFAULT 1024"))
        conn.execute(text("ALTER TABLE llm_profile ALTER COLUMN embedding_dim SET NOT NULL"))


def _ensure_crawl_config_columns(engine) -> None:
    with engine.begin() as conn:
        if conn.execute(text("SELECT to_regclass('public.crawl_config')")).scalar() is None:
            return
        conn.execute(
            text("ALTER TABLE crawl_config ADD COLUMN IF NOT EXISTS interval_minutes INTEGER")
        )


def _encrypt_llm_profile_keys() -> None:
    """把仍是明文的模型密钥改成密文。已经加密的行跳过。"""
    from backend.src.core.keystore import is_sealed, seal
    from backend.src.models.llm_profile import LlmProfile

    with session_scope() as session:
        if session.execute(text("SELECT to_regclass('public.llm_profile')")).scalar() is None:
            return
        rows = list(session.scalars(select(LlmProfile)).all())
        changed = 0
        for row in rows:
            for attr in (
                "api_key",
                "embedding_api_key",
                "reranker_api_key",
                "vision_api_key",
            ):
                value = getattr(row, attr) or ""
                if value and not is_sealed(value):
                    setattr(row, attr, seal(value))
                    changed += 1
        if changed:
            logger.info("已加密 %s 个模型密钥字段", changed)


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


def _fix_naive_publish_time_as_shanghai(engine) -> None:
    """历史数据曾把北京墙钟当成 UTC 写入 timestamptz，启动时一次性纠偏。"""
    with engine.begin() as conn:
        if conn.execute(text("SELECT to_regclass('public.news')")).scalar() is None:
            return
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS schema_patch (
                    name TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
        )
        existed = conn.execute(
            text("SELECT 1 FROM schema_patch WHERE name = :name"),
            {"name": "news_publish_time_shanghai_v1"},
        ).first()
        if existed is not None:
            return
        result = conn.execute(
            text(
                """
                UPDATE news
                SET publish_time = (publish_time AT TIME ZONE 'UTC')
                                    AT TIME ZONE 'Asia/Shanghai'
                WHERE publish_time IS NOT NULL
                """
            )
        )
        conn.execute(
            text("INSERT INTO schema_patch(name) VALUES (:name)"),
            {"name": "news_publish_time_shanghai_v1"},
        )
        logger.info("已纠偏新闻发布时间时区 %s 条", result.rowcount)


def _split_html_content_into_content_html(engine) -> None:
    """上次误把消毒 HTML 写入 content 的行，拆到 content_html 并把 content 还原为纯文本。"""
    from backend.src.crawlers.scrapling_support import html_to_text, looks_like_html
    from backend.src.models.news import News

    with engine.begin() as conn:
        if conn.execute(text("SELECT to_regclass('public.news')")).scalar() is None:
            return
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS schema_patch (
                    name TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
        )
        existed = conn.execute(
            text("SELECT 1 FROM schema_patch WHERE name = :name"),
            {"name": "news_content_html_split_v1"},
        ).first()
        if existed is not None:
            return

    changed = 0
    with session_scope() as session:
        rows = list(
            session.scalars(
                select(News).where(
                    News.content.is_not(None),
                    News.content != "",
                )
            ).all()
        )
        for row in rows:
            raw = row.content or ""
            if not looks_like_html(raw):
                continue
            if not (row.content_html or "").strip():
                row.content_html = raw
            row.content = html_to_text(raw)
            changed += 1
        session.flush()

    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO schema_patch(name) VALUES (:name) ON CONFLICT DO NOTHING"),
            {"name": "news_content_html_split_v1"},
        )
    logger.info("已拆分 content→content_html %s 条", changed)


def _backfill_news_process_status(engine) -> None:
    """存量：有向量→ready；有正文无向量→raw（可补跑）。只在首次补丁时跑。"""
    with engine.begin() as conn:
        if conn.execute(text("SELECT to_regclass('public.news')")).scalar() is None:
            return
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS schema_patch (
                    name TEXT PRIMARY KEY
                )
                """
            )
        )
        done = conn.execute(
            text("SELECT 1 FROM schema_patch WHERE name = 'news_process_status_v1'")
        ).scalar()
        if done:
            return
        conn.execute(
            text(
                """
                UPDATE news
                SET process_status = 'ready'
                WHERE embedding IS NOT NULL
                  AND (process_status IS NULL OR process_status = 'ready' OR process_status = '')
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE news
                SET process_status = 'raw'
                WHERE embedding IS NULL
                  AND content IS NOT NULL
                  AND btrim(content) <> ''
                  AND process_status = 'ready'
                """
            )
        )
        conn.execute(
            text("INSERT INTO schema_patch(name) VALUES ('news_process_status_v1') ON CONFLICT DO NOTHING")
        )
    logger.info("已回填 news.process_status")


def _ensure_search_tsv(engine) -> None:
    """为 BM25 召回增加 search_tsv + GIN，并回填空值行。"""
    with engine.begin() as conn:
        if conn.execute(text("SELECT to_regclass('public.news')")).scalar() is None:
            return
        conn.execute(text("ALTER TABLE news ADD COLUMN IF NOT EXISTS search_tsv tsvector"))
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_news_search_tsv ON news USING GIN (search_tsv)"
            )
        )
    try:
        with session_scope() as session:
            from backend.src.search.bm25 import invalidate_bm25_stats
            from backend.src.search.tsv import backfill_search_tsv

            n = backfill_search_tsv(session)
            if n:
                invalidate_bm25_stats()
                logger.info("search_tsv 回填完成 %s 条", n)
    except Exception as exc:
        logger.warning("search_tsv 回填跳过: %s", exc)


def _ensure_pipeline_schema(engine) -> None:
    """管线表可推倒重建：补列；旧版 pipeline_deal（无 news_id）直接 DROP 后由 create_all 重建。"""
    from backend.src.models.pipeline import PipelineDeal

    with engine.begin() as conn:
        if conn.execute(text("SELECT to_regclass('public.pipeline_asset')")).scalar() is not None:
            for name, ddl in (
                ("target", "VARCHAR(200)"),
                ("modality", "VARCHAR(40) NOT NULL DEFAULT 'unknown'"),
                ("review_status", "VARCHAR(20) NOT NULL DEFAULT 'auto'"),
                ("manual_fields", "JSONB NOT NULL DEFAULT '[]'::jsonb"),
                ("reviewed_at", "TIMESTAMPTZ"),
                ("reviewed_by", "INTEGER"),
            ):
                conn.execute(
                    text(f"ALTER TABLE pipeline_asset ADD COLUMN IF NOT EXISTS {name} {ddl}")
                )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_pipeline_asset_target ON pipeline_asset (target)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_pipeline_asset_modality ON pipeline_asset (modality)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_pipeline_asset_review_status "
                    "ON pipeline_asset (review_status)"
                )
            )
        if conn.execute(text("SELECT to_regclass('public.pipeline_change')")).scalar() is not None:
            conn.execute(
                text(
                    "ALTER TABLE pipeline_change ADD COLUMN IF NOT EXISTS "
                    "source VARCHAR(20) NOT NULL DEFAULT 'crawl'"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_pipeline_change_source ON pipeline_change (source)"
                )
            )
        deal_reg = conn.execute(text("SELECT to_regclass('public.pipeline_deal')")).scalar()
        if deal_reg is not None:
            has_news = conn.execute(
                text(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_schema='public' AND table_name='pipeline_deal' "
                    "AND column_name='news_id'"
                )
            ).scalar()
            if has_news is None:
                conn.execute(text("DROP TABLE IF EXISTS pipeline_deal CASCADE"))
                logger.info("已删除旧版 pipeline_deal（无 news_id），将重建")
    # DROP 后补建
    PipelineDeal.__table__.create(bind=engine, checkfirst=True)


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


def _seed_pipeline_crawl_config() -> None:
    from backend.src.models.pipeline import PipelineCrawlConfig

    with session_scope() as session:
        session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _SEED_LOCK + 1})
        existing = session.scalar(select(PipelineCrawlConfig).limit(1))
        if existing is None:
            session.add(
                PipelineCrawlConfig(
                    running=False,
                    schedule_mode="manual",
                    crawler_keys=["simcere_pipeline"],
                    source_url="https://www.simcere.com/kxcx/yggx.aspx",
                )
            )
            logger.info("已写入默认管线采集配置（未启动）")


def _ensure_company_name_zh_column(engine) -> None:
    with engine.begin() as conn:
        if conn.execute(text("SELECT to_regclass('public.companies')")).scalar() is None:
            return
        conn.execute(
            text("ALTER TABLE companies ADD COLUMN IF NOT EXISTS name_zh VARCHAR(200)")
        )


def _seed_simcere_company() -> None:
    from backend.src.models.entities import Company

    with session_scope() as session:
        row = session.scalar(select(Company).where(Company.name == "先声药业"))
        if row is None:
            session.add(Company(name="先声药业", name_en="Simcere", name_zh="先声药业"))
            logger.info("已写入先声药业公司种子")
        else:
            if not (row.name_en or "").strip():
                row.name_en = "Simcere"
            if not (row.name_zh or "").strip():
                row.name_zh = "先声药业"


def _seed_company_name_zh() -> None:
    try:
        from backend.src.pipeline_intel.seed import seed_company_name_zh

        seed_company_name_zh()
    except Exception as exc:
        logger.warning("公司中文名回填跳过: %s", exc)


def _seed_pipeline_demo_assets() -> None:
    try:
        from backend.src.pipeline_intel.seed import seed_pipeline_demo_assets

        seed_pipeline_demo_assets()
    except Exception as exc:
        logger.warning("管线展示种子跳过: %s", exc)


def _seed_rag_and_crawler_settings() -> None:
    try:
        with session_scope() as session:
            from backend.src.crawlers.settings_store import seed_crawler_settings
            from backend.src.rag.settings import get_or_create_rag_config

            get_or_create_rag_config(session)
            seed_crawler_settings(session)
    except Exception as exc:
        logger.warning("初始化 rag/crawler 配置跳过: %s", exc)


def _seed_smtp_config() -> None:
    try:
        with session_scope() as session:
            from backend.src.alerts.smtp_settings import get_or_create_smtp_config

            get_or_create_smtp_config(session)
    except Exception as exc:
        logger.warning("初始化 smtp_config 跳过: %s", exc)


def _seed_filter_keywords() -> None:
    try:
        with session_scope() as session:
            from backend.src.processors.keyword_store import import_keywords_from_yaml

            n = import_keywords_from_yaml(session, only_if_empty=True)
            if n:
                logger.info("过滤关键词首次导入 %s 条", n)
    except Exception as exc:
        logger.warning("过滤关键词导入跳过: %s", exc)
