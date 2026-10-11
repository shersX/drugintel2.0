"""多套模型接口的保存、启用与连通性检查。"""

from __future__ import annotations

from typing import Any, Dict, Optional

import aiohttp
from sqlalchemy import select, update

from backend.src.db.session import (
    rebuild_vector_columns,
    session_scope,
    vector_column_dim,
)
from backend.src.models.llm_profile import LlmProfile

DEFAULT_BASE_URL = "https://api.siliconflow.cn/v1"
DEFAULT_CHAT_MODEL = "deepseek-ai/DeepSeek-V4-Flash"
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-m3"
DEFAULT_EMBEDDING_DIM = 1024
DEFAULT_RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"

_KEY_ATTR = {
    "chat": "api_key",
    "embedding": "embedding_api_key",
    "rerank": "reranker_api_key",
    "reranker": "reranker_api_key",
}


class LlmProfileError(ValueError):
    """前端可展示的配置错误。"""


class DimensionMismatch(LlmProfileError):
    """启用的嵌入维度和库中向量列不一致。"""

    def __init__(self, current_dim: Optional[int], next_dim: int):
        self.current_dim = current_dim
        self.next_dim = next_dim
        current = f"{current_dim} 维" if current_dim else "未固定维度"
        super().__init__(
            f"嵌入维度将从 {current}改为 {next_dim} 维。"
            "确认后会清空已有新闻向量和事件中心向量，并重建索引。"
            "历史新闻不会自动重新向量化，之后的采集只处理新文章。"
        )


def _clean_url(value: str) -> str:
    return (value or "").strip().rstrip("/")


def _require_text(value: Optional[str], label: str) -> str:
    text = (value or "").strip()
    if not text:
        raise LlmProfileError(f"请填写{label}")
    return text


def _require_dim(value: Any) -> int:
    try:
        dim = int(value)
    except (TypeError, ValueError):
        raise LlmProfileError("请填写向量维度") from None
    if dim < 1 or dim > 4096:
        raise LlmProfileError("向量维度需在 1 到 4096 之间")
    return dim


def _mask_key(api_key: str) -> str:
    key = api_key or ""
    if not key:
        return ""
    if len(key) <= 4:
        return "•" * len(key)
    return f"••••{key[-4:]}"


def _public(row: LlmProfile) -> Dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "base_url": row.base_url,
        "chat_model": row.chat_model,
        "has_chat_key": bool(row.api_key),
        "chat_key_hint": _mask_key(row.api_key),
        "embedding_base_url": row.embedding_base_url,
        "embedding_model": row.embedding_model,
        "embedding_dim": row.embedding_dim,
        "has_embedding_key": bool(row.embedding_api_key),
        "embedding_key_hint": _mask_key(row.embedding_api_key),
        "reranker_base_url": row.reranker_base_url,
        "reranker_model": row.reranker_model,
        "has_reranker_key": bool(row.reranker_api_key),
        "reranker_key_hint": _mask_key(row.reranker_api_key),
        "is_active": row.is_active,
    }


def _defaults() -> Dict[str, Any]:
    return {
        "base_url": DEFAULT_BASE_URL,
        "chat_model": DEFAULT_CHAT_MODEL,
        "embedding_base_url": DEFAULT_BASE_URL,
        "embedding_model": DEFAULT_EMBEDDING_MODEL,
        "embedding_dim": DEFAULT_EMBEDDING_DIM,
        "reranker_base_url": DEFAULT_BASE_URL,
        "reranker_model": DEFAULT_RERANKER_MODEL,
    }


def list_profiles() -> Dict[str, Any]:
    with session_scope() as session:
        rows = list(session.scalars(select(LlmProfile).order_by(LlmProfile.id.asc())).all())
        profiles = [_public(row) for row in rows]
        return {
            "profiles": profiles,
            "using_env": not any(item["is_active"] for item in profiles),
            "vector_dim": vector_column_dim(session.connection()),
            "defaults": _defaults(),
        }


def create_profile(
    *,
    name: str,
    api_key: str,
    base_url: str,
    chat_model: str,
    embedding_api_key: str,
    embedding_base_url: str,
    embedding_model: str,
    embedding_dim: int,
    reranker_api_key: str,
    reranker_base_url: str,
    reranker_model: str,
) -> Dict[str, Any]:
    with session_scope() as session:
        row = LlmProfile(
            name=_require_text(name, "名称")[:100],
            api_key=_require_text(api_key, "对话 API Key"),
            base_url=_clean_url(_require_text(base_url, "对话 Base URL"))[:300],
            chat_model=_require_text(chat_model, "对话模型")[:200],
            embedding_api_key=_require_text(embedding_api_key, "嵌入 API Key"),
            embedding_base_url=_clean_url(_require_text(embedding_base_url, "嵌入 Base URL"))[:300],
            embedding_model=_require_text(embedding_model, "嵌入模型")[:200],
            embedding_dim=_require_dim(embedding_dim),
            reranker_api_key=_require_text(reranker_api_key, "重排 API Key"),
            reranker_base_url=_clean_url(_require_text(reranker_base_url, "重排 Base URL"))[:300],
            reranker_model=_require_text(reranker_model, "重排模型")[:200],
            is_active=False,
        )
        session.add(row)
        session.flush()
        return _public(row)


