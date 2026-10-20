"""Okapi BM25 检索：tsvector 召回 + 应用层打分。"""

from __future__ import annotations

import math
import time
from typing import Dict, List, Sequence, Tuple

from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

from backend.src.core.logger import get_logger
from backend.src.models.news import News
from backend.src.search.tokenize import tokenize, tokens_to_tsquery_parts

logger = get_logger("search.bm25")

_K1 = 1.5
_B = 0.75
_STATS_TTL_SEC = 600
_stats_cache: Dict[str, object] = {"ts": 0.0, "N": 0, "avgdl": 1.0, "df": {}}


def _doc_text(news: News) -> str:
    return f"{news.title or ''}\n{news.abstract or ''}\n{news.content or ''}"


def _doc_len(news: News) -> int:
    return max(1, len(tokenize(_doc_text(news))))


def _term_freq(tokens: Sequence[str]) -> Dict[str, int]:
    freq: Dict[str, int] = {}
    for t in tokens:
        freq[t] = freq.get(t, 0) + 1
    return freq


def _load_corpus_stats(session: Session) -> Tuple[int, float, Dict[str, int]]:
    now = time.time()
    if now - float(_stats_cache["ts"]) < _STATS_TTL_SEC and int(_stats_cache["N"]) > 0:
        return (
            int(_stats_cache["N"]),
            float(_stats_cache["avgdl"]),
            dict(_stats_cache["df"]),  # type: ignore[arg-type]
        )

    result = session.execute(
        select(News.title, News.abstract, News.content).limit(5000)
    ).all()
    n = 0
    total_dl = 0
    df: Dict[str, int] = {}
    for title, abstract, content in result:
        tokens = tokenize(f"{title or ''}\n{abstract or ''}\n{content or ''}")
        if not tokens:
            continue
        n += 1
        total_dl += len(tokens)
        for term in set(tokens):
            df[term] = df.get(term, 0) + 1
    avgdl = (total_dl / n) if n else 1.0
    _stats_cache.update({"ts": now, "N": n, "avgdl": avgdl, "df": df})
    return n, avgdl, df


def invalidate_bm25_stats() -> None:
    _stats_cache["ts"] = 0.0


def _idf(n_docs: int, df: int) -> float:
    # Lucene-style IDF，避免负值
    return math.log(1.0 + (n_docs - df + 0.5) / (df + 0.5))


def bm25_score_document(
    query_terms: Sequence[str],
    doc_tokens: Sequence[str],
    *,
    n_docs: int,
    avgdl: float,
    df_map: Dict[str, int],
    k1: float = _K1,
    b: float = _B,
) -> float:
    if not query_terms or not doc_tokens:
        return 0.0
    tf_map = _term_freq(doc_tokens)
    dl = max(1, len(doc_tokens))
    score = 0.0
    for term in query_terms:
        tf = tf_map.get(term, 0)
        if tf <= 0:
            continue
        df = df_map.get(term, 0)
        idf = _idf(max(1, n_docs), df)
        denom = tf + k1 * (1.0 - b + b * dl / max(avgdl, 1e-6))
        score += idf * (tf * (k1 + 1.0)) / denom
    return score


def _tsvector_ready(session: Session) -> bool:
    try:
        row = session.execute(
            text(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'news'
                  AND column_name = 'search_tsv'
                LIMIT 1
                """
            )
        ).first()
        return row is not None
    except Exception:
        return False


def _bm25_via_tsv(
    session: Session,
    query: str,
    *,
    top_k: int,
) -> List[Tuple[News, float]]:
    parts = tokens_to_tsquery_parts(query)
    if not parts:
        return []
    # OR 召回，提高中文短查询命中率
    tsquery = " | ".join(parts)
    candidate_limit = max(top_k * 5, 30)
    sql = text(
        """
        SELECT id
        FROM news
        WHERE search_tsv IS NOT NULL
          AND process_status = 'ready'
          AND search_tsv @@ to_tsquery('simple', :q)
        ORDER BY ts_rank_cd(search_tsv, to_tsquery('simple', :q)) DESC
        LIMIT :lim
        """
    )
    try:
        ids = [
            int(r[0])
            for r in session.execute(
                sql, {"q": tsquery, "lim": candidate_limit}
            ).all()
        ]
    except Exception as e:
        logger.warning("tsvector 召回失败，将降级: %s", e)
        return []
    if not ids:
        return []

    news_rows = session.scalars(select(News).where(News.id.in_(ids))).all()
    by_id = {n.id: n for n in news_rows}
    n_docs, avgdl, df_map = _load_corpus_stats(session)
    query_terms = tokenize(query)
    scored: List[Tuple[News, float]] = []
    for i in ids:
        news = by_id.get(i)
        if news is None:
            continue
        doc_tokens = tokenize(_doc_text(news))
        score = bm25_score_document(
            query_terms,
            doc_tokens,
            n_docs=n_docs,
            avgdl=avgdl,
            df_map=df_map,
        )
        if score > 0:
            scored.append((news, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]


def _bm25_ilike_fallback(
    session: Session,
    query: str,
    *,
    top_k: int,
) -> List[Tuple[News, float]]:
    """无 search_tsv 时：ILIKE 粗召回 + BM25 精排。"""
    q = (query or "").strip()
    if not q:
        return []
    terms = tokenize(q)
    patterns = [f"%{t}%" for t in terms[:8]] or [f"%{q}%"]
    conds = []
    for p in patterns:
        conds.extend(
            [
                News.title.ilike(p),
                News.abstract.ilike(p),
                News.content.ilike(p),
            ]
        )
    from backend.src.db.crud.news import news_ready_filter

    rows = list(
        session.scalars(
            select(News)
            .where(or_(*conds))
            .where(news_ready_filter())
            .limit(max(top_k * 5, 30))
        ).all()
    )
    if not rows:
        return []
    n_docs, avgdl, df_map = _load_corpus_stats(session)
    query_terms = tokenize(q)
    scored: List[Tuple[News, float]] = []
    for news in rows:
        doc_tokens = tokenize(_doc_text(news))
        score = bm25_score_document(
            query_terms,
            doc_tokens,
            n_docs=max(n_docs, len(rows)),
            avgdl=avgdl,
            df_map=df_map,
        )
        if score > 0:
            scored.append((news, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]


def bm25_search(
    session: Session,
    query: str,
    *,
    top_k: int = 10,
) -> List[Tuple[News, float]]:
    """
    BM25 检索。优先 tsvector 召回；列未就绪时降级 ILIKE + BM25。
    """
    q = (query or "").strip()
    if not q:
        return []
    if _tsvector_ready(session):
        hits = _bm25_via_tsv(session, q, top_k=top_k)
        if hits:
            return hits
        logger.warning("BM25 tsvector 无命中，尝试 ILIKE 降级")
    else:
        logger.warning("news.search_tsv 未就绪，BM25 使用 ILIKE 降级")
    return _bm25_ilike_fallback(session, q, top_k=top_k)
