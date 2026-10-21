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


def _load_page_pin(session, news_id: Optional[int]) -> Optional[Hit]:
    if news_id is None:
        return None
    try:
        nid = int(news_id)
    except (TypeError, ValueError):
        return None
    news = session.get(News, nid)
    if news is None or news.process_status != "ready":
        return None
    return (news, 1.0)


def _merge_with_pin(
    retrieved: Sequence[Hit],
    pinned: Optional[Hit],
    *,
    top_k: int,
) -> List[Hit]:
    """Pinned 始终首位；去重后截断到 top_k。"""
    if pinned is None:
        return list(retrieved[:top_k])
    pin_news, pin_score = pinned
    rest: List[Hit] = []
    for n, score in retrieved:
        if n.id == pin_news.id:
            continue
        rest.append((n, score))
        if len(rest) >= max(0, top_k - 1):
            break
    return [(pin_news, pin_score), *rest]


def _sources_from_hits(
    hits: Sequence[Hit],
    *,
    page_news_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for n, score in hits:
        row: Dict[str, Any] = {
            "id": n.id,
            "title": n.title,
            "score": float(score),
            "detail_url": n.detail_url,
            "abstract": (n.abstract or "")[:200],
        }
        if page_news_id is not None and n.id == page_news_id:
            row["page_context"] = True
        out.append(row)
    return out


def _stage(
    stage: str,
    *,
    detail: str = "",
    intent: Optional[str] = None,
    search_query: Optional[str] = None,
    news_id: Optional[int] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"type": "stage", "stage": stage}
    if detail:
        payload["detail"] = detail
    if intent:
        payload["intent"] = intent
    if search_query:
        payload["search_query"] = search_query
    if news_id is not None:
        payload["news_id"] = news_id
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
    news_id: Optional[int] = None,
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
        news_id=news_id,
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
    news_id: Optional[int] = None,
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
        pinned = _load_page_pin(session, news_id)
        page_news_id = pinned[0].id if pinned else None
        intent = classify_intent(query)
        yield _stage(
            "intent",
            detail=intent.intent.value,
            intent=intent.intent.value,
            news_id=page_news_id,
        )

        # 闲聊：不检索（页面上下文也不注入）
        if intent.intent == Intent.CHITCHAT:
            yield _stage("generate", intent=intent.intent.value, news_id=page_news_id)
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

        # 1) 原句检索 + 页面 pin 合并
        search_query = query
        sources: List[Dict[str, Any]] = []
        yield _stage(
            "retrieve",
            intent=intent.intent.value,
            news_id=page_news_id,
        )
        raw_hits = await retrieve_hits(session, search_query, top_k=resolved_k * 2)
        yield _stage(
            "rerank",
            intent=intent.intent.value,
            news_id=page_news_id,
        )
        retrieved = await rerank(search_query, raw_hits, top_k=resolved_k)
        retrieved = filter_by_relevance(retrieved)
        hits = _merge_with_pin(retrieved, pinned, top_k=resolved_k)

        # 2) 库内不足且无 pin → 改写再检索；有 pin 则跳过 clarify
        if not _hits_ok(retrieved) and pinned is None:
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
            retrieved = await rerank(search_query, raw_hits, top_k=resolved_k)
            retrieved = filter_by_relevance(retrieved)
            hits = _merge_with_pin(retrieved, pinned, top_k=resolved_k)

        elif not _hits_ok(retrieved) and pinned is not None:
            # 有页面上下文：仍可尝试一轮补充检索，但不澄清
            yield _stage(
                "retry",
                detail="补充检索相关新闻",
                intent=intent.intent.value,
                news_id=page_news_id,
            )
            yield _stage(
                "rewrite",
                intent=intent.intent.value,
                news_id=page_news_id,
            )
            rewritten = await rewrite_query(
                query, history=history, intent=intent, empty_retry=True
            )
            search_query = rewritten.search_query or query
            if not (rewritten.need_clarify and rewritten.clarify_question):
                yield _stage(
                    "retrieve",
                    detail="使用优化问法补充检索",
                    intent=intent.intent.value,
                    search_query=search_query,
                    news_id=page_news_id,
                )
                raw_hits = await retrieve_hits(
                    session, search_query, top_k=resolved_k * 2
                )
                yield _stage(
                    "rerank",
                    intent=intent.intent.value,
                    search_query=search_query,
                    news_id=page_news_id,
                )
                retrieved = await rerank(search_query, raw_hits, top_k=resolved_k)
                retrieved = filter_by_relevance(retrieved)
                hits = _merge_with_pin(retrieved, pinned, top_k=resolved_k)
            else:
                # 改写认为需澄清，但有 pin：仅用当前页作答
                search_query = query
                hits = _merge_with_pin([], pinned, top_k=resolved_k)

        if not _hits_ok(hits):
            question = await clarify_after_empty(
                query, history=history, search_query=search_query
            )
            async for ev in _emit_clarify(question, search_query):
                yield ev
            return

        sources = _sources_from_hits(hits, page_news_id=page_news_id)
        yield {
            "type": "meta",
            "session_id": cid,
            "conversation_id": cid,
            "intent": intent.intent.value,
            "sources": sources,
            "search_query": search_query if search_query != query else None,
            "news_id": page_news_id,
        }
        yield _stage(
            "generate",
            intent=intent.intent.value,
            search_query=search_query if search_query != query else None,
            news_id=page_news_id,
        )
        parts = []
        async for piece in generate_answer_stream(
            query,
            hits,
            history=history,
            intent=intent,
            page_news_id=page_news_id,
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
        "news_id": page_news_id,
    }
