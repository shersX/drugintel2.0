"""RAG 问答编排（含重排与多轮）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, List, Optional

from backend.src.db.session import session_scope
from backend.src.rag.conversation import append_turn, get_history, new_session_id
from backend.src.rag.generator import generate_answer, generate_answer_stream
from backend.src.rag.intent import IntentResult
from backend.src.rag.reranker import rerank
from backend.src.rag.retriever import retrieve_for_query


@dataclass
class AskResult:
    intent: IntentResult
    answer: str
    sources: List[Dict[str, Any]]
    session_id: str


async def ask(
    query: str,
    *,
    top_k: int = 5,
    session_id: Optional[str] = None,
) -> AskResult:
    sid = session_id or new_session_id()
    history = get_history(sid)
    with session_scope() as session:
        intent, hits = await retrieve_for_query(session, query, top_k=top_k * 2)
        hits = await rerank(query, hits, top_k=top_k)
        sources = [
            {
                "id": n.id,
                "title": n.title,
                "score": float(score),
                "detail_url": n.detail_url,
                "abstract": (n.abstract or "")[:200],
            }
            for n, score in hits
        ]
        answer = await generate_answer(query, hits, history=history)
    append_turn(sid, role="user", content=query)
    append_turn(sid, role="assistant", content=answer)
    return AskResult(intent=intent, answer=answer, sources=sources, session_id=sid)


async def ask_stream(
    query: str,
    *,
    top_k: int = 5,
    session_id: Optional[str] = None,
) -> AsyncIterator[Dict[str, Any]]:
    """先 yield meta，再 yield token，最后 yield done。"""
    sid = session_id or new_session_id()
    history = get_history(sid)
    with session_scope() as session:
        intent, hits = await retrieve_for_query(session, query, top_k=top_k * 2)
        hits = await rerank(query, hits, top_k=top_k)
        sources = [
            {
                "id": n.id,
                "title": n.title,
                "score": float(score),
                "detail_url": n.detail_url,
                "abstract": (n.abstract or "")[:200],
            }
            for n, score in hits
        ]
        yield {
            "type": "meta",
            "session_id": sid,
            "intent": intent.intent.value,
            "sources": sources,
        }
        parts: List[str] = []
        async for piece in generate_answer_stream(query, hits, history=history):
            parts.append(piece)
            yield {"type": "token", "content": piece}
        answer = "".join(parts)
    append_turn(sid, role="user", content=query)
    append_turn(sid, role="assistant", content=answer)
    yield {"type": "done", "session_id": sid, "answer": answer}
