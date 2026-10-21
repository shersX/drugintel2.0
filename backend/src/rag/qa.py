"""RAG 问答编排：意图 → 原句检索 →（不足则改写再检索|澄清）→ 生成；支持阶段事件流。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, List, Optional, Sequence, Tuple

from backend.src.db.crud.chat import (
    append_message,
    ensure_conversation,
    get_history_messages,
    touch_conversation,
)
from backend.src.db.session import session_scope
from backend.src.models.news import News
from backend.src.rag.generator import generate_answer_stream
from backend.src.rag.intent import Intent, IntentResult, classify_intent
from backend.src.rag.query_rewrite import clarify_after_empty, rewrite_query
from backend.src.rag.reranker import rerank
from backend.src.rag.retriever import retrieve_hits
from backend.src.rag.settings import load_rag_settings
from backend.src.rag.threshold import filter_by_relevance

Hit = Tuple[News, float]


@dataclass
class AskResult:
    intent: IntentResult
    answer: str
    sources: List[Dict[str, Any]]
    session_id: str
    conversation_id: str
    search_query: Optional[str] = None
    clarify: bool = False


def _resolve_conversation_id(
    *,
    conversation_id: Optional[str],
    session_id: Optional[str],
) -> Optional[str]:
    return (conversation_id or session_id or "").strip() or None


def _resolve_top_k(top_k: Optional[int] = None) -> int:
    settings = load_rag_settings()
    return settings.top_k


def _sources_from_hits(hits: Sequence[Hit]) -> List[Dict[str, Any]]:
    return [
        {
            "id": n.id,
            "title": n.title,
            "score": float(score),
            "detail_url": n.detail_url,
            "abstract": (n.abstract or "")[:200],
        }
        for n, score in hits
    ]


def _stage(
    stage: str,
    *,
    detail: str = "",
    intent: Optional[str] = None,
    search_query: Optional[str] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"type": "stage", "stage": stage}
    if detail:
        payload["detail"] = detail
    if intent:
        payload["intent"] = intent
    if search_query:
        payload["search_query"] = search_query
    return payload


def _hits_ok(hits: Sequence[Hit]) -> bool:
    return len(hits) > 0


async def ask(
    query: str,
    *,
    user_id: int,
    top_k: Optional[int] = None,
    conversation_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> AskResult:
    """同步问答（聚合流式路径结果）。"""
    final: Dict[str, Any] = {
        "answer": "",
        "sources": [],
        "intent": None,
        "search_query": None,
        "clarify": False,
        "session_id": "",
        "conversation_id": "",
    }
    async for event in ask_stream(
        query,
        user_id=user_id,
        top_k=top_k,
        conversation_id=conversation_id,
        session_id=session_id,
    ):
        et = event.get("type")
        if et == "meta":
            final["sources"] = event.get("sources") or []
            final["search_query"] = event.get("search_query")
            if event.get("intent"):
                final["intent_value"] = event["intent"]
            final["session_id"] = event.get("session_id") or final["session_id"]
            final["conversation_id"] = (
                event.get("conversation_id") or final["conversation_id"]
            )
        elif et == "clarify":
            final["clarify"] = True
            final["answer"] = event.get("question") or ""
            final["search_query"] = event.get("search_query")
            if event.get("intent"):
                final["intent_value"] = event["intent"]
            final["session_id"] = event.get("session_id") or final["session_id"]
            final["conversation_id"] = (
                event.get("conversation_id") or final["conversation_id"]
            )
        elif et == "token":
            if not final["clarify"]:
                final["answer"] = (final["answer"] or "") + (event.get("content") or "")
        elif et == "done":
            if event.get("answer") and not final["clarify"]:
                final["answer"] = event["answer"]
            if event.get("clarify"):
                final["clarify"] = True
            if event.get("sources") is not None:
                final["sources"] = event.get("sources") or []
            if event.get("search_query"):
                final["search_query"] = event.get("search_query")
            final["session_id"] = event.get("session_id") or final["session_id"]
            final["conversation_id"] = (
                event.get("conversation_id") or final["conversation_id"]
            )

    intent_value = final.get("intent_value") or Intent.NEWS_QUERY.value
    try:
        intent_enum = Intent(intent_value)
    except ValueError:
        intent_enum = Intent.NEWS_QUERY
    intent = IntentResult(intent=intent_enum, confidence=0.6, raw=query)
    return AskResult(
        intent=intent,
        answer=final["answer"] or "",
        sources=list(final["sources"] or []),
        session_id=str(final["session_id"] or ""),
        conversation_id=str(final["conversation_id"] or ""),
        search_query=final.get("search_query"),
        clarify=bool(final.get("clarify")),
    )


async def ask_stream(
    query: str,
    *,
    user_id: int,
    top_k: Optional[int] = None,
    conversation_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> AsyncIterator[Dict[str, Any]]:
    """
    事件顺序：
    stage* → (clarify + done) | (meta → stage generate → token* → done)
    """
    resolved_k = _resolve_top_k(top_k)
    cid_hint = _resolve_conversation_id(
        conversation_id=conversation_id, session_id=session_id
    )
    with session_scope() as session:
        conv = ensure_conversation(
            session, user_id=user_id, conversation_id=cid_hint
        )
        cid = conv.id
        history = get_history_messages(session, conversation_id=cid, limit=40)
        intent = classify_intent(query)
        yield _stage(
            "intent",
            detail=intent.intent.value,
            intent=intent.intent.value,
        )

        # 闲聊：不检索
        if intent.intent == Intent.CHITCHAT:
            yield _stage("generate", intent=intent.intent.value)
            parts: List[str] = []
            async for piece in generate_answer_stream(
                query, [], history=history, intent=intent
            ):
                parts.append(piece)
                yield {"type": "token", "content": piece}
            answer = "".join(parts)
            append_message(session, conversation_id=cid, role="user", content=query)
            append_message(
                session, conversation_id=cid, role="assistant", content=answer
            )
            touch_conversation(session, conversation=conv, title_from_query=query)
            yield {
                "type": "done",
                "session_id": cid,
                "conversation_id": cid,
                "answer": answer,
                "clarify": False,
                "sources": [],
            }
            return

        async def _emit_clarify(question: str, used_query: str) -> AsyncIterator[Dict[str, Any]]:
            append_message(session, conversation_id=cid, role="user", content=query)
            append_message(
                session, conversation_id=cid, role="assistant", content=question
            )
            touch_conversation(session, conversation=conv, title_from_query=query)
            yield {
                "type": "clarify",
                "question": question,
                "intent": intent.intent.value,
                "search_query": used_query,
                "session_id": cid,
                "conversation_id": cid,
            }
            yield {
                "type": "done",
                "session_id": cid,
                "conversation_id": cid,
                "answer": question,
                "clarify": True,
                "sources": [],
            }

        # 1) 原句检索
        search_query = query
        sources: List[Dict[str, Any]] = []
        yield _stage("retrieve", intent=intent.intent.value)
        raw_hits = await retrieve_hits(session, search_query, top_k=resolved_k * 2)
        yield _stage("rerank", intent=intent.intent.value)
        hits = await rerank(search_query, raw_hits, top_k=resolved_k)
        hits = filter_by_relevance(hits)

        # 2) 不足 → 改写再检索（最多一轮）
        if not _hits_ok(hits):
            yield _stage(
                "retry",
                detail="原句检索不足，正在优化问法",
                intent=intent.intent.value,
            )
            yield _stage("rewrite", intent=intent.intent.value)
            rewritten = await rewrite_query(
                query, history=history, intent=intent, empty_retry=True
            )
            search_query = rewritten.search_query or query
            if rewritten.need_clarify and rewritten.clarify_question:
                async for ev in _emit_clarify(rewritten.clarify_question, search_query):
                    yield ev
                return

            yield _stage(
                "retrieve",
                detail="使用优化问法补充检索",
                intent=intent.intent.value,
                search_query=search_query,
            )
            raw_hits = await retrieve_hits(
                session, search_query, top_k=resolved_k * 2
            )
            yield _stage(
                "rerank",
                intent=intent.intent.value,
                search_query=search_query,
            )
            hits = await rerank(search_query, raw_hits, top_k=resolved_k)
            hits = filter_by_relevance(hits)

        if not _hits_ok(hits):
            question = await clarify_after_empty(
                query, history=history, search_query=search_query
            )
            async for ev in _emit_clarify(question, search_query):
                yield ev
            return

        sources = _sources_from_hits(hits)
        yield {
            "type": "meta",
            "session_id": cid,
            "conversation_id": cid,
            "intent": intent.intent.value,
            "sources": sources,
            "search_query": search_query if search_query != query else None,
        }
        yield _stage(
            "generate",
            intent=intent.intent.value,
            search_query=search_query if search_query != query else None,
        )
        parts = []
        async for piece in generate_answer_stream(
            query, hits, history=history, intent=intent
        ):
            parts.append(piece)
            yield {"type": "token", "content": piece}
        answer = "".join(parts)
        append_message(session, conversation_id=cid, role="user", content=query)
        append_message(
            session,
            conversation_id=cid,
            role="assistant",
            content=answer,
            sources=sources or None,
        )
        touch_conversation(session, conversation=conv, title_from_query=query)
    yield {
        "type": "done",
        "session_id": cid,
        "conversation_id": cid,
        "answer": answer,
        "clarify": False,
        "search_query": search_query if search_query != query else None,
        "sources": sources,
    }
