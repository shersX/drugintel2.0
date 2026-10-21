"""RAG 检索器。"""

from __future__ import annotations

from typing import List, Tuple

from sqlalchemy.orm import Session

from backend.src.models.news import News
from backend.src.processors.embedding import SiliconFlowEmbeddingClient
from backend.src.rag.intent import Intent, IntentResult, classify_intent
from backend.src.search.hybrid import hybrid_search


async def retrieve_hits(
    session: Session,
    search_query: str,
    *,
    top_k: int = 5,
    embedding_client: SiliconFlowEmbeddingClient | None = None,
) -> List[Tuple[News, float]]:
    """仅检索，不分类意图。search_query 应为改写后的检索句。"""
    q = (search_query or "").strip()
    if not q:
        return []
    client = embedding_client or SiliconFlowEmbeddingClient.from_env()
    q_emb = await client.embed_one(q)
    return hybrid_search(session, q, q_emb, top_k=top_k)


async def retrieve_for_query(
    session: Session,
    query: str,
    *,
    top_k: int = 5,
    embedding_client: SiliconFlowEmbeddingClient | None = None,
) -> tuple[IntentResult, List[Tuple[News, float]]]:
    intent = classify_intent(query)
    if intent.intent == Intent.CHITCHAT:
        return intent, []
    hits = await retrieve_hits(
        session, query, top_k=top_k, embedding_client=embedding_client
    )
    return intent, hits
