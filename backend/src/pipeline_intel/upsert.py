"""将视觉抽取结果对账写入资产 / 变更 / 交易。"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.src.models.entities import Company, Drug
from backend.src.models.pipeline import PipelineAsset, PipelineChange, PipelineDeal
from backend.src.pipeline_intel.normalize import (
    normalize_drug_code,
    normalize_indication,
    normalize_stage,
)


def _ensure_company(session: Session, name: str, name_en: Optional[str] = None) -> Company:
    row = session.scalar(select(Company).where(Company.name == name))
    if row is None:
        row = Company(name=name, name_en=name_en)
        session.add(row)
        session.flush()
    elif name_en and not (row.name_en or "").strip():
        row.name_en = name_en
    return row


def _ensure_drug(
    session: Session,
    *,
    name: str,
    generic_name: Optional[str],
    mechanism: Optional[str],
) -> Drug:
    display = (name or "").strip() or "UNKNOWN"
    # 按归一代号匹配已有药
    code = normalize_drug_code(display)
    rows = list(session.scalars(select(Drug)).all())
    for row in rows:
        if normalize_drug_code(row.name) == code:
            if generic_name and not row.generic_name:
                row.generic_name = generic_name[:200]
            if mechanism and not row.mechanism_of_action:
                row.mechanism_of_action = mechanism
            return row
    row = Drug(
        name=display[:200],
        generic_name=(generic_name or None),
        mechanism_of_action=mechanism or None,
    )
    session.add(row)
    session.flush()
    return row


def _asset_key(
    company_id: int, drug_id: int, indication: str, region: str
) -> Tuple[int, int, str, str]:
    return (company_id, drug_id, indication, region)


def _write_change(
    session: Session,
    *,
    asset: Optional[PipelineAsset],
    field: str,
    old_value: Optional[str],
    new_value: Optional[str],
    change_kind: str,
    snapshot_id: int,
    prev_snapshot_id: Optional[int],
    drug_name: Optional[str],
    company_name: Optional[str],
    indication: Optional[str],
    notify: bool,
) -> PipelineChange:
    row = PipelineChange(
        asset_id=asset.id if asset is not None else None,
        field=field,
        old_value=old_value,
        new_value=new_value,
        change_kind=change_kind,
        detected_at=datetime.now(timezone.utc),
        snapshot_id=snapshot_id,
        prev_snapshot_id=prev_snapshot_id,
        notified=False if notify else True,  # 不需通知的直接标已处理
        drug_name=drug_name,
        company_name=company_name,
        indication=indication,
    )
    session.add(row)
    session.flush()
    return row


def _deal_dedupe_key(
    company_id: int,
    drug_id: Optional[int],
    deal_type: str,
    counterparty: str,
    summary: str,
) -> str:
    raw = f"{company_id}|{drug_id or ''}|{deal_type}|{counterparty}|{summary}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:64]


def apply_extract(
    session: Session,
    *,
    company_name: str,
    company_name_en: Optional[str],
    source_url: str,
    extract: Dict[str, Any],
    snapshot_id: int,
    prev_snapshot_id: Optional[int],
    is_baseline: bool,
) -> Dict[str, Any]:
    """
    Diff 并写入。返回 {created, updated, removed, deals, change_ids}。
    is_baseline=True 时 created 不发邮件。
    """
    company = _ensure_company(session, company_name, company_name_en)
    now = datetime.now(timezone.utc)
    assets_in = extract.get("assets") or []
    deals_in = extract.get("deals") or []

    existing = list(
        session.scalars(
            select(PipelineAsset).where(PipelineAsset.company_id == company.id)
        ).all()
    )
    by_key = {
        _asset_key(a.company_id, a.drug_id, a.indication or "", a.region or ""): a
        for a in existing
    }
    seen_keys: set[Tuple[int, int, str, str]] = set()
    change_ids: List[int] = []
    stats = {"created": 0, "updated": 0, "removed": 0, "deals": 0}

    for item in assets_in:
        if not isinstance(item, dict):
            continue
        drug_name = str(item.get("drug_name") or "").strip()
        if not drug_name:
            continue
        indication = normalize_indication(str(item.get("indication") or ""))
        region = unicodedata_region(str(item.get("region") or ""))
        stage = normalize_stage(str(item.get("stage") or ""))
        if item.get("partner") and stage == "unknown":
            stage = "partner"
        therapeutic_area = (str(item.get("therapeutic_area") or "").strip() or None)
        drug = _ensure_drug(
            session,
            name=drug_name,
            generic_name=str(item.get("generic_name") or "").strip() or None,
            mechanism=str(item.get("mechanism") or "").strip() or None,
        )
        key = _asset_key(company.id, drug.id, indication, region)
        seen_keys.add(key)
        asset = by_key.get(key)
        if asset is None:
            asset = PipelineAsset(
                company_id=company.id,
                drug_id=drug.id,
                indication=indication,
                therapeutic_area=therapeutic_area,
                current_stage=stage,
                region=region,
                status="active",
                source_url=source_url,
                last_seen_at=now,
            )
            session.add(asset)
            session.flush()
            by_key[key] = asset
            ch = _write_change(
                session,
                asset=asset,
                field="stage",
                old_value=None,
                new_value=stage,
                change_kind="created",
                snapshot_id=snapshot_id,
                prev_snapshot_id=prev_snapshot_id,
                drug_name=drug.name,
                company_name=company.name,
                indication=indication,
                notify=not is_baseline,
            )
            change_ids.append(ch.id)
            stats["created"] += 1
            continue

        asset.last_seen_at = now
        asset.source_url = source_url
        if asset.status != "active":
            old_status = asset.status
            asset.status = "active"
            ch = _write_change(
                session,
                asset=asset,
                field="status",
                old_value=old_status,
                new_value="active",
                change_kind="updated",
                snapshot_id=snapshot_id,
                prev_snapshot_id=prev_snapshot_id,
                drug_name=drug.name,
                company_name=company.name,
                indication=indication,
                notify=True,
            )
            change_ids.append(ch.id)
            stats["updated"] += 1

        field_updates: List[Tuple[str, Optional[str], Optional[str]]] = []
        if (asset.current_stage or "") != stage:
            field_updates.append(("stage", asset.current_stage, stage))
            asset.current_stage = stage
        if (asset.therapeutic_area or "") != (therapeutic_area or ""):
            field_updates.append(
                ("therapeutic_area", asset.therapeutic_area, therapeutic_area)
            )
            asset.therapeutic_area = therapeutic_area
        for field, old, new in field_updates:
            ch = _write_change(
                session,
                asset=asset,
                field=field,
                old_value=old,
                new_value=new,
                change_kind="updated",
                snapshot_id=snapshot_id,
                prev_snapshot_id=prev_snapshot_id,
                drug_name=drug.name,
                company_name=company.name,
                indication=indication,
                notify=True,
            )
            change_ids.append(ch.id)
            stats["updated"] += 1

    # 消失
    for key, asset in by_key.items():
        if key in seen_keys:
            continue
        if asset.status == "inactive":
            continue
        drug = session.get(Drug, asset.drug_id)
        old_status = asset.status
        asset.status = "inactive"
        ch = _write_change(
            session,
            asset=asset,
            field="status",
            old_value=old_status,
            new_value="inactive",
            change_kind="removed",
            snapshot_id=snapshot_id,
            prev_snapshot_id=prev_snapshot_id,
            drug_name=drug.name if drug else None,
            company_name=company.name,
            indication=asset.indication,
            notify=True,
        )
        change_ids.append(ch.id)
        stats["removed"] += 1

    # 交易
    for item in deals_in:
        if not isinstance(item, dict):
            continue
        deal_type = str(item.get("deal_type") or "partner").strip()[:50] or "partner"
        counterparty = str(item.get("counterparty") or "").strip()[:200]
        summary = str(item.get("summary") or "").strip()
        drug_id = None
        dname = str(item.get("drug_name") or "").strip()
        if dname:
            drug = _ensure_drug(session, name=dname, generic_name=None, mechanism=None)
            drug_id = drug.id
        dedupe = _deal_dedupe_key(company.id, drug_id, deal_type, counterparty, summary)
        existing_deal = session.scalar(
            select(PipelineDeal).where(PipelineDeal.dedupe_key == dedupe)
        )
        if existing_deal is not None:
            continue
        session.add(
            PipelineDeal(
                company_id=company.id,
                drug_id=drug_id,
                deal_type=deal_type,
                counterparty=counterparty or None,
                summary=summary or None,
                source_url=source_url,
                raw=item,
                dedupe_key=dedupe,
            )
        )
        stats["deals"] += 1

    session.flush()
    return {**stats, "change_ids": change_ids, "company_id": company.id}


def unicodedata_region(text: str) -> str:
    import unicodedata

    return unicodedata.normalize("NFKC", (text or "").strip())[:50]
