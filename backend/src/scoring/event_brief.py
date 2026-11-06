"""事件簇综合摘要 + 长文研报式推演（证据以簇摘要为主，跨实体事件链）。"""

from __future__ import annotations

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.src.core.logger import get_logger
from backend.src.db.crud.news import news_ready_filter
from backend.src.llm.client import SiliconFlowClient
from backend.src.models.event import Event
from backend.src.models.news import News

logger = get_logger("scoring.event_brief")

_ROOT = Path(__file__).resolve().parents[3]
_SUMMARY_PROMPT = _ROOT / "config" / "prompts" / "event_cluster_summary.txt"
_FORECAST_PROMPT = _ROOT / "config" / "prompts" / "event_forecast_report.txt"

_CHAIN_LIMIT = 12
_ORPHAN_LIMIT = 8
_SHORT_SUMMARY = 40


def _run_coro(coro):
    """在已有/无事件循环下安全跑异步 LLM。"""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result(timeout=180)


def _read_prompt(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"缺少 prompt: {path}")
    return path.read_text(encoding="utf-8").strip()


def _as_list(values: Optional[Sequence[Any]]) -> List[str]:
    out: List[str] = []
    for x in values or []:
        s = str(x or "").strip()
        if s:
            out.append(s)
    return out


def _norm_set(values: Optional[Sequence[Any]]) -> Set[str]:
    return {str(x).strip().lower() for x in (values or []) if str(x or "").strip()}


def _overlap(a: Sequence[Any], b: Sequence[Any]) -> bool:
    return bool(_norm_set(a) & _norm_set(b))


def _chat_client() -> SiliconFlowClient:
    """事件摘要走 Analyst 槽（thinking=true）。"""
    return SiliconFlowClient.from_analyst_env()


def _member_payloads(session: Session, event_id: int) -> List[News]:
    return list(
        session.scalars(
            select(News)
            .where(News.event_id == event_id)
            .where(news_ready_filter())
            .order_by(News.publish_time.asc().nulls_last(), News.id.asc())
        ).all()
    )


def event_anchor_entities(event: Event, members: Optional[Sequence[News]] = None) -> Dict[str, List[str]]:
    products = _as_list(event.products)
    drugs: List[str] = []
    orgs = _as_list(event.orgs)
    if members:
        seen_d: Set[str] = set()
        for m in members:
            for d in m.drugs or []:
                key = str(d).strip().lower()
                if key and key not in seen_d:
                    seen_d.add(key)
                    drugs.append(str(d).strip())
            if not products:
                for p in m.products or []:
                    if p and p not in products:
                        products.append(p)
            for o in m.orgs or []:
                if o and o not in orgs:
                    orgs.append(o)
    return {"products": products, "drugs": drugs, "orgs": orgs}


def find_entity_event_chain(
    session: Session,
    event: Event,
    *,
    limit: int = _CHAIN_LIMIT,
) -> List[Dict[str, Any]]:
    """同 product（空则 drug）交集的其他事件簇；只返回簇级字段。"""
    members = _member_payloads(session, event.id)
    anchor = event_anchor_entities(event, members)
    keys = anchor["products"] or anchor["drugs"]
    if not keys:
        return []

    rows = list(
        session.scalars(
            select(Event)
            .where(Event.id != event.id)
            .where(Event.status == "active")
            .order_by(Event.updated_at.desc())
            .limit(200)
        ).all()
    )
    chain: List[Dict[str, Any]] = []
    key_set = _norm_set(keys)
    for row in rows:
        row_products = _as_list(row.products)
        # event 表无 drugs 列：用成员聚合或仅 products
        row_drugs: List[str] = []
        if not (key_set & _norm_set(row_products)):
            row_members = _member_payloads(session, row.id)
            for m in row_members:
                row_drugs.extend(_as_list(m.drugs))
            if not (key_set & _norm_set(row_drugs)):
                continue
        chain.append(
            {
                "id": row.id,
                "title": row.title,
                "summary": (row.summary or "")[:800],
                "story_types": row.story_types or [],
                "products": row.products or [],
                "orgs": row.orgs or [],
                "news_count": row.news_count,
                "ci_risk_score": row.ci_risk_score,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            }
        )
        if len(chain) >= limit:
            break
    return chain


