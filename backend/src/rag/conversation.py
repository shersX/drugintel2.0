"""多轮对话管理（任务 5.4）：Redis 优先，失败则进程内缓存。"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, Dict, List, Optional

from backend.src.core.config import RedisEnvConfig
from backend.src.core.logger import get_logger

logger = get_logger("rag.conversation")

_MEMORY: Dict[str, Dict[str, Any]] = {}
_TTL_SEC = 60 * 60 * 24


def _redis_client():
    try:
        import redis

        client = redis.Redis.from_url(RedisEnvConfig.load().url, decode_responses=True)
        client.ping()
        return client
    except Exception as e:
        logger.warning("Redis 不可用，对话改用内存: %s", e)
        return None


def new_session_id() -> str:
    return uuid.uuid4().hex


def _key(session_id: str) -> str:
    return f"drugintel:chat:{session_id}"


def get_history(session_id: str, *, limit: int = 20) -> List[Dict[str, str]]:
    if not session_id:
        return []
    client = _redis_client()
    if client is not None:
        raw = client.get(_key(session_id))
        if not raw:
            return []
        data = json.loads(raw)
        return list(data.get("messages") or [])[-limit:]
    data = _MEMORY.get(session_id) or {}
    return list(data.get("messages") or [])[-limit:]


def append_turn(
    session_id: str,
    *,
    role: str,
    content: str,
) -> str:
    sid = session_id or new_session_id()
    messages = get_history(sid, limit=100)
    messages.append({"role": role, "content": content, "ts": int(time.time())})
    payload = {"messages": messages[-40:], "updated_at": int(time.time())}
    client = _redis_client()
    if client is not None:
        client.setex(_key(sid), _TTL_SEC, json.dumps(payload, ensure_ascii=False))
    else:
        _MEMORY[sid] = payload
    return sid


def clear_session(session_id: str) -> None:
    client = _redis_client()
    if client is not None:
        client.delete(_key(session_id))
    _MEMORY.pop(session_id, None)
