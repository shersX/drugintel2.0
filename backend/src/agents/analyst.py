"""分析预判 Agent：研报工具循环 + 异步入队。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Set

from backend.src.agents.runtime import run_tool_loop
from backend.src.agents.tools_events import build_event_tools
from backend.src.core.config import AnalystEnvConfig
from backend.src.core.logger import get_logger
from backend.src.db.session import session_scope
from backend.src.llm.client import SiliconFlowClient
from backend.src.models.event import Event
from backend.src.scoring.event_brief import (
    event_anchor_entities,
    synthesize_event_summary,
    _member_payloads,
    _run_coro,
)

logger = get_logger("agents.analyst")

_ROOT = Path(__file__).resolve().parents[3]
_PROMPT = {
    "clinical_asset": _ROOT / "config" / "prompts" / "analyst_event_forecast_clinical.txt",
    "deal_capital": _ROOT / "config" / "prompts" / "analyst_event_forecast_deal.txt",
    "general_intel": _ROOT / "config" / "prompts" / "analyst_event_forecast_general.txt",
}
_CLINICAL = frozenset({"clinical", "regulatory", "pipeline", "safety"})
_DEAL = frozenset({"deal", "financing"})
_SCHEMA_VERSION = 2

_inflight: Set[int] = set()


def resolve_report_mode(
    *,
    products: list,
    drugs: list,
    orgs: list,
    story_types: list,
) -> str:
    st = {str(x).strip().lower() for x in (story_types or []) if x}
    has_drug = bool(products or drugs)
    if has_drug and (st & _CLINICAL):
        return "clinical_asset"
    if (st & _DEAL) or ((not has_drug) and orgs):
        return "deal_capital"
    return "general_intel"


def _read_prompt(mode: str) -> str:
    path = _PROMPT.get(mode) or _PROMPT["general_intel"]
    if not path.exists():
        raise FileNotFoundError(f"缺少 prompt: {path}")
    return path.read_text(encoding="utf-8").strip()


class AnalystAgent:
    def __init__(self, client: Optional[SiliconFlowClient] = None):
        self.cfg = AnalystEnvConfig.load()
        self.client = client or SiliconFlowClient.from_analyst_env()
        self.enable_thinking = bool(self.cfg.enable_thinking)

    async def run_forecast(self, event_id: int) -> Dict[str, Any]:
        with session_scope() as session:
            event = session.get(Event, int(event_id))
            if event is None:
                raise ValueError("event not found")
            if not (event.summary or "").strip() or len((event.summary or "").strip()) < 40:
                synthesize_event_summary(session, event)
                session.flush()
            members = _member_payloads(session, event.id)
            anchor = event_anchor_entities(event, members)
            story_types = list(event.story_types or [])
            title = event.title
            summary = event.summary or ""
            mode = resolve_report_mode(
                products=anchor["products"],
                drugs=anchor["drugs"],
                orgs=anchor["orgs"],
                story_types=story_types,
            )

        system = _read_prompt(mode)
        user = (
            f"焦点 event_id={event_id}\n"
            f"report_mode={mode}\n"
            f"标题: {title}\n"
            f"当前簇摘要: {summary[:800]}\n"
            f"请先调用工具取证，再输出完整研报。"
        )
        tools = build_event_tools(event_id)
        result = await run_tool_loop(
            self.client,
            system=system,
            user=user,
            tools=tools,
            max_steps=6,
            temperature=0.25,
            enable_thinking=self.enable_thinking,
        )
        content = (result.get("content") or "").strip()
        if not content or len(content) < 80:
            raise ValueError("研报输出过短")

        tool_names = [t.get("name") for t in (result.get("tool_trace") or []) if t.get("name")]
        chain_ids = []
        for t in result.get("tool_trace") or []:
            if t.get("name") == "list_entity_event_chain":
                # ids 在工具返回里，此处仅记调用
                pass
        meta = {
            "report_mode": mode,
            "schema_version": _SCHEMA_VERSION,
            "tools": tool_names,
            "steps": result.get("steps"),
            "story_types": story_types,
            "anchor": {
                "products": anchor["products"],
                "drugs": anchor["drugs"],
                "orgs": anchor["orgs"],
            },
            "has_approval_outlook": mode == "clinical_asset",
            "enable_thinking": self.enable_thinking,
            "chain_event_ids": chain_ids,
        }
        return {"forecast_report": content, "forecast_evidence_meta": meta, "report_mode": mode}


def run_event_forecast_job(event_id: int) -> Dict[str, Any]:
    """Celery / 同步入口：短持有 session 写状态。"""
    eid = int(event_id)
    with session_scope() as session:
        event = session.get(Event, eid)
        if event is None:
            return {"ok": False, "error": "event not found"}
        event.forecast_status = "running"
        event.forecast_error = None
        session.flush()

    try:
        agent = AnalystAgent()
        payload = _run_coro(agent.run_forecast(eid))
        from datetime import datetime, timezone

        with session_scope() as session:
            event = session.get(Event, eid)
            if event is None:
                return {"ok": False, "error": "event disappeared"}
            event.forecast_report = payload["forecast_report"]
            event.forecast_evidence_meta = payload["forecast_evidence_meta"]
            event.forecast_generated_at = datetime.now(timezone.utc)
            event.forecast_status = "ready"
            event.forecast_error = None
            session.flush()
        return {"ok": True, "event_id": eid, "report_mode": payload.get("report_mode")}
    except Exception as exc:
        logger.exception("研报任务失败 event=%s", eid)
        with session_scope() as session:
            event = session.get(Event, eid)
            if event is not None:
                event.forecast_status = "failed"
                event.forecast_error = str(exc)[:500]
                session.flush()
        return {"ok": False, "event_id": eid, "error": str(exc)[:300]}
    finally:
        _inflight.discard(eid)


def enqueue_event_forecast(event_id: int, *, force: bool = False) -> Dict[str, Any]:
    """API 入队：秒回。依赖 Celery worker。"""
    eid = int(event_id)
    with session_scope() as session:
        event = session.get(Event, eid)
        if event is None:
            raise ValueError("event not found")
        status = (event.forecast_status or "idle").strip()
        if not force and status in ("queued", "running"):
            return {
                "event_id": eid,
                "status": status,
                "queued": False,
                "message": "已在生成中",
            }
        if not force and status == "ready" and event.forecast_report:
            return {
                "event_id": eid,
                "status": "ready",
                "queued": False,
                "cached": True,
            }
        event.forecast_status = "queued"
        event.forecast_error = None
        if force:
            # 保留旧文直至成功覆盖
            pass
        session.flush()

    if eid in _inflight:
        return {"event_id": eid, "status": "queued", "queued": False, "message": "inflight"}

    try:
        from tasks.celery_app import celery_app

        insp = celery_app.control.inspect(timeout=2.0)
        ping = insp.ping() if insp else None
        if not ping:
            with session_scope() as session:
                event = session.get(Event, eid)
                if event is not None:
                    event.forecast_status = "failed"
                    event.forecast_error = "Celery worker 未启动，无法异步生成研报"
                    session.flush()
            raise RuntimeError("Celery worker 未启动，无法异步生成研报")

        # 用 celery 的限流：task 内再检查并发；此处先入队
        celery_app.send_task(
            "tasks.forecast_tasks.generate_event_forecast",
            args=[eid],
            kwargs={},
        )
        _inflight.add(eid)
        return {"event_id": eid, "status": "queued", "queued": True}
    except RuntimeError:
        raise
    except Exception as exc:
        with session_scope() as session:
            event = session.get(Event, eid)
            if event is not None:
                event.forecast_status = "failed"
                event.forecast_error = f"入队失败: {exc}"[:500]
                session.flush()
        raise RuntimeError(f"研报入队失败: {exc}") from exc
