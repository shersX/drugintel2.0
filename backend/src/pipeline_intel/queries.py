"""管线查询 / 聚合 / CRUD API 用。"""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from backend.src.models.entities import Company, Drug, Watchlist
from backend.src.models.news import News
from backend.src.models.pipeline import (
    PipelineAsset,
    PipelineChange,
    PipelineDeal,
    PipelinePageSnapshot,
)
from backend.src.pipeline_intel.normalize import (
    display_company_name,
    STAGE_BAR_ORDER,
    modality_label,
    normalize_indication,
    normalize_modality,
    normalize_stage,
    normalize_target,
    stage_label,
)
from backend.src.pipeline_intel.upsert import _ensure_company, _ensure_drug, apply_manual_patch


def _asset_dict(session: Session, row: PipelineAsset) -> Dict[str, Any]:
    drug = session.get(Drug, row.drug_id)
    company = session.get(Company, row.company_id)
    return {
        "id": row.id,
        "company_id": row.company_id,
        "company_name": display_company_name(company),
        "company_name_en": (company.name_en or None) if company else None,
        "drug_id": row.drug_id,
        "drug_name": drug.name if drug else None,
        "generic_name": drug.generic_name if drug else None,
        "mechanism": drug.mechanism_of_action if drug else None,
        "indication": row.indication,
        "therapeutic_area": row.therapeutic_area,
        "target": row.target,
        "modality": row.modality or "unknown",
        "modality_label": modality_label(row.modality or "unknown"),
        "current_stage": row.current_stage,
        "stage_label": stage_label(row.current_stage),
        "region": row.region,
        "status": row.status,
        "review_status": row.review_status or "auto",
        "manual_fields": list(row.manual_fields or []),
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
        "source_url": row.source_url,
        "last_seen_at": row.last_seen_at.isoformat() if row.last_seen_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _parse_stages(stages: str) -> List[str]:
    if not stages:
        return []
    return [s.strip() for s in stages.split(",") if s.strip()]


def _watched_names(session: Session, user_id: Optional[int]) -> set[str]:
    if not user_id:
        return set()
    rows = session.scalars(
        select(Watchlist).where(Watchlist.user_id == user_id, Watchlist.enabled.is_(True))
    ).all()
    return {(r.entity_name or "").strip().lower() for r in rows if (r.entity_name or "").strip()}


def list_assets(
    session: Session,
    *,
    q: str = "",
    target: str = "",
    indication: str = "",
    company: str = "",
    stages: str = "",
    stage: str = "",
    modality: str = "",
    status: str = "active",
    watched_only: bool = False,
    user_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    stmt = (
        select(PipelineAsset, Drug, Company)
        .join(Drug, Drug.id == PipelineAsset.drug_id)
        .join(Company, Company.id == PipelineAsset.company_id)
    )
    if status:
        stmt = stmt.where(PipelineAsset.status == status)
    stage_list = _parse_stages(stages) or ([stage] if stage else [])
    if stage_list:
        stmt = stmt.where(PipelineAsset.current_stage.in_(stage_list))
    if modality:
        stmt = stmt.where(PipelineAsset.modality == modality)
    if target.strip():
        stmt = stmt.where(PipelineAsset.target.ilike(f"%{target.strip()}%"))
    if indication.strip():
        stmt = stmt.where(PipelineAsset.indication.ilike(f"%{indication.strip()}%"))
    if company.strip():
        c = f"%{company.strip()}%"
        stmt = stmt.where(
            or_(
                Company.name.ilike(c),
                Company.name_en.ilike(c),
                Company.name_zh.ilike(c),
            )
        )
    if q.strip():
        needle = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Drug.name.ilike(needle),
                PipelineAsset.indication.ilike(needle),
                Company.name.ilike(needle),
                Company.name_en.ilike(needle),
                Company.name_zh.ilike(needle),
                PipelineAsset.target.ilike(needle),
            )
        )
    stmt = stmt.order_by(PipelineAsset.updated_at.desc())
    rows = list(session.execute(stmt).all())
    items = [_asset_dict(session, r[0]) for r in rows]

    if watched_only:
        names = _watched_names(session, user_id)
        if names:
            items = [
                i
                for i in items
                if (i.get("drug_name") or "").lower() in names
                or (i.get("company_name") or "").lower() in names
                or (i.get("target") or "").lower() in names
            ]
        else:
            items = []

    total = len(items)
    start = max(0, (page - 1) * page_size)
    page_items = items[start : start + page_size]
    return {"total": total, "page": page, "page_size": page_size, "items": page_items}


