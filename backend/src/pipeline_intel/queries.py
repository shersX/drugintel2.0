"""管线查询 API 用。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from backend.src.models.entities import Company, Drug
from backend.src.models.news import News
from backend.src.models.pipeline import (
    PipelineAsset,
    PipelineChange,
    PipelineDeal,
    PipelinePageSnapshot,
)
from backend.src.pipeline_intel.normalize import stage_label


def _asset_dict(session: Session, row: PipelineAsset) -> Dict[str, Any]:
    drug = session.get(Drug, row.drug_id)
    company = session.get(Company, row.company_id)
    return {
        "id": row.id,
        "company_id": row.company_id,
        "company_name": company.name if company else None,
        "drug_id": row.drug_id,
        "drug_name": drug.name if drug else None,
        "generic_name": drug.generic_name if drug else None,
        "mechanism": drug.mechanism_of_action if drug else None,
        "indication": row.indication,
        "therapeutic_area": row.therapeutic_area,
        "current_stage": row.current_stage,
        "stage_label": stage_label(row.current_stage),
        "region": row.region,
        "status": row.status,
        "source_url": row.source_url,
        "last_seen_at": row.last_seen_at.isoformat() if row.last_seen_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def list_assets(
    session: Session,
    *,
    q: str = "",
    stage: str = "",
    company: str = "",
    status: str = "active",
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    stmt = select(PipelineAsset)
    if status:
        stmt = stmt.where(PipelineAsset.status == status)
    if stage:
        stmt = stmt.where(PipelineAsset.current_stage == stage)
    rows = list(session.scalars(stmt.order_by(PipelineAsset.updated_at.desc())).all())
    items = [_asset_dict(session, r) for r in rows]
    if company:
        c = company.strip().lower()
        items = [i for i in items if c in (i.get("company_name") or "").lower()]
    if q:
        needle = q.strip().lower()
        items = [
            i
            for i in items
            if needle in (i.get("drug_name") or "").lower()
            or needle in (i.get("indication") or "").lower()
            or needle in (i.get("company_name") or "").lower()
        ]
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
        company_name=company.name if company else "",
    )
    return data


def list_changes(
    session: Session,
    *,
    limit: int = 50,
    change_kind: str = "",
) -> List[Dict[str, Any]]:
    stmt = select(PipelineChange).order_by(PipelineChange.id.desc()).limit(limit)
    if change_kind:
        stmt = select(PipelineChange).where(PipelineChange.change_kind == change_kind).order_by(
            PipelineChange.id.desc()
        ).limit(limit)
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
    company = session.get(Company, d.company_id)
    return {
        "id": d.id,
        "company_name": company.name if company else None,
        "drug_name": drug.name if drug else None,
        "deal_type": d.deal_type,
        "counterparty": d.counterparty,
        "summary": d.summary,
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
