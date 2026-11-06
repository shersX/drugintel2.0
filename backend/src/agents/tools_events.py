"""事件研报只读工具（短 session）。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import func, select

from backend.src.db.session import session_scope
from backend.src.models.entities import Company
from backend.src.models.event import Event
from backend.src.models.news import News
from backend.src.models.pipeline import PipelineAsset, PipelineChange, PipelineDeal
from backend.src.scoring.event_brief import (
    event_anchor_entities,
    find_entity_event_chain,
    find_orphan_news,
    soft_match_pipeline_assets,
    _member_payloads,
)


def get_event_card(event_id: int) -> Dict[str, Any]:
    with session_scope() as session:
        event = session.get(Event, int(event_id))
        if event is None:
            return {"error": "event not found"}
        members = _member_payloads(session, event.id)
        anchor = event_anchor_entities(event, members)
        return {
            "id": event.id,
            "title": event.title,
            "summary": (event.summary or "")[:1200],
            "products": anchor["products"],
            "drugs": anchor["drugs"],
            "orgs": anchor["orgs"],
            "story_types": event.story_types or [],
            "news_count": event.news_count,
            "ci_risk_score": event.ci_risk_score,
            "burst_prob": event.burst_prob,
            "score_components": event.score_components,
        }


def list_entity_event_chain_tool(event_id: int, limit: int = 12) -> Dict[str, Any]:
    with session_scope() as session:
        event = session.get(Event, int(event_id))
        if event is None:
            return {"error": "event not found", "items": []}
        chain = find_entity_event_chain(session, event, limit=min(20, max(1, int(limit))))
        return {"items": chain, "count": len(chain)}


def get_event_timeline(event_id: int, limit: int = 12) -> Dict[str, Any]:
    with session_scope() as session:
        from backend.src.db.crud.news import news_ready_filter

        rows = list(
            session.scalars(
                select(News)
                .where(News.event_id == int(event_id))
                .where(news_ready_filter())
                .order_by(News.publish_time.asc().nulls_last(), News.id.asc())
                .limit(min(30, max(1, int(limit))))
            ).all()
        )
        return {
            "items": [
                {
                    "id": m.id,
                    "title": m.title,
                    "abstract_snippet": ((m.abstract or "")[:180]),
                    "story_type": m.story_type,
                    "publish_time": m.publish_time.isoformat() if m.publish_time else None,
                    "products": m.products or [],
                    "orgs": m.orgs or [],
                }
                for m in rows
            ]
        }


def list_orphan_news_tool(event_id: int, limit: int = 8) -> Dict[str, Any]:
    with session_scope() as session:
        event = session.get(Event, int(event_id))
        if event is None:
            return {"error": "event not found", "items": []}
        members = _member_payloads(session, event.id)
        items = find_orphan_news(
            session, event, member_ids={m.id for m in members}, limit=min(15, max(1, int(limit)))
        )
        return {"items": items}


def match_pipeline_assets_tool(event_id: int) -> Dict[str, Any]:
    with session_scope() as session:
        event = session.get(Event, int(event_id))
        if event is None:
            return {"error": "event not found", "items": []}
        members = _member_payloads(session, event.id)
        anchor = event_anchor_entities(event, members)
        hits = soft_match_pipeline_assets(session, anchor)
        return {"items": hits, "empty": not hits}


def get_company_track_record(event_id: int) -> Dict[str, Any]:
    """弱聚合：阶段分布 + 近期 deal/change；非真实获批史。"""
    with session_scope() as session:
        event = session.get(Event, int(event_id))
        if event is None:
            return {"empty": True, "reason": "event not found"}
        members = _member_payloads(session, event.id)
        anchor = event_anchor_entities(event, members)
        orgs = [o for o in (anchor.get("orgs") or []) if o]
        if not orgs:
            return {"empty": True, "reason": "no org anchor"}

        company_ids: List[int] = []
        for name in orgs[:4]:
            like = f"%{name}%"
            rows = list(
                session.scalars(
                    select(Company)
                    .where(
                        (Company.name.ilike(like))
                        | (Company.name_en.ilike(like))
                        | (Company.name_zh.ilike(like))
                    )
                    .limit(3)
                ).all()
            )
            company_ids.extend(r.id for r in rows)
        company_ids = list(dict.fromkeys(company_ids))
        if not company_ids:
            return {"empty": True, "reason": "no company match", "orgs": orgs}

        stage_rows = list(
            session.execute(
                select(PipelineAsset.current_stage, func.count())
                .where(PipelineAsset.company_id.in_(company_ids))
                .where(PipelineAsset.status == "active")
                .group_by(PipelineAsset.current_stage)
            ).all()
        )
        stage_dist = {str(s or "unknown"): int(c) for s, c in stage_rows}

        deals = list(
            session.scalars(
                select(PipelineDeal)
                .where(PipelineDeal.company_id.in_(company_ids))
                .order_by(PipelineDeal.id.desc())
                .limit(8)
            ).all()
        )
        asset_ids = list(
            session.scalars(
                select(PipelineAsset.id).where(PipelineAsset.company_id.in_(company_ids)).limit(50)
            ).all()
        )
        changes = []
        if asset_ids:
            changes = list(
                session.scalars(
                    select(PipelineChange)
                    .where(PipelineChange.asset_id.in_(asset_ids))
                    .order_by(PipelineChange.id.desc())
                    .limit(8)
                ).all()
            )

        return {
            "empty": not (stage_dist or deals or changes),
            "disclaimer": "弱聚合（管线阶段/交易/变更），非监管获批成功率",
            "orgs_queried": orgs,
            "stage_distribution": stage_dist,
            "recent_deals": [
                {
                    "deal_type": d.deal_type,
                    "counterparty": d.counterparty,
                    "summary": (d.summary or "")[:200],
                    "announced_on": d.announced_on,
                }
                for d in deals
            ],
            "recent_changes": [
                {
                    "field": d.field,
                    "old_value": (d.old_value or "")[:80],
                    "new_value": (d.new_value or "")[:80],
                    "change_kind": d.change_kind,
                }
                for d in changes
            ],
        }


def build_event_tools(focus_event_id: int):
    from backend.src.agents.runtime import ToolSpec

    def _card(args: Dict[str, Any]):
        eid = int(args.get("event_id") or focus_event_id)
        return get_event_card(eid)

    def _chain(args: Dict[str, Any]):
        eid = int(args.get("event_id") or focus_event_id)
        return list_entity_event_chain_tool(eid, limit=int(args.get("limit") or 12))

    def _timeline(args: Dict[str, Any]):
        eid = int(args.get("event_id") or focus_event_id)
        return get_event_timeline(eid, limit=int(args.get("limit") or 12))

    def _orphan(args: Dict[str, Any]):
        eid = int(args.get("event_id") or focus_event_id)
        return list_orphan_news_tool(eid, limit=int(args.get("limit") or 8))

    def _pipe(args: Dict[str, Any]):
        eid = int(args.get("event_id") or focus_event_id)
        return match_pipeline_assets_tool(eid)

    def _track(args: Dict[str, Any]):
        eid = int(args.get("event_id") or focus_event_id)
        return get_company_track_record(eid)

    _eid = {
        "type": "object",
        "properties": {
            "event_id": {"type": "integer", "description": "事件 ID，默认焦点事件"},
            "limit": {"type": "integer"},
        },
    }
    return [
        ToolSpec(
            "get_event_card",
            "获取事件簇级卡片（摘要、实体、风险分、burst）",
            _eid,
            _card,
        ),
        ToolSpec(
            "list_entity_event_chain",
            "同 product/drug 的其他事件簇链（簇摘要，不含成员全文）",
            _eid,
            _chain,
        ),
        ToolSpec(
            "get_event_timeline",
            "焦点簇成员时间线（标题+短摘要）",
            _eid,
            _timeline,
        ),
        ToolSpec(
            "list_orphan_news",
            "同实体未入簇新闻补漏",
            _eid,
            _orphan,
        ),
        ToolSpec(
            "match_pipeline_assets",
            "软匹配官网管线资产（只读）",
            _eid,
            _pipe,
        ),
        ToolSpec(
            "get_company_track_record",
            "公司弱聚合战绩（阶段分布/交易/变更，非 LoA）",
            _eid,
            _track,
        ),
    ]
