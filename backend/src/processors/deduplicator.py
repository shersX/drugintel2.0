"""标题去重（任务 2.3）：批内去重 + 可选对照库中已有标题。"""

from __future__ import annotations

import re
from typing import Iterable, List, Mapping, MutableMapping, Optional, Sequence, Set

from backend.src.core.logger import get_logger

logger = get_logger("processors.deduplicator")

_WHITESPACE_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[\s\u3000\|｜\-—_·•、，,。.!！?？:：;；\"'“”‘’\(\)（）\[\]【】<>《》]+")


def normalize_title(title: str) -> str:
    """规范化标题：去空白与常见标点，统一小写，便于精确比对。"""
    if not title or not isinstance(title, str):
        return ""
    text = title.strip().lower()
    text = _PUNCT_RE.sub("", text)
    text = _WHITESPACE_RE.sub("", text)
    return text


def deduplicate_by_title(
    news_list: Sequence[MutableMapping],
    *,
    existing_titles: Optional[Iterable[str]] = None,
) -> List[MutableMapping]:
    """
    基于规范化标题去重。

    Args:
        news_list: 待去重新闻（需含 title）
        existing_titles: 库中已有原始标题；若提供则同时过滤已入库标题

    Returns:
        保留列表（同批内保留首次出现；已在库中的丢弃）
    """
    existing_norm: Set[str] = set()
    if existing_titles:
        for t in existing_titles:
            n = normalize_title(t)
            if n:
                existing_norm.add(n)

    seen: Set[str] = set()
    kept: List[MutableMapping] = []
    dropped_batch = 0
    dropped_db = 0

    for item in news_list or []:
        if not isinstance(item, Mapping):
            continue
        title = item.get("title") or ""
        key = normalize_title(str(title))
        if not key:
            kept.append(item)  # type: ignore[arg-type]
            continue
        if key in existing_norm:
            dropped_db += 1
            continue
        if key in seen:
            dropped_batch += 1
            continue
        seen.add(key)
        kept.append(item)  # type: ignore[arg-type]

    logger.info(
        "标题去重 输入=%s 保留=%s 批内重复=%s 库内已有=%s",
        len(news_list or []),
        len(kept),
        dropped_batch,
        dropped_db,
    )
    return kept