def get_asset(session: Session, asset_id: int) -> Optional[Dict[str, Any]]:
    row = session.get(PipelineAsset, asset_id)
    if row is None:
        return None
    data = _asset_dict(session, row)
    changes = list(
        session.scalars(
            select(PipelineChange)
            .where(PipelineChange.asset_id == asset_id)
            .order_by(PipelineChange.id.desc())
            .limit(100)
        ).all()
    )
    data["changes"] = [_change_dict(c) for c in changes]
    deals = list(
        session.scalars(
            select(PipelineDeal)
            .where(
                or_(
                    PipelineDeal.asset_id == asset_id,
                    PipelineDeal.drug_id == row.drug_id,
                )
            )
            .order_by(PipelineDeal.id.desc())
            .limit(50)
        ).all()
    )
    data["deals"] = [_deal_dict(session, d) for d in deals]
    drug = session.get(Drug, row.drug_id)
    company = session.get(Company, row.company_id)
    data["related_news"] = _related_news(
        session,
        drug_name=drug.name if drug else "",
        company_name=display_company_name(company) or (company.name_en if company else "") or "",
    )
    return data


def create_asset(
    session: Session,
    *,
    payload: Dict[str, Any],
    actor_id: Optional[int],
) -> Dict[str, Any]:
    company_name = str(payload.get("company_name") or "").strip()
    drug_name = str(payload.get("drug_name") or "").strip()
    if not company_name or not drug_name:
        raise ValueError("company_name 与 drug_name 必填")
    company = _ensure_company(
        session,
        company_name,
        payload.get("company_name_en"),
        payload.get("company_name_zh"),
    )
    drug = _ensure_drug(
        session,
        name=drug_name,
        generic_name=str(payload.get("generic_name") or "").strip() or None,
        mechanism=str(payload.get("mechanism") or "").strip() or None,
    )
    indication = normalize_indication(str(payload.get("indication") or ""))
    region = str(payload.get("region") or "").strip()[:50]
    existing = session.scalar(
        select(PipelineAsset).where(
            PipelineAsset.company_id == company.id,
            PipelineAsset.drug_id == drug.id,
            PipelineAsset.indication == indication,
            PipelineAsset.region == region,
        )
    )
    if existing is not None:
        raise ValueError("相同公司/药物/适应症/区域的资产已存在")
    stage = normalize_stage(str(payload.get("current_stage") or payload.get("stage") or ""))
    row = PipelineAsset(
        company_id=company.id,
        drug_id=drug.id,
        indication=indication,
        therapeutic_area=(str(payload.get("therapeutic_area") or "").strip() or None),
        target=normalize_target(str(payload.get("target") or "")),
        modality=normalize_modality(str(payload.get("modality") or "")),
        current_stage=stage,
        region=region,
        status=str(payload.get("status") or "active")[:20],
        review_status="corrected",
        manual_fields=[
            "target",
            "modality",
            "current_stage",
            "indication",
            "therapeutic_area",
            "region",
            "status",
        ],
        reviewed_by=actor_id,
        source_url=(str(payload.get("source_url") or "").strip() or None),
    )
    session.add(row)
    session.flush()
    return get_asset(session, row.id) or _asset_dict(session, row)


def patch_asset(
    session: Session,
    asset_id: int,
    *,
    payload: Dict[str, Any],
    actor_id: Optional[int],
) -> Optional[Dict[str, Any]]:
    row = session.get(PipelineAsset, asset_id)
    if row is None:
        return None
    mark = bool(payload.pop("mark_reviewed", False))
    apply_manual_patch(session, row, patch=payload, actor_id=actor_id, mark_reviewed=mark)
    return get_asset(session, asset_id)


def soft_delete_asset(session: Session, asset_id: int) -> bool:
    row = session.get(PipelineAsset, asset_id)
    if row is None:
        return False
    row.status = "inactive"
    session.flush()
    return True