def _assign_key(current: str, incoming: Optional[str], label: str) -> str:
    text = (incoming or "").strip()
    if text:
        return text
    if current:
        return current
    raise LlmProfileError(f"请填写{label}")


def update_profile(
    profile_id: int,
    *,
    name: str,
    api_key: Optional[str],
    base_url: str,
    chat_model: str,
    embedding_api_key: Optional[str],
    embedding_base_url: str,
    embedding_model: str,
    embedding_dim: int,
    reranker_api_key: Optional[str],
    reranker_base_url: str,
    reranker_model: str,
    rebuild: bool = False,
) -> Dict[str, Any]:
    dim = _require_dim(embedding_dim)
    with session_scope() as session:
        row = session.get(LlmProfile, profile_id)
        if row is None:
            raise LlmProfileError("配置不存在")
        if row.is_active:
            _align_dimension(session.connection(), dim, rebuild)
        row.name = _require_text(name, "名称")[:100]
        row.base_url = _clean_url(_require_text(base_url, "对话 Base URL"))[:300]
        row.chat_model = _require_text(chat_model, "对话模型")[:200]
        row.api_key = _assign_key(row.api_key, api_key, "对话 API Key")
        row.embedding_base_url = _clean_url(_require_text(embedding_base_url, "嵌入 Base URL"))[:300]
        row.embedding_model = _require_text(embedding_model, "嵌入模型")[:200]
        row.embedding_dim = dim
        row.embedding_api_key = _assign_key(row.embedding_api_key, embedding_api_key, "嵌入 API Key")
        row.reranker_base_url = _clean_url(_require_text(reranker_base_url, "重排 Base URL"))[:300]
        row.reranker_model = _require_text(reranker_model, "重排模型")[:200]
        row.reranker_api_key = _assign_key(row.reranker_api_key, reranker_api_key, "重排 API Key")
        return _public(row)


def delete_profile(profile_id: int) -> None:
    with session_scope() as session:
        row = session.get(LlmProfile, profile_id)
        if row is None:
            raise LlmProfileError("配置不存在")
        session.delete(row)


def _require_saved_keys(row: LlmProfile) -> None:
    if not row.api_key:
        raise LlmProfileError("请先填写对话 API Key")
    if not row.embedding_api_key:
        raise LlmProfileError("请先填写嵌入 API Key")
    if not row.reranker_api_key:
        raise LlmProfileError("请先填写重排 API Key")


def _align_dimension(connection, target: int, rebuild: bool) -> None:
    current = vector_column_dim(connection)
    if current == target:
        return
    if not rebuild:
        raise DimensionMismatch(current, target)
    rebuild_vector_columns(target, connection)


def activate_profile(profile_id: int, *, rebuild: bool = False) -> Dict[str, Any]:
    with session_scope() as session:
        row = session.get(LlmProfile, profile_id)
        if row is None:
            raise LlmProfileError("配置不存在")
        _require_saved_keys(row)
        _align_dimension(session.connection(), int(row.embedding_dim), rebuild)
        session.execute(update(LlmProfile).values(is_active=False))
        row.is_active = True
        session.flush()
        return _public(row)


def _stored_key(profile_id: Optional[int], slot: str) -> str:
    if profile_id is None:
        return ""
    attr = _KEY_ATTR.get(slot or "chat")
    if attr is None:
        raise LlmProfileError("未知的接口类型")
    with session_scope() as session:
        row = session.get(LlmProfile, profile_id)
        if row is None:
            raise LlmProfileError("配置不存在")
        return getattr(row, attr) or ""


async def test_connection(
    *,
    base_url: str,
    api_key: Optional[str],
    profile_id: Optional[int] = None,
    slot: str = "chat",
) -> Dict[str, Any]:
    url = _clean_url(_require_text(base_url, "Base URL"))
    key = (api_key or "").strip() or _stored_key(profile_id, slot)
    if not key:
        raise LlmProfileError("请填写 API Key")
    timeout = aiohttp.ClientTimeout(total=20)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                f"{url}/models",
                headers={"Authorization": f"Bearer {key}"},
            ) as resp:
                if resp.status >= 400:
                    text = (await resp.text())[:200]
                    raise LlmProfileError(f"接口返回 HTTP {resp.status} {text}".strip())
    except LlmProfileError:
        raise
    except Exception as exc:
        raise LlmProfileError(f"无法连接：{exc}") from exc
    return {"ok": True}
