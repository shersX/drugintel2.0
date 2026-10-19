"""过滤关键词 DB 存储与 YAML 首次导入。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import yaml
from sqlalchemy import Text, cast, func, or_, select
from sqlalchemy.orm import Session

from backend.src.core.logger import get_logger
from backend.src.models.filter_keyword import FilterKeyword

logger = get_logger("processors.keyword_store")

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_KEYWORD_YAML = PROJECT_ROOT / "config" / "keywords.yaml"
CATEGORIES = ("靶点", "公司")


def _normalize_aliases(aliases: Sequence[str] | None, canonical: str) -> List[str]:
    seen = set()
    out: List[str] = []
    for term in list(aliases or []):
        if not isinstance(term, str):
            continue
        clean = term.strip()
        if not clean or clean == canonical or clean in seen:
            continue
        seen.add(clean)
        out.append(clean)
    return out


def import_keywords_from_yaml(
    session: Session,
    *,
    yaml_path: Path | None = None,
    only_if_empty: bool = True,
) -> int:
    """从 keywords.yaml 导入；only_if_empty 时表非空则跳过。"""
    count = session.scalar(select(func.count()).select_from(FilterKeyword)) or 0
    if only_if_empty and count > 0:
        return 0

    path = yaml_path or DEFAULT_KEYWORD_YAML
    if not path.exists():
        logger.warning("关键词 YAML 不存在: %s", path)
        return 0

    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError("keywords.yaml 根节点应为字典")

    inserted = 0
    for category in CATEGORIES:
        block = data.get(category)
        if not isinstance(block, dict):
            continue
        for canonical, aliases in block.items():
            if not isinstance(canonical, str) or not canonical.strip():
                continue
            key = canonical.strip()
            alias_list = aliases if isinstance(aliases, list) else []
            clean_aliases = _normalize_aliases(
                [a for a in alias_list if isinstance(a, str)],
                key,
            )
            existing = session.scalar(
                select(FilterKeyword).where(
                    FilterKeyword.category == category,
                    FilterKeyword.canonical == key,
                )
            )
            if existing is not None:
                continue
            session.add(
                FilterKeyword(
                    category=category,
                    canonical=key,
                    aliases=clean_aliases,
                )
            )
            inserted += 1
    if inserted:
        session.flush()
        logger.info("已从 YAML 导入过滤关键词 %s 条", inserted)
    return inserted


def lexicon_from_db(session: Session) -> Tuple[Dict[str, List[str]], Dict[str, str]]:
    """返回 (keyword_map, category_by_canonical)。"""
    rows = list(session.scalars(select(FilterKeyword)).all())
    merged: Dict[str, List[str]] = {}
    category_by_canonical: Dict[str, str] = {}
    for row in rows:
        key = (row.canonical or "").strip()
        if not key:
            continue
        terms = [key, *list(row.aliases or [])]
        deduped: List[str] = []
        seen = set()
        for t in terms:
            if not isinstance(t, str):
                continue
            clean = t.strip()
            if not clean or clean in seen:
                continue
            seen.add(clean)
            deduped.append(clean)
        if not deduped:
            continue
        merged[key] = deduped
        category_by_canonical[key] = row.category or "未分类"
    return merged, category_by_canonical


def list_keywords(
    session: Session,
    *,
    category: Optional[str] = None,
    q: str = "",
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    page = max(1, page)
    page_size = max(1, min(100, page_size))
    stmt = select(FilterKeyword)
    if category in CATEGORIES:
        stmt = stmt.where(FilterKeyword.category == category)
    q = (q or "").strip()
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                FilterKeyword.canonical.ilike(like),
                cast(FilterKeyword.aliases, Text).ilike(like),
            )
        )
    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(
        session.scalars(
            stmt.order_by(FilterKeyword.category, FilterKeyword.canonical)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return {
        "total": int(total),
        "page": page,
        "page_size": page_size,
        "items": [keyword_to_dict(r) for r in rows],
    }


def keyword_to_dict(row: FilterKeyword) -> Dict[str, Any]:
    return {
        "id": row.id,
        "category": row.category,
        "canonical": row.canonical,
        "aliases": list(row.aliases or []),
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def create_keyword(
    session: Session,
    *,
    category: str,
    canonical: str,
    aliases: Sequence[str] | None = None,
) -> FilterKeyword:
    if category not in CATEGORIES:
        raise ValueError("分类只能是「靶点」或「公司」")
    key = (canonical or "").strip()
    if not key:
        raise ValueError("规范名不能为空")
    exists = session.scalar(
        select(FilterKeyword).where(
            FilterKeyword.category == category,
            FilterKeyword.canonical == key,
        )
    )
    if exists is not None:
        raise ValueError("同分类下规范名已存在")
    row = FilterKeyword(
        category=category,
        canonical=key,
        aliases=_normalize_aliases(aliases, key),
    )
    session.add(row)
    session.flush()
    return row


def update_keyword(
    session: Session,
    keyword_id: int,
    *,
    category: Optional[str] = None,
    canonical: Optional[str] = None,
    aliases: Optional[Sequence[str]] = None,
) -> FilterKeyword:
    row = session.get(FilterKeyword, keyword_id)
    if row is None:
        raise KeyError("关键词不存在")
    new_cat = category if category is not None else row.category
    new_key = canonical.strip() if canonical is not None else row.canonical
    if new_cat not in CATEGORIES:
        raise ValueError("分类只能是「靶点」或「公司」")
    if not new_key:
        raise ValueError("规范名不能为空")
    clash = session.scalar(
        select(FilterKeyword).where(
            FilterKeyword.category == new_cat,
            FilterKeyword.canonical == new_key,
            FilterKeyword.id != keyword_id,
        )
    )
    if clash is not None:
        raise ValueError("同分类下规范名已存在")
    row.category = new_cat
    row.canonical = new_key
    if aliases is not None:
        row.aliases = _normalize_aliases(aliases, new_key)
    session.flush()
    return row


def delete_keyword(session: Session, keyword_id: int) -> None:
    row = session.get(FilterKeyword, keyword_id)
    if row is None:
        raise KeyError("关键词不存在")
    session.delete(row)
    session.flush()