def list_facets(session: Session, *, status: str = "active") -> Dict[str, Any]:
    stmt = select(PipelineAsset)
    if status:
        stmt = stmt.where(PipelineAsset.status == status)
    rows = list(session.scalars(stmt).all())

    def _count(getter):
        bag: Dict[str, int] = {}
        for r in rows:
            key = getter(r) or ""
            if not key:
                continue
            bag[key] = bag.get(key, 0) + 1
        return [{"value": k, "count": v} for k, v in sorted(bag.items(), key=lambda x: (-x[1], x[0]))]

    companies = []
    for r in rows:
        c = session.get(Company, r.company_id)
        if c:
            companies.append(display_company_name(c) or c.name)
    company_bag: Dict[str, int] = {}
    for name in companies:
        company_bag[name] = company_bag.get(name, 0) + 1

    return {
        "targets": _count(lambda r: r.target),
        "indications": _count(lambda r: r.indication),
        "companies": [
            {"value": k, "count": v}
            for k, v in sorted(company_bag.items(), key=lambda x: (-x[1], x[0]))
        ],
        "modalities": [
            {"value": m["value"], "label": modality_label(m["value"]), "count": m["count"]}
            for m in _count(lambda r: r.modality or "unknown")
        ],
        "stages": [
            {"value": m["value"], "label": stage_label(m["value"]), "count": m["count"]}
            for m in _count(lambda r: r.current_stage)
        ],
    }


def analytics_target_compare(session: Session, *, target: str = "") -> Dict[str, Any]:
    stmt = (
        select(PipelineAsset, Company)
        .join(Company, Company.id == PipelineAsset.company_id)
        .where(PipelineAsset.status == "active")
    )
    if target.strip():
        stmt = stmt.where(PipelineAsset.target.ilike(f"%{target.strip()}%"))
    rows = list(session.execute(stmt).all())
    # company -> stage -> count
    matrix: Dict[str, Dict[str, int]] = {}
    targets_seen: Dict[str, int] = {}
    for asset, company in rows:
        cname = display_company_name(company) or "未知"
        stage = asset.current_stage or "unknown"
        matrix.setdefault(cname, {})
        matrix[cname][stage] = matrix[cname].get(stage, 0) + 1
        if asset.target:
            targets_seen[asset.target] = targets_seen.get(asset.target, 0) + 1

    stages = list(STAGE_BAR_ORDER) + ["nda", "partner", "unknown"]
    series = []
    for cname, stage_map in sorted(matrix.items(), key=lambda x: -sum(x[1].values()))[:8]:
        series.append(
            {
                "company": cname,
                "counts": [stage_map.get(s, 0) for s in stages],
            }
        )
    return {
        "target": target or None,
        "stages": stages,
        "stage_labels": [stage_label(s) for s in stages],
        "series": series,
        "available_targets": [
            {"value": k, "count": v}
            for k, v in sorted(targets_seen.items(), key=lambda x: (-x[1], x[0]))[:30]
        ],
    }


def analytics_competition(session: Session, *, limit: int = 10) -> Dict[str, Any]:
    clinical = {"phase1", "phase2", "phase3", "nda", "approved"}
    stmt = (
        select(PipelineAsset, Company)
        .join(Company, Company.id == PipelineAsset.company_id)
        .where(PipelineAsset.status == "active")
    )
    bag: Dict[str, Dict[str, int]] = {}
    for asset, company in session.execute(stmt).all():
        name = display_company_name(company) or "未知"
        bag.setdefault(name, {"pipeline": 0, "clinical": 0})
        bag[name]["pipeline"] += 1
        if (asset.current_stage or "") in clinical:
            bag[name]["clinical"] += 1
    ranking = sorted(bag.items(), key=lambda x: (-x[1]["pipeline"], -x[1]["clinical"], x[0]))
    return {
        "items": [
            {
                "rank": i + 1,
                "company": name,
                "pipeline_count": stats["pipeline"],
                "clinical_count": stats["clinical"],
            }
            for i, (name, stats) in enumerate(ranking[:limit])
        ]
    }


def export_assets_csv(session: Session, **filters: Any) -> str:
    data = list_assets(session, page=1, page_size=10000, **filters)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "id",
            "drug_name",
            "target",
            "indication",
            "company_name",
            "modality",
            "current_stage",
            "therapeutic_area",
            "region",
            "status",
            "review_status",
        ]
    )
    for row in data["items"]:
        writer.writerow(
            [
                row.get("id"),
                row.get("drug_name"),
                row.get("target"),
                row.get("indication"),
                row.get("company_name"),
                row.get("modality"),
                row.get("current_stage"),
                row.get("therapeutic_area"),
                row.get("region"),
                row.get("status"),
                row.get("review_status"),
            ]
        )
    return buf.getvalue()