def find_orphan_news(
    session: Session,
    event: Event,
    *,
    member_ids: Set[int],
    limit: int = _ORPHAN_LIMIT,
) -> List[Dict[str, Any]]:
    members = _member_payloads(session, event.id)
    anchor = event_anchor_entities(event, members)
    keys = anchor["products"] or anchor["drugs"]
    if not keys:
        return []
    key_set = _norm_set(keys)
    rows = list(
        session.scalars(
            select(News)
            .where(news_ready_filter())
            .order_by(News.publish_time.desc().nulls_last(), News.id.desc())
            .limit(120)
        ).all()
    )
    out: List[Dict[str, Any]] = []
    for row in rows:
        if row.id in member_ids or row.event_id == event.id:
            continue
        bag = _norm_set(row.products) | _norm_set(row.drugs)
        if not (bag & key_set):
            continue
        out.append(
            {
                "id": row.id,
                "title": row.title,
                "abstract_snippet": ((row.abstract or "")[:180]),
                "publish_time": row.publish_time.isoformat() if row.publish_time else None,
                "story_type": row.story_type,
            }
        )
        if len(out) >= limit:
            break
    return out


async def _llm_text(
    system: str,
    user: str,
    *,
    temperature: float = 0.2,
    enable_thinking: Optional[bool] = None,
) -> str:
    from backend.src.core.config import AnalystEnvConfig

    client = _chat_client()
    thinking = (
        AnalystEnvConfig.load().enable_thinking
        if enable_thinking is None
        else enable_thinking
    )
    text = await client.chat_completion(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        enable_thinking=thinking,
    )
    return (text or "").strip()


def synthesize_event_summary(session: Session, event: Event) -> str:
    """生成簇级综合摘要；失败回退代表篇 abstract。"""
    members = _member_payloads(session, event.id)
    fallback = ""
    if event.representative_news_id:
        rep = session.get(News, event.representative_news_id)
        if rep and rep.abstract:
            fallback = rep.abstract
    if not fallback and members:
        fallback = members[0].abstract or ""

    lines = []
    for m in members[:12]:
        lines.append(
            f"- 标题: {m.title or ''}\n  摘要: {(m.abstract or '')[:280]}\n"
            f"  类型: {m.story_type or 'other'}"
        )
    if not lines:
        event.summary = fallback or event.summary
        return event.summary or ""

    user = (
        f"事件标题候选: {event.title}\n"
        f"产品: {', '.join(event.products or [])}\n"
        f"机构: {', '.join(event.orgs or [])}\n"
        f"故事类型: {', '.join(event.story_types or [])}\n"
        f"成员新闻:\n" + "\n".join(lines)
    )
    try:
        system = _read_prompt(_SUMMARY_PROMPT)
        text = _run_coro(_llm_text(system, user, temperature=0.2))
        if text and len(text) >= 40:
            event.summary = text[:2000]
            return event.summary
    except Exception as exc:
        logger.warning("事件综合摘要失败 event=%s: %s", event.id, exc)
    event.summary = fallback or event.summary
    return event.summary or ""


