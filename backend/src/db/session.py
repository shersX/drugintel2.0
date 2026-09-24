"""数据库引擎与会话。"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator, Iterator

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
