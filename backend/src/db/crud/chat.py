"""问答会话 CRUD。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.src.models.chat import ChatConversation, ChatMessage

DEFAULT_TITLE = "新对话"
TITLE_MAX = 40


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_conversation_id() -> str:
    # 与 rag.conversation.new_session_id 对齐（UUID hex），避免 CRUD↔rag 循环导入
    from uuid import uuid4

    return uuid4().hex


def truncate_title(text: str, max_len: int = TITLE_MAX) -> str:
    cleaned = " ".join((text or "").strip().split())
    if not cleaned:
        return DEFAULT_TITLE
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1] + "…"


def create_conversation(session: Session, *, user_id: int, title: str = DEFAULT_TITLE) -> ChatConversation:
    row = ChatConversation(
        id=_new_conversation_id(),
        user_id=user_id,
        title=title or DEFAULT_TITLE,
        created_at=_now(),
        updated_at=_now(),
    )
    session.add(row)
    session.flush()
    return row


def get_conversation_for_user(
    session: Session, *, conversation_id: str, user_id: int
) -> Optional[ChatConversation]:
    if not conversation_id:
        return None
    return session.scalar(
        select(ChatConversation).where(
            ChatConversation.id == conversation_id,
            ChatConversation.user_id == user_id,
        )
    )


def list_conversations(
    session: Session, *, user_id: int, limit: int = 50
) -> List[ChatConversation]:
    return list(
        session.scalars(
            select(ChatConversation)
            .where(ChatConversation.user_id == user_id)
            .order_by(ChatConversation.updated_at.desc())
            .limit(limit)
        ).all()
    )


def rename_conversation(
    session: Session, *, conversation_id: str, user_id: int, title: str
) -> Optional[ChatConversation]:
    row = get_conversation_for_user(session, conversation_id=conversation_id, user_id=user_id)
    if row is None:
        return None
    row.title = truncate_title(title, max_len=200) if title.strip() else DEFAULT_TITLE
    row.updated_at = _now()
    session.flush()
    return row


def delete_conversation(session: Session, *, conversation_id: str, user_id: int) -> bool:
    row = get_conversation_for_user(session, conversation_id=conversation_id, user_id=user_id)
    if row is None:
        return False
    session.execute(delete(ChatMessage).where(ChatMessage.conversation_id == conversation_id))
    session.delete(row)
    session.flush()
    return True


def list_messages(
    session: Session, *, conversation_id: str, limit: int = 200
) -> List[ChatMessage]:
    return list(
        session.scalars(
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.id.asc())
            .limit(limit)
        ).all()
    )


def get_history_messages(
    session: Session, *, conversation_id: str, limit: int = 40
) -> List[Dict[str, str]]:
    rows = list(
        session.scalars(
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.id.desc())
            .limit(limit)
        ).all()
    )
    rows.reverse()
    return [{"role": r.role, "content": r.content} for r in rows]


def append_message(
    session: Session,
    *,
    conversation_id: str,
    role: str,
    content: str,
    sources: Any = None,
) -> ChatMessage:
    msg = ChatMessage(
        conversation_id=conversation_id,
        role=role,
        content=content or "",
        sources=sources,
        created_at=_now(),
    )
    session.add(msg)
    session.flush()
    return msg


def touch_conversation(
    session: Session,
    *,
    conversation: ChatConversation,
    title_from_query: Optional[str] = None,
) -> None:
    if title_from_query and (not conversation.title or conversation.title == DEFAULT_TITLE):
        conversation.title = truncate_title(title_from_query)
    conversation.updated_at = _now()
    session.flush()


def ensure_conversation(
    session: Session,
    *,
    user_id: int,
    conversation_id: Optional[str] = None,
) -> ChatConversation:
    if conversation_id:
        existing = get_conversation_for_user(
            session, conversation_id=conversation_id, user_id=user_id
        )
        if existing is not None:
            return existing
    return create_conversation(session, user_id=user_id)


def conversation_to_dict(row: ChatConversation) -> Dict[str, Any]:
    return {
        "id": row.id,
        "title": row.title,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def message_to_dict(row: ChatMessage) -> Dict[str, Any]:
    return {
        "id": row.id,
        "role": row.role,
        "content": row.content,
        "sources": row.sources or [],
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
