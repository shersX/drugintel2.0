"""实体字符串预处理与 alias → canonical 索引。"""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, Iterable, List, Optional, Tuple

_TRADEMARK = re.compile(r"[®™©]")
_SPACE = re.compile(r"\s+")


def preprocess(text: str) -> str:
    if not text:
        return ""
    s = unicodedata.normalize("NFKC", str(text)).strip().lower()
    s = _TRADEMARK.sub("", s)
    s = s.replace("　", " ")
    s = _SPACE.sub(" ", s).strip()
    return s


class AliasIndex:
    """(entity_type, alias_norm) -> (canonical, entity_id, status)."""

    def __init__(self) -> None:
        self._map: Dict[Tuple[str, str], Tuple[str, int, str]] = {}

    def clear(self) -> None:
        self._map.clear()

    def add(
        self,
        entity_type: str,
        canonical: str,
        aliases: Iterable[str],
        *,
        entity_id: int,
        status: str,
    ) -> None:
        et = (entity_type or "").strip().lower()
        can = preprocess(canonical)
        if not et or not can:
            return
        self._map[(et, can)] = (can, entity_id, status)
        for raw in aliases or []:
            a = preprocess(str(raw))
            if a:
                self._map[(et, a)] = (can, entity_id, status)

    def resolve(
        self, entity_type: str, raw: str, *, allow_pending: bool = False
    ) -> Optional[str]:
        et = (entity_type or "").strip().lower()
        key = preprocess(raw)
        if not et or not key:
            return None
        hit = self._map.get((et, key))
        if hit is None:
            return None
        can, _eid, status = hit
        if status == "active":
            return can
        if allow_pending and status == "pending":
            return can
        return None

    def resolve_many(
        self,
        entity_type: str,
        values: Iterable[str],
        *,
        allow_pending: bool = False,
    ) -> Tuple[List[str], List[str]]:
        """返回 (canonicals, unresolved_raw)."""
        out: List[str] = []
        unresolved: List[str] = []
        seen = set()
        for raw in values or []:
            text = str(raw or "").strip()
            if not text:
                continue
            can = self.resolve(entity_type, text, allow_pending=allow_pending)
            if can:
                if can not in seen:
                    seen.add(can)
                    out.append(can)
            else:
                unresolved.append(text)
        return out, unresolved