def list_changes(
    session: Session,
    *,
    limit: int = 50,
    change_kind: str = "",
    source: str = "",
    asset_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    stmt = select(PipelineChange).order_by(PipelineChange.id.desc())
    if change_kind:
        stmt = stmt.where(PipelineChange.change_kind == change_kind)
    if source:
        stmt = stmt.where(PipelineChange.source == source)
    if asset_id is not None:
        stmt = stmt.where(PipelineChange.asset_id == asset_id)
    stmt = stmt.limit(limit)
    return [_change_dict(c) for c in session.scalars(stmt).all()]


def list_deals(session: Session, *, limit: int = 50) -> List[Dict[str, Any]]:
    rows = session.scalars(
        select(PipelineDeal).order_by(PipelineDeal.id.desc()).limit(limit)
    ).all()
    return [_deal_dict(session, d) for d in rows]


def get_snapshot(session: Session, snapshot_id: int) -> Optional[Dict[str, Any]]:
    row = session.get(PipelinePageSnapshot, snapshot_id)
    if row is None:
        return None
    return {
        "id": row.id,
        "source_url": row.source_url,
        "fetched_at": row.fetched_at.isoformat() if row.fetched_at else None,
        "image_paths": list(row.image_paths or []),
        "image_hashes": list(row.image_hashes or []),
        "status": row.status,
        "model_name": row.model_name,
        "error": row.error,
        "extract_json": row.extract_json,
        "image_count": len(row.image_paths or []),
    }


def resolve_snapshot_image(session: Session, snapshot_id: int, index: int) -> Optional[Path]:
    row = session.get(PipelinePageSnapshot, snapshot_id)
    if row is None:
        return None
    paths = list(row.image_paths or [])
    if index < 0 or index >= len(paths):
        return None
    path = Path(paths[index])
    if path.is_file():
        return path
    alt = Path.cwd() / paths[index]
    return alt if alt.is_file() else None


def _change_dict(c: PipelineChange) -> Dict[str, Any]:
    return {
        "id": c.id,
        "asset_id": c.asset_id,
        "field": c.field,
        "old_value": c.old_value,
        "new_value": c.new_value,
        "old_label": stage_label(c.old_value) if c.field == "stage" else c.old_value,
        "new_label": stage_label(c.new_value) if c.field == "stage" else c.new_value,
        "change_kind": c.change_kind,
        "source": getattr(c, "source", None) or "crawl",
        "detected_at": c.detected_at.isoformat() if c.detected_at else None,
        "snapshot_id": c.snapshot_id,
        "prev_snapshot_id": c.prev_snapshot_id,
        "drug_name": c.drug_name,
        "company_name": c.company_name,
        "indication": c.indication,
        "notified": c.notified,
    }


def _deal_dict(session: Session, d: PipelineDeal) -> Dict[str, Any]:
    drug = session.get(Drug, d.drug_id) if d.drug_id else None
    company = session.get(Company, d.company_id) if d.company_id else None
    news = session.get(News, d.news_id) if d.news_id else None
    return {
        "id": d.id,
        "news_id": d.news_id,
        "news_title": news.title if news else None,
        "company_name": display_company_name(company),
        "drug_name": drug.name if drug else None,
        "asset_id": d.asset_id,
        "deal_type": d.deal_type,
        "counterparty": d.counterparty,
        "summary": d.summary,
        "announced_on": d.announced_on,
        "source_url": d.source_url,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }


def _related_news(
    session: Session, *, drug_name: str, company_name: str, limit: int = 10
) -> List[Dict[str, Any]]:
    terms = []
    if drug_name and len(drug_name.strip()) >= 3:
        terms.append(drug_name.strip())
    if company_name and len(company_name.strip()) >= 2:
        terms.append(company_name.strip())
    if not terms:
        return []
    conds = []
    for t in terms:
        like = f"%{t}%"
        conds.append(News.title.ilike(like))
        conds.append(News.abstract.ilike(like))
    rows = session.scalars(
        select(News)
        .where(News.process_status == "ready", or_(*conds))
        .order_by(News.publish_time.desc().nulls_last())
        .limit(limit)
    ).all()
    return [
        {
            "id": n.id,
            "title": n.title,
            "publish_time": n.publish_time.isoformat() if n.publish_time else None,
            "source": n.source,
        }
        for n in rows
    ]