def soft_match_pipeline_assets(
    session: Session,
    anchor: Dict[str, List[str]],
    *,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """只读软匹配官网管线资产；无命中则返回空（不写回进度）。"""
    from sqlalchemy import or_

    from backend.src.models.entities import Company, Drug
    from backend.src.models.pipeline import PipelineAsset
    from backend.src.scoring.ci_risk import stage_prior_pos

    names = _as_list(anchor.get("products")) + _as_list(anchor.get("drugs"))
    orgs = _as_list(anchor.get("orgs"))
    if not names and not orgs:
        return []

    clauses = []
    for n in names[:8]:
        like = f"%{n}%"
        clauses.append(Drug.name.ilike(like))
        clauses.append(Drug.generic_name.ilike(like))
    for o in orgs[:4]:
        like = f"%{o}%"
        clauses.append(Company.name.ilike(like))
        clauses.append(Company.name_en.ilike(like))
        clauses.append(Company.name_zh.ilike(like))
    if not clauses:
        return []

    rows = list(
        session.execute(
            select(PipelineAsset, Drug, Company)
            .join(Drug, Drug.id == PipelineAsset.drug_id)
            .join(Company, Company.id == PipelineAsset.company_id)
            .where(PipelineAsset.status == "active")
            .where(or_(*clauses))
            .limit(limit)
        ).all()
    )
    out: List[Dict[str, Any]] = []
    for asset, drug, company in rows:
        prior = stage_prior_pos(asset.current_stage)
        out.append(
            {
                "asset_id": asset.id,
                "drug_name": drug.name if drug else None,
                "generic_name": drug.generic_name if drug else None,
                "company_name": (company.name_zh or company.name or company.name_en)
                if company
                else None,
                "indication": asset.indication,
                "current_stage": asset.current_stage,
                "stage_prior_pos": prior.get("prior_pos"),
                "stage_prior_disclaimer": prior.get("disclaimer"),
            }
        )
    return out


def build_evidence_pack(session: Session, event: Event) -> Dict[str, Any]:
    members = _member_payloads(session, event.id)
    anchor = event_anchor_entities(event, members)
    summary = (event.summary or "").strip()
    focus: Dict[str, Any] = {
        "id": event.id,
        "title": event.title,
        "summary": summary,
        "products": anchor["products"],
        "drugs": anchor["drugs"],
        "orgs": anchor["orgs"],
        "story_types": event.story_types or [],
        "news_count": event.news_count,
        "ci_risk_score": event.ci_risk_score,
        "score_components": event.score_components,
        "burst_prob": event.burst_prob,
        "next_window_volume": (event.score_components or {}).get("next_window_volume")
        if isinstance(event.score_components, dict)
        else None,
    }
    if len(summary) < _SHORT_SUMMARY:
        rep = None
        if event.representative_news_id:
            rep = session.get(News, event.representative_news_id)
        focus["representative"] = {
            "title": (rep.title if rep else (members[0].title if members else "")),
            "abstract": (rep.abstract if rep else (members[0].abstract if members else "")) or "",
        }
        focus["member_titles"] = [m.title for m in members[:3] if m.title]

    chain = find_entity_event_chain(session, event)
    orphan: List[Dict[str, Any]] = []
    if len(chain) < 2:
        orphan = find_orphan_news(
            session, event, member_ids={m.id for m in members}
        )

    pipeline_hits: List[Dict[str, Any]] = []
    try:
        pipeline_hits = soft_match_pipeline_assets(session, anchor)
    except Exception as exc:
        logger.warning("管线软匹配失败 event=%s: %s", event.id, exc)

    gaps: List[str] = []
    if not (anchor["products"] or anchor["drugs"]):
        gaps.append("缺少 product/drug 锚点，无法可靠串联跨阶段事件")
    if len(chain) < 2:
        gaps.append("同实体事件链过短（少于 2 个相关簇）")
    if len(summary) < _SHORT_SUMMARY:
        gaps.append("焦点簇综合摘要偏短或缺失")
    if event.burst_prob is None:
        gaps.append("爆发/热度模型样本不足或未计算 burst_prob")
    if not pipeline_hits:
        gaps.append("未命中官网管线资产（仅作可选上下文，本轮不回写进度）")

    return {
        "focus_event": focus,
        "entity_event_chain": chain,
        "orphan_news": orphan,
        "pipeline_context": pipeline_hits,
        "evidence_gaps": gaps,
        "disclaimer": "情报关注/热度与叙事推演，非药物临床成功概率，非 LoA",
    }


def generate_forecast_report(
    session: Session,
    event: Event,
    *,
    force: bool = False,
) -> Dict[str, Any]:
    """兼容入口：优先返回缓存；强制时走 Analyst Agent（同步，供任务/测试）。

    线上 API 请用 agents.analyst.enqueue_event_forecast 异步入队。
    """
    if event.forecast_report and event.forecast_generated_at and not force:
        return {
            "forecast_report": event.forecast_report,
            "forecast_generated_at": event.forecast_generated_at.isoformat(),
            "forecast_evidence_meta": event.forecast_evidence_meta,
            "cached": True,
        }

    from backend.src.agents.analyst import AnalystAgent

    if not (event.summary or "").strip() or len((event.summary or "").strip()) < _SHORT_SUMMARY:
        synthesize_event_summary(session, event)
        session.flush()
    eid = event.id
    session.flush()
    # 释放长持有：Agent 内部自管短 session；此处仅回写
    payload = _run_coro(AnalystAgent().run_forecast(eid))
    event.forecast_report = payload["forecast_report"]
    event.forecast_evidence_meta = payload["forecast_evidence_meta"]
    event.forecast_generated_at = datetime.now(timezone.utc)
    event.forecast_status = "ready"
    event.forecast_error = None
    session.flush()
    return {
        "forecast_report": event.forecast_report,
        "forecast_generated_at": event.forecast_generated_at.isoformat(),
        "forecast_evidence_meta": event.forecast_evidence_meta,
        "cached": False,
    }


def refresh_summaries_for_events(session: Session, event_ids: Sequence[int]) -> int:
    n = 0
    for eid in event_ids:
        event = session.get(Event, int(eid))
        if event is None:
            continue
        try:
            synthesize_event_summary(session, event)
            n += 1
        except Exception as exc:
            logger.warning("刷新事件摘要失败 id=%s: %s", eid, exc)
    session.flush()
    return n
