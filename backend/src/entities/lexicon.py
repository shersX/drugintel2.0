"""实体词典 CRUD、种子导入、归一化回流。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.src.core.logger import get_logger
from backend.src.entities.normalize import AliasIndex, preprocess
from backend.src.models.entity_lexicon import EntityLexicon
from backend.src.models.filter_keyword import FilterKeyword

logger = get_logger("entities.lexicon")

ENTITY_TYPES = ("product", "drug", "org", "target", "indication")
PENDING_PROMOTE_SEEN = 3

_SEED_PATH = Path(__file__).resolve().parents[3] / "config" / "entity_seed.yaml"


def _public(row: EntityLexicon) -> Dict[str, Any]:
    return {
        "id": row.id,
        "entity_type": row.entity_type,
        "canonical": row.canonical,
        "aliases": list(row.aliases or []),
        "source": row.source,
        "confidence": row.confidence,
        "status": row.status,
        "merged_into_id": row.merged_into_id,
        "seen_count": row.seen_count,
        "created_at": str(row.created_at) if row.created_at else None,
        "updated_at": str(row.updated_at) if row.updated_at else None,
    }


def load_alias_index(session: Session, *, include_pending: bool = False) -> AliasIndex:
    idx = AliasIndex()
    statuses = ["active"]
    if include_pending:
        statuses.append("pending")
    rows = session.scalars(
        select(EntityLexicon).where(EntityLexicon.status.in_(statuses))
    ).all()
    for row in rows:
        idx.add(
            row.entity_type,
            row.canonical,
            row.aliases or [],
            entity_id=row.id,
            status=row.status,
        )
    return idx


def list_entities(
    session: Session,
    *,
    entity_type: Optional[str] = None,
    status: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> Dict[str, Any]:
    stmt = select(EntityLexicon).order_by(EntityLexicon.updated_at.desc())
    if entity_type:
        stmt = stmt.where(EntityLexicon.entity_type == entity_type)
    if status:
        stmt = stmt.where(EntityLexicon.status == status)
    term = (q or "").strip().lower()
    rows = list(session.scalars(stmt).all())
    if term:
        filtered = []
        for row in rows:
            blob = " ".join(
                [row.canonical or "", " ".join(row.aliases or [])]
            ).lower()
            if term in blob:
                filtered.append(row)
        rows = filtered
    total = len(rows)
    page = rows[offset : offset + limit]
    return {"total": total, "items": [_public(r) for r in page]}


def get_entity(session: Session, entity_id: int) -> Optional[EntityLexicon]:
    return session.get(EntityLexicon, entity_id)


def create_entity(
    session: Session,
    *,
    entity_type: str,
    canonical: str,
    aliases: Optional[Sequence[str]] = None,
    source: str = "manual",
    status: str = "active",
    confidence: float = 1.0,
) -> EntityLexicon:
    et = (entity_type or "").strip().lower()
    if et not in ENTITY_TYPES:
        raise ValueError(f"不支持的 entity_type: {et}")
    can = preprocess(canonical)
    if not can:
        raise ValueError("canonical 不能为空")
    alias_list = sorted({preprocess(a) for a in (aliases or []) if preprocess(a)} - {can})
    existing = session.scalar(
        select(EntityLexicon).where(
            EntityLexicon.entity_type == et,
            EntityLexicon.canonical == can,
        )
    )
    if existing:
        merged = set(existing.aliases or []) | set(alias_list)
        existing.aliases = sorted(merged)
        if status == "active" and existing.status == "pending":
            existing.status = "active"
        session.flush()
        return existing
    row = EntityLexicon(
        entity_type=et,
        canonical=can,
        aliases=alias_list,
        source=source,
        status=status,
        confidence=confidence,
        seen_count=1,
    )
    session.add(row)
    session.flush()
    return row


def update_entity(
    session: Session,
    entity_id: int,
    *,
    canonical: Optional[str] = None,
    aliases: Optional[Sequence[str]] = None,
    status: Optional[str] = None,
) -> EntityLexicon:
    row = session.get(EntityLexicon, entity_id)
    if row is None:
        raise ValueError("实体不存在")
    if canonical is not None:
        can = preprocess(canonical)
        if not can:
            raise ValueError("canonical 不能为空")
        row.canonical = can
    if aliases is not None:
        can = row.canonical
        row.aliases = sorted({preprocess(a) for a in aliases if preprocess(a)} - {can})
    if status is not None:
        row.status = status
    session.flush()
    return row


def merge_entities(session: Session, keep_id: int, drop_id: int) -> EntityLexicon:
    keep = session.get(EntityLexicon, keep_id)
    drop = session.get(EntityLexicon, drop_id)
    if keep is None or drop is None:
        raise ValueError("实体不存在")
    if keep.entity_type != drop.entity_type:
        raise ValueError("只能合并同类型实体")
    aliases = set(keep.aliases or [])
    aliases.add(drop.canonical)
    aliases |= set(drop.aliases or [])
    aliases.discard(keep.canonical)
    keep.aliases = sorted(aliases)
    keep.seen_count = int(keep.seen_count or 0) + int(drop.seen_count or 0)
    drop.status = "merged"
    drop.merged_into_id = keep.id
    session.flush()
    return keep


def upsert_pending(
    session: Session,
    *,
    entity_type: str,
    raw: str,
    source: str = "llm",
) -> Optional[EntityLexicon]:
    et = (entity_type or "").strip().lower()
    can = preprocess(raw)
    if et not in ENTITY_TYPES or not can:
        return None
    row = session.scalar(
        select(EntityLexicon).where(
            EntityLexicon.entity_type == et,
            EntityLexicon.canonical == can,
        )
    )
    if row is None:
        # 也可能命中已有 alias
        for candidate in session.scalars(
            select(EntityLexicon).where(EntityLexicon.entity_type == et)
        ).all():
            alias_set = {preprocess(a) for a in (candidate.aliases or [])}
            if can == candidate.canonical or can in alias_set:
                candidate.seen_count = int(candidate.seen_count or 0) + 1
                if (
                    candidate.status == "pending"
                    and candidate.seen_count >= PENDING_PROMOTE_SEEN
                ):
                    candidate.status = "active"
                session.flush()
                return candidate
        row = EntityLexicon(
            entity_type=et,
            canonical=can,
            aliases=[],
            source=source,
            status="pending",
            confidence=0.5,
            seen_count=1,
        )
        session.add(row)
        session.flush()
        return row
    row.seen_count = int(row.seen_count or 0) + 1
    if row.status == "pending" and row.seen_count >= PENDING_PROMOTE_SEEN:
        row.status = "active"
    session.flush()
    return row


def normalize_and_feedback(
    session: Session,
    *,
    products: Iterable[str] = (),
    drugs: Iterable[str] = (),
    orgs: Iterable[str] = (),
    targets: Iterable[str] = (),
    indications: Iterable[str] = (),
) -> Dict[str, Any]:
    """归一化到 canonical，未命中的回流 pending；强路径只用 active。"""
    idx = load_alias_index(session, include_pending=False)
    result: Dict[str, Any] = {
        "products": [],
        "drugs": [],
        "orgs": [],
        "targets": [],
        "indications": [],
        "entity_raw": {
            "products": list(products or []),
            "drugs": list(drugs or []),
            "orgs": list(orgs or []),
            "targets": list(targets or []),
            "indications": list(indications or []),
        },
    }
    mapping = (
        ("product", "products", products),
        ("drug", "drugs", drugs),
        ("org", "orgs", orgs),
        ("target", "targets", targets),
        ("indication", "indications", indications),
    )
    for et, key, values in mapping:
        cans, unresolved = idx.resolve_many(et, values, allow_pending=False)
        result[key] = cans
        for raw in unresolved:
            # 快照里保留 raw 字符串（便于展示），同时 pending 回流
            if preprocess(raw) not in cans:
                result[key].append(preprocess(raw))
            upsert_pending(session, entity_type=et, raw=raw, source="llm")
        # 去重保序
        seen = set()
        deduped = []
        for x in result[key]:
            if x and x not in seen:
                seen.add(x)
                deduped.append(x)
        result[key] = deduped
    return result


def import_from_keywords(session: Session) -> Dict[str, int]:
    """公司→org，靶点→target。"""
    cat_map = {"公司": "org", "靶点": "target", "company": "org", "target": "target"}
    created = updated = 0
    rows = session.scalars(select(FilterKeyword)).all()
    for kw in rows:
        et = cat_map.get((kw.category or "").strip())
        if not et:
            continue
        before = session.scalar(
            select(EntityLexicon).where(
                EntityLexicon.entity_type == et,
                EntityLexicon.canonical == preprocess(kw.canonical),
            )
        )
        row = create_entity(
            session,
            entity_type=et,
            canonical=kw.canonical,
            aliases=kw.aliases or [],
            source="seed",
            status="active",
        )
        if before is None and row.seen_count == 1 and row.source == "seed":
            created += 1
        else:
            updated += 1
    return {"created": created, "updated": updated}


def import_seed_yaml(session: Session, path: Optional[Path] = None) -> Dict[str, int]:
    seed_path = path or _SEED_PATH
    if not seed_path.exists():
        logger.warning("实体种子文件不存在: %s", seed_path)
        return {"created": 0, "updated": 0}
    data = yaml.safe_load(seed_path.read_text(encoding="utf-8")) or {}
    type_map = {
        "orgs": "org",
        "products": "product",
        "drugs": "drug",
        "targets": "target",
        "indications": "indication",
    }
    created = updated = 0
    for key, et in type_map.items():
        for item in data.get(key) or []:
            can = (item or {}).get("canonical") or ""
            aliases = (item or {}).get("aliases") or []
            before = session.scalar(
                select(EntityLexicon).where(
                    EntityLexicon.entity_type == et,
                    EntityLexicon.canonical == preprocess(can),
                )
            )
            create_entity(
                session,
                entity_type=et,
                canonical=can,
                aliases=aliases,
                source="seed",
                status="active",
            )
            if before is None:
                created += 1
            else:
                updated += 1
    return {"created": created, "updated": updated}


def seed_all(session: Session) -> Dict[str, Any]:
    a = import_from_keywords(session)
    b = import_seed_yaml(session)
    return {"from_keywords": a, "from_yaml": b}
