"""从 docs/DrugIntel_pipeline_seed_data.csv 幂等导入展示用管线资产。"""

from __future__ import annotations

import csv
from pathlib import Path

from sqlalchemy import select

from backend.src.core.logger import get_logger
from backend.src.db.session import session_scope
from backend.src.models.pipeline import PipelineAsset
from backend.src.pipeline_intel.normalize import (
    normalize_indication,
    normalize_modality,
    normalize_stage,
    normalize_target,
)
from backend.src.pipeline_intel.upsert import _ensure_company, _ensure_drug

logger = get_logger("pipeline_intel.seed")

# 已知英文 developer → 中文展示名（幂等回填 name_zh）
COMPANY_NAME_ZH: dict[str, str] = {
    "Novo Nordisk": "诺和诺德",
    "Eli Lilly": "礼来",
    "Sanofi": "赛诺菲",
    "Regeneron": "再生元",
    "Eisai": "卫材",
    "Biogen": "渤健",
    "Sanofi / Regeneron": "赛诺菲 / 再生元",
    "Eisai / Biogen": "卫材 / 渤健",
    "Simcere": "先声药业",
}


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _csv_path() -> Path:
    return _project_root() / "docs" / "DrugIntel_pipeline_seed_data.csv"


def _map_stage(stage_code: str, highest_stage: str) -> str:
    code = (stage_code or "").strip().upper().replace(" ", "").replace("-", "")
    aliases = {
        "PHASE1": "phase1",
        "PHASE2": "phase2",
        "PHASE3": "phase3",
        "MARKETED": "approved",
        "APPROVED": "approved",
        "PRECLINICAL": "preclinical",
        "NDA": "nda",
        "BLA": "nda",
    }
    if code in aliases:
        return aliases[code]
    return normalize_stage(highest_stage or stage_code)


def seed_company_name_zh() -> None:
    """对已有 companies 按 name / name_en 回填 name_zh。"""
    from backend.src.models.entities import Company

    updated = 0
    with session_scope() as session:
        rows = list(session.scalars(select(Company)).all())
        for row in rows:
            if (row.name_zh or "").strip():
                continue
            zh = COMPANY_NAME_ZH.get(row.name) or COMPANY_NAME_ZH.get(row.name_en or "")
            if zh:
                row.name_zh = zh
                updated += 1
            elif row.name_en and COMPANY_NAME_ZH.get(row.name_en):
                row.name_zh = COMPANY_NAME_ZH[row.name_en]
                updated += 1
        if updated:
            logger.info("已回填公司中文名 %s 条", updated)


def seed_pipeline_demo_assets() -> None:
    path = _csv_path()
    if not path.is_file():
        logger.warning("管线种子 CSV 不存在，跳过: %s", path)
        return

    inserted = 0
    skipped = 0
    with session_scope() as session:
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            for raw in reader:
                asset_name = (raw.get("asset_name") or "").strip()
                if not asset_name:
                    continue
                developer = (raw.get("developer") or "").strip()
                zh = COMPANY_NAME_ZH.get(developer)
                company = _ensure_company(session, developer, name_zh=zh)
                drug = _ensure_drug(
                    session,
                    name=asset_name,
                    generic_name=(raw.get("generic_name") or "").strip() or None,
                    mechanism=None,
                )
                indication = normalize_indication(raw.get("indication") or "")
                region = ""
                existing = session.scalar(
                    select(PipelineAsset).where(
                        PipelineAsset.company_id == company.id,
                        PipelineAsset.drug_id == drug.id,
                        PipelineAsset.indication == indication,
                        PipelineAsset.region == region,
                    )
                )
                if existing is not None:
                    skipped += 1
                    continue
                stage = _map_stage(raw.get("stage_code") or "", raw.get("highest_stage") or "")
                modality = normalize_modality(raw.get("modality") or "")
                target = normalize_target(raw.get("target") or "")
                source_url = (raw.get("source_url") or "").strip()[:500] or None
                session.add(
                    PipelineAsset(
                        company_id=company.id,
                        drug_id=drug.id,
                        indication=indication,
                        therapeutic_area=None,
                        target=target,
                        modality=modality,
                        current_stage=stage,
                        region=region,
                        status="active",
                        review_status="auto",
                        manual_fields=[],
                        source_url=source_url,
                    )
                )
                inserted += 1
    logger.info("管线种子导入完成: inserted=%s skipped=%s", inserted, skipped)
