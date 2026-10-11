"""数据库引擎与会话。"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from backend.src.core.config import DatabaseEnvConfig

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine(url: str | None = None) -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        db_url = url or DatabaseEnvConfig.load().url
        _engine = create_engine(db_url, pool_pre_ping=True)
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    if _SessionLocal is None:
        get_engine()
    assert _SessionLocal is not None
    return _SessionLocal


@contextmanager
def session_scope() -> Iterator[Session]:
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def enable_pgvector(engine: Engine | None = None) -> None:
    eng = engine or get_engine()
    with eng.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))


def vector_column_dim(connection) -> Optional[int]:
    """news.embedding 的列宽。未限定维度时返回 None。"""
    typmod = connection.execute(
        text(
            """
            SELECT a.atttypmod
            FROM pg_attribute a
            JOIN pg_class c ON c.oid = a.attrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public'
              AND c.relname = 'news'
              AND a.attname = 'embedding'
              AND a.attnum > 0
              AND NOT a.attisdropped
            """
        )
    ).scalar()
    if typmod is None or int(typmod) < 1:
        return None
    return int(typmod)


def rebuild_vector_columns(dim: int, connection) -> None:
    """清空已有向量，把新闻向量和事件中心改成给定维度，并重建 HNSW 索引。"""
    width = int(dim)
    connection.execute(text("DROP INDEX IF EXISTS news_embedding_idx"))
    connection.execute(text("DROP INDEX IF EXISTS event_centroid_idx"))
    connection.execute(text("UPDATE news SET embedding = NULL"))
    connection.execute(text("UPDATE event SET centroid_embedding = NULL"))
    connection.execute(text(f"ALTER TABLE news ALTER COLUMN embedding TYPE vector({width})"))
    connection.execute(
        text(f"ALTER TABLE event ALTER COLUMN centroid_embedding TYPE vector({width})")
    )
    connection.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS news_embedding_idx
            ON news USING hnsw (embedding vector_cosine_ops)
            """
        )
    )
    connection.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS event_centroid_idx
            ON event USING hnsw (centroid_embedding vector_cosine_ops)
            """
        )
    )


def create_vector_indexes(engine: Engine | None = None) -> None:
    """创建 HNSW 向量索引（空表也可建，优于 IVFFlat 对最小行数要求）。"""
    eng = engine or get_engine()
    stmts = [
        """
        CREATE INDEX IF NOT EXISTS news_embedding_idx
        ON news USING hnsw (embedding vector_cosine_ops)
        """,
        """
        CREATE INDEX IF NOT EXISTS event_centroid_idx
        ON event USING hnsw (centroid_embedding vector_cosine_ops)
        """,
    ]
    with eng.begin() as conn:
        for sql in stmts:
            conn.execute(text(sql))
