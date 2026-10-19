"""中文分词工具：jieba 切词后供 tsvector / BM25 使用。"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import List

from backend.src.core.logger import get_logger

logger = get_logger("search.tokenize")

_TOKEN_RE = re.compile(r"[\u4e00-\u9fffA-Za-z0-9][\u4e00-\u9fffA-Za-z0-9\-+./%]*")
_CJK_SPAN_RE = re.compile(r"[\u4e00-\u9fff]{2,16}")
_ASCII_TERM_RE = re.compile(r"[A-Za-z][A-Za-z0-9\-+./%]{1,40}|\d+(?:\.\d+)?%?")


@lru_cache(maxsize=1)
def _ensure_jieba():
    try:
        import jieba

        jieba.setLogLevel(20)
        return jieba
    except Exception as e:
        logger.warning("jieba 不可用，分词降级为正则: %s", e)
        return None


def tokenize(text: str) -> List[str]:
    """
    返回小写 token 列表。
    - jieba 切词（search 模式）
    - 额外保留连续中文片段（利于药名整词命中）
    - 保留英文/数字术语（如 KRAS、G12C）
    """
    raw = (text or "").strip()
    if not raw:
        return []

    seen = set()
    out: List[str] = []

    def _add(token: str) -> None:
        t = (token or "").strip().lower()
        if not t or t in seen:
            return
        if len(t) == 1 and not ("\u4e00" <= t <= "\u9fff"):
            return
        seen.add(t)
        out.append(t)

    jieba = _ensure_jieba()
    if jieba is not None:
        for p in jieba.lcut_for_search(raw):
            _add(p)
    else:
        for m in _TOKEN_RE.finditer(raw):
            _add(m.group(0))

    for m in _CJK_SPAN_RE.finditer(raw):
        _add(m.group(0))
    for m in _ASCII_TERM_RE.finditer(raw):
        _add(m.group(0))

    return out


def tokens_to_ts_text(text: str) -> str:
    """空格拼接的 token 串，供 to_tsvector('simple', ...) 使用。"""
    return " ".join(tokenize(text))


def tokens_to_tsquery_parts(text: str) -> List[str]:
    """生成可安全拼进 to_tsquery 的词项（已做简单转义）。"""
    parts: List[str] = []
    for tok in tokenize(text):
        cleaned = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff\-+./%]", "", tok)
        if not cleaned:
            continue
        cleaned = cleaned.replace("'", "''").replace("\\", "\\\\").replace(":", "\\:")
        parts.append(cleaned)
    return parts
