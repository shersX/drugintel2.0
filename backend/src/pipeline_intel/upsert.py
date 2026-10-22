"""将视觉抽取结果对账写入资产 / 变更（交易由新闻模块写入）。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.src.models.entities import Company, Drug
from backend.src.models.pipeline import PipelineAsset, PipelineChange
from backend.src.pipeline_intel.normalize import (
    company_name_key,
    display_company_name,
    looks_cjk,
    normalize_drug_code,
    normalize_indication,
    normalize_modality,
    normalize_stage,
    normalize_target,
)


def _ensure_company(
    session: Session,
    name: str,
    name_en: Optional[str] = None,
    name_zh: Optional[str] = None,
) -> Company:
    raw = (name or "").strip()[:200] or "Unknown"
    en = (name_en or "").strip()[:200] or None
    zh = (name_zh or "").strip()[:200] or None
    if zh is None and looks_cjk(raw):
        zh = raw
    if en is None and raw and not looks_cjk(raw):
        en = raw

    keys = {company_name_key(x) for x in (raw, en, zh) if x}
    row: Optional[Company] = None
    for cand in session.scalars(select(Company)).all():
        fields = {company_name_key(f) for f in (cand.name, cand.name_en, cand.name_zh) if f}
        if keys & fields:
            row = cand
            break

    if row is None:
        row = Company(name=raw, name_en=en, name_zh=zh)
        session.add(row)
        session.flush()
    else:
        if en and not (row.name_en or "").strip():
            row.name_en = en
        if zh and not (row.name_zh or "").strip():
            row.name_zh = zh
    return row


def _ensure_drug(
    session: Session,
    *,
    name: str,
    generic_name: Optional[str],
    mechanism: Optional[str],
) -> Drug:
    display = (name or "").strip() or "UNKNOWN"
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


def _manual_set(asset: PipelineAsset) -> Set[str]:
    raw = asset.manual_fields or []
    if not isinstance(raw, list):
        return set()
    return {str(x) for x in raw}


def _locked(asset: PipelineAsset, field: str) -> bool:
    return field in _manual_set(asset)


def _write_change(
    session: Session,
    *,
    asset: Optional[PipelineAsset],
    field: str,
    old_value: Optional[str],
    new_value: Optional[str],
    change_kind: str,
    snapshot_id: Optional[int],
    prev_snapshot_id: Optional[int],
    drug_name: Optional[str],
    company_name: Optional[str],
    indication: Optional[str],
    notify: bool,
    source: str = "crawl",
) -> PipelineChange:
    row = PipelineChange(
        asset_id=asset.id if asset is not None else None,
        field=field,
        old_value=old_value,
        new_value=new_value,
        change_kind=change_kind,
        source=source,
        detected_at=datetime.now(timezone.utc),
        snapshot_id=snapshot_id,
        prev_snapshot_id=prev_snapshot_id,
        notified=False if notify else True,
        drug_name=drug_name,
        company_name=company_name,
        indication=indication,
    )
    session.add(row)
    session.flush()
    return row


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
    人工锁定字段（manual_fields）不被覆盖。
    """
    company = _ensure_company(session, company_name, company_name_en)
    now = datetime.now(timezone.utc)
    assets_in = extract.get("assets") or []

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
        region = _normalize_region(str(item.get("region") or ""))
        stage = normalize_stage(str(item.get("stage") or ""))
        if item.get("partner") and stage == "unknown":
            stage = "partner"
        therapeutic_area = (str(item.get("therapeutic_area") or "").strip() or None)
        target = normalize_target(str(item.get("target") or item.get("mechanism") or ""))
        modality = normalize_modality(str(item.get("modality") or ""))
        mechanism = str(item.get("mechanism") or "").strip() or None
        drug = _ensure_drug(
            session,
            name=drug_name,
            generic_name=str(item.get("generic_name") or "").strip() or None,
            mechanism=mechanism,
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
                target=target,
                modality=modality,
                current_stage=stage,
                region=region,
                status="active",
                review_status="auto",
                manual_fields=[],
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
                company_name=display_company_name(company),
                indication=indication,
                notify=not is_baseline,
                source="crawl",
            )
            change_ids.append(ch.id)
            stats["created"] += 1
            continue

        asset.last_seen_at = now
        if not _locked(asset, "source_url"):
            asset.source_url = source_url

        if asset.status != "active" and not _locked(asset, "status"):
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
                company_name=display_company_name(company),
                indication=indication,
                notify=True,
                source="crawl",
            )
            change_ids.append(ch.id)
            stats["updated"] += 1

        candidates: List[Tuple[str, Optional[str], Optional[str]]] = []
        if (asset.current_stage or "") != stage:
            candidates.append(("current_stage", asset.current_stage, stage))
        if (asset.therapeutic_area or "") != (therapeutic_area or ""):
            candidates.append(("therapeutic_area", asset.therapeutic_area, therapeutic_area))
        if (asset.target or "") != (target or ""):
            candidates.append(("target", asset.target, target))
        if (asset.modality or "unknown") != modality:
            candidates.append(("modality", asset.modality, modality))
        if (asset.region or "") != region and region:
            candidates.append(("region", asset.region, region))

        for field, old, new in candidates:
            if _locked(asset, field):
                continue
            setattr(asset, field, new)
            change_field = "stage" if field == "current_stage" else field
            ch = _write_change(
                session,
                asset=asset,
                field=change_field,
                old_value=old,
                new_value=new,
                change_kind="updated",
                snapshot_id=snapshot_id,
                prev_snapshot_id=prev_snapshot_id,
                drug_name=drug.name,
                company_name=display_company_name(company),
                indication=indication,
                notify=True,
                source="crawl",
            )
            change_ids.append(ch.id)
            stats["updated"] += 1

    for key, asset in by_key.items():
        if key in seen_keys:
            continue
        if asset.status == "inactive":
            continue
        if _locked(asset, "status"):
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
            company_name=display_company_name(company),
            indication=asset.indication,
            notify=True,
            source="crawl",
        )
        change_ids.append(ch.id)
        stats["removed"] += 1

    session.flush()
    return {**stats, "change_ids": change_ids, "company_id": company.id}


