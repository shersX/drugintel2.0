"""RAG 问答编排（含重排与多轮 + PG 会话持久化）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, List, Optional

from backend.src.db.crud.chat import (
    append_message,
    ensure_conversation,
    get_history_messages,
    touch_conversation,
)
from backend.src.db.session import session_scope
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
    conversation_id: str


def _resolve_conversation_id(
    *,
    conversation_id: Optional[str],
    session_id: Optional[str],
) -> Optional[str]:
    return (conversation_id or session_id or "").strip() or None


async def ask(
    query: str,
    *,
    user_id: int,
    top_k: int = 5,
    conversation_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> AskResult:
    cid_hint = _resolve_conversation_id(
        conversation_id=conversation_id, session_id=session_id
    )
    with session_scope() as session:
        conv = ensure_conversation(
            session, user_id=user_id, conversation_id=cid_hint
        )
        cid = conv.id
        history = get_history_messages(session, conversation_id=cid, limit=40)
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
        append_message(session, conversation_id=cid, role="user", content=query)
        append_message(
            session,
            conversation_id=cid,
            role="assistant",
            content=answer,
            sources=sources,
        )
        touch_conversation(session, conversation=conv, title_from_query=query)
    return AskResult(
        intent=intent,
        answer=answer,
        sources=sources,
        session_id=cid,
        conversation_id=cid,
    )


async def ask_stream(
    query: str,
    *,
    user_id: int,
    top_k: int = 5,
    conversation_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> AsyncIterator[Dict[str, Any]]:
    """先 yield meta，再 yield token，最后 yield done。"""
    cid_hint = _resolve_conversation_id(
        conversation_id=conversation_id, session_id=session_id
    )
    with session_scope() as session:
        conv = ensure_conversation(
            session, user_id=user_id, conversation_id=cid_hint
        )
        cid = conv.id
        history = get_history_messages(session, conversation_id=cid, limit=40)
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
            "session_id": cid,
            "conversation_id": cid,
            "intent": intent.intent.value,
            "sources": sources,
        }
        parts: List[str] = []
        async for piece in generate_answer_stream(query, hits, history=history):
            parts.append(piece)
            yield {"type": "token", "content": piece}
        answer = "".join(parts)
        append_message(session, conversation_id=cid, role="user", content=query)
        append_message(
            session,
            conversation_id=cid,
            role="assistant",
            content=answer,
            sources=sources,
        )
        touch_conversation(session, conversation=conv, title_from_query=query)
    yield {"type": "done", "session_id": cid, "conversation_id": cid, "answer": answer}
