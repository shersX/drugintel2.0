"""从新闻中识别与管线相关的交易/合作并入库。"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from backend.src.models.entities import Company, Drug
from backend.src.models.news import News
from backend.src.models.pipeline import PipelineAsset, PipelineDeal

_DEAL_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"授权|license|licensing", re.I), "license"),
    (re.compile(r"引进|引进许可|in[- ]?license", re.I), "license"),
    (re.compile(r"合作|collaboration|partner|联手|战略合作", re.I), "collaboration"),
    (re.compile(r"收购|并购|收购|acquisition|m&a", re.I), "acquisition"),
    (re.compile(r"转让|transfer", re.I), "transfer"),
]


def _dedupe_key(news_id: int, company_id: Optional[int], drug_id: Optional[int], deal_type: str) -> str:
    raw = f"news:{news_id}|c:{company_id or ''}|d:{drug_id or ''}|t:{deal_type}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:64]


def _detect_deal_type(text: str) -> Optional[str]:
    for pattern, code in _DEAL_PATTERNS:
        if pattern.search(text):
            return code
    return None


def _match_entities(
    session: Session, text: str
) -> Tuple[Optional[Company], Optional[Drug], Optional[PipelineAsset]]:
    """在新闻正文中匹配已知管线公司/药物。"""
    companies = list(session.scalars(select(Company)).all())
    drugs = list(session.scalars(select(Drug)).all())
    assets = list(
        session.scalars(select(PipelineAsset).where(PipelineAsset.status == "active")).all()
    )
    hit_company: Optional[Company] = None
    hit_drug: Optional[Drug] = None
    hit_asset: Optional[PipelineAsset] = None

    lower = text
    for c in companies:
        names = [c.name]
        if c.name_en:
            names.append(c.name_en)
        if c.name_zh:
            names.append(c.name_zh)
        for n in names:
            if n and len(n) >= 2 and n in lower:
                hit_company = c
                break
        if hit_company:
            break

    for d in drugs:
        if d.name and len(d.name) >= 2 and d.name in lower:
            hit_drug = d
            break
        if d.generic_name and len(d.generic_name) >= 2 and d.generic_name in lower:
            hit_drug = d
            break

    if hit_drug is not None:
        for a in assets:
            if a.drug_id == hit_drug.id:
                hit_asset = a
                if hit_company is None:
                    hit_company = session.get(Company, a.company_id)
                break
    elif hit_company is not None:
        for a in assets:
            if a.company_id == hit_company.id:
                hit_asset = a
                break

    return hit_company, hit_drug, hit_asset


def sync_deals_from_news(session: Session, *, limit: int = 500) -> Dict[str, Any]:
    """扫描 ready 新闻，写入与管线相关的交易。返回 {scanned, created, skipped}。"""
    # 无管线资产时仍可匹配公司名，但优先有资产时更有意义
    news_rows = list(
        session.scalars(
            select(News)
            .where(News.process_status == "ready")
            .order_by(News.id.desc())
            .limit(limit)
        ).all()
    )
    created = 0
    skipped = 0
    for news in news_rows:
        blob = " ".join(
            filter(
                None,
                [
                    news.title or "",
                    news.abstract or "",
                    (news.content or "")[:2000],
                ],
            )
        )
        deal_type = _detect_deal_type(blob)
        if not deal_type:
            skipped += 1
            continue
        company, drug, asset = _match_entities(session, blob)
        if company is None and drug is None and asset is None:
            skipped += 1
            continue
        if company is None and asset is not None:
            company = session.get(Company, asset.company_id)
        company_id = company.id if company else (asset.company_id if asset else None)
        drug_id = drug.id if drug else (asset.drug_id if asset else None)
        asset_id = asset.id if asset else None
        key = _dedupe_key(news.id, company_id, drug_id, deal_type)
        exists = session.scalar(select(PipelineDeal).where(PipelineDeal.dedupe_key == key))
        if exists is not None:
            skipped += 1
            continue
        announced = None
        if news.publish_time is not None:
            announced = news.publish_time.date().isoformat()
        session.add(
            PipelineDeal(
                news_id=news.id,
                company_id=company_id,
                drug_id=drug_id,
                asset_id=asset_id,
                deal_type=deal_type,
                counterparty=None,
                summary=(news.title or "")[:500],
                announced_on=announced,
                source_url=news.detail_url,
                raw={"news_id": news.id, "title": news.title},
                dedupe_key=key,
            )
        )
        created += 1
    session.flush()
    return {"scanned": len(news_rows), "created": created, "skipped": skipped}