def apply_manual_patch(
    session: Session,
    asset: PipelineAsset,
    *,
    patch: Dict[str, Any],
    actor_id: Optional[int],
    mark_reviewed: bool = False,
) -> Dict[str, Any]:
    """人工校对：更新字段、写入 manual_fields、记 change(source=manual)。"""
    company = session.get(Company, asset.company_id)
    drug = session.get(Drug, asset.drug_id)
    locked = _manual_set(asset)
    change_ids: List[int] = []
    field_map = {
        "indication": "indication",
        "therapeutic_area": "therapeutic_area",
        "target": "target",
        "modality": "modality",
        "current_stage": "current_stage",
        "stage": "current_stage",
        "region": "region",
        "status": "status",
        "source_url": "source_url",
    }
    for key, attr in field_map.items():
        if key not in patch and attr not in patch:
            continue
        raw = patch[key] if key in patch else patch[attr]
        if attr == "current_stage":
            new_val = normalize_stage(str(raw or ""))
        elif attr == "modality":
            new_val = normalize_modality(str(raw or ""))
        elif attr == "target":
            new_val = normalize_target(str(raw) if raw is not None else None)
        elif attr == "indication":
            new_val = normalize_indication(str(raw or ""))
        elif attr == "region":
            new_val = _normalize_region(str(raw or ""))
        elif attr == "therapeutic_area":
            new_val = (str(raw or "").strip() or None)
        elif attr == "status":
            new_val = str(raw or "active").strip()[:20] or "active"
        else:
            new_val = (str(raw).strip()[:500] if raw is not None else None) or None

        old_val = getattr(asset, attr)
        old_s = "" if old_val is None else str(old_val)
        new_s = "" if new_val is None else str(new_val)
        if old_s == new_s:
            locked.add(attr)
            continue
        setattr(asset, attr, new_val)
        locked.add(attr)
        ch = _write_change(
            session,
            asset=asset,
            field="stage" if attr == "current_stage" else attr,
            old_value=old_s or None,
            new_value=new_s or None,
            change_kind="updated",
            snapshot_id=None,
            prev_snapshot_id=None,
            drug_name=drug.name if drug else None,
            company_name=display_company_name(company),
            indication=asset.indication,
            notify=False,
            source="manual",
        )
        change_ids.append(ch.id)

    if "generic_name" in patch and drug is not None:
        g = str(patch.get("generic_name") or "").strip()[:200] or None
        if (drug.generic_name or None) != g:
            drug.generic_name = g
    if "mechanism" in patch and drug is not None:
        m = str(patch.get("mechanism") or "").strip() or None
        if (drug.mechanism_of_action or None) != m:
            drug.mechanism_of_action = m

    asset.manual_fields = sorted(locked)
    asset.review_status = "reviewed" if mark_reviewed else "corrected"
    asset.reviewed_at = datetime.now(timezone.utc)
    asset.reviewed_by = actor_id
    session.flush()
    return {"change_ids": change_ids, "manual_fields": list(asset.manual_fields)}


def _normalize_region(text: str) -> str:
    import unicodedata

    return unicodedata.normalize("NFKC", (text or "").strip())[:50]
