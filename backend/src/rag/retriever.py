"""RAG 检索器。"""

from __future__ import annotations

from typing import List, Tuple

from sqlalchemy.orm import Session

from backend.src.models.news import News
from backend.src.processors.embedding import SiliconFlowEmbeddingClient
from backend.src.rag.intent import Intent, IntentResult, classify_intent
from backend.src.search.hybrid import hybrid_search
from backend.src.search.vector import vector_search


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

    client = embedding_client or SiliconFlowEmbeddingClient.from_env()
    q_emb = await client.embed_one(query)
    if intent.intent in {Intent.NEWS_QUERY, Intent.COMPARE}:
        hits = hybrid_search(session, query, q_emb, top_k=top_k)
    else:
        hits = vector_search(session, q_emb, top_k=top_k)
    return intent, hits
