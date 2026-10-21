"""管线变更邮件：按用户 Watchlist 汇总发送。"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Sequence

from jinja2 import Template
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.src.alerts.matcher import send_email
from backend.src.alerts.smtp_settings import is_smtp_ready
from backend.src.core.logger import get_logger
from backend.src.models.entities import Watchlist
from backend.src.models.pipeline import PipelineChange
from backend.src.pipeline_intel.normalize import stage_label

logger = get_logger("pipeline_intel.notify")

_TEMPLATE = """
<!DOCTYPE html>
<html><body style="font-family:sans-serif;line-height:1.5">
  <h2>研发管线变更通知</h2>
  <p>您订阅的实体出现以下管线变动（共 {{ items|length }} 条）：</p>
  <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse">
    <thead>
      <tr>
        <th>类型</th><th>公司</th><th>药物</th><th>适应症</th>
        <th>字段</th><th>旧值</th><th>新值</th><th>时间</th>
      </tr>
    </thead>
    <tbody>
      {% for it in items %}
      <tr>
        <td>{{ it.change_kind }}</td>
        <td>{{ it.company_name or '-' }}</td>
        <td>{{ it.drug_name or '-' }}</td>
        <td>{{ it.indication or '-' }}</td>
        <td>{{ it.field }}</td>
        <td>{{ it.old_display }}</td>
        <td>{{ it.new_display }}</td>
        <td>{{ it.detected_at }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  <p style="color:#666;font-size:12px">本邮件由 DrugIntel 按您的 Watchlist 订阅发送。</p>
</body></html>
"""


def _display_value(field: str, value: str | None) -> str:
    if value is None or value == "":
        return "—"
    if field == "stage":
        return stage_label(value)
    return value


def _match_watchlists(
    change: PipelineChange, watchlists: Sequence[Watchlist]
) -> List[Watchlist]:
    drug = (change.drug_name or "").strip().lower()
    company = (change.company_name or "").strip().lower()
    hit: List[Watchlist] = []
    for wl in watchlists:
        if not wl.enabled or not (wl.email or "").strip():
            continue
        name = (wl.entity_name or "").strip().lower()
        if not name:
            continue
        et = (wl.entity_type or "").lower()
        if et in {"drug", "pipeline_asset"} and drug and name in drug:
            hit.append(wl)
        elif et == "company" and company and name in company:
            hit.append(wl)
        elif et == "keyword" and (
            (drug and name in drug) or (company and name in company)
        ):
            hit.append(wl)
        elif not et and ((drug and name in drug) or (company and name in company)):
            hit.append(wl)
    return hit


def notify_pipeline_changes(session: Session, change_ids: Sequence[int]) -> Dict[str, Any]:
    if not change_ids:
        return {"sent": 0, "skipped": 0}
    if not is_smtp_ready():
        logger.info("SMTP 未就绪，跳过管线变更邮件")
        return {"sent": 0, "skipped": len(change_ids), "reason": "smtp_not_ready"}

    changes = list(
        session.scalars(
            select(PipelineChange).where(
                PipelineChange.id.in_(list(change_ids)),
                PipelineChange.notified.is_(False),
            )
        ).all()
    )
    # 仅通知非 created？计划：首次基线 created 已标 notified；其余 created/updated/removed 都可通知
    watchlists = list(
        session.scalars(select(Watchlist).where(Watchlist.enabled.is_(True))).all()
    )
    if not watchlists:
        for ch in changes:
            ch.notified = True
        session.flush()
        return {"sent": 0, "skipped": len(changes), "reason": "no_watchlist"}

    # email -> items
    buckets: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    change_by_email: Dict[str, List[PipelineChange]] = defaultdict(list)

    for ch in changes:
        matched = _match_watchlists(ch, watchlists)
        if not matched:
            ch.notified = True  # 无订阅者，避免反复扫描
            continue
        item = {
            "change_kind": ch.change_kind,
            "company_name": ch.company_name,
            "drug_name": ch.drug_name,
            "indication": ch.indication,
            "field": ch.field,
            "old_display": _display_value(ch.field, ch.old_value),
            "new_display": _display_value(ch.field, ch.new_value),
            "detected_at": ch.detected_at.isoformat() if ch.detected_at else "",
        }
        emails = {(wl.email or "").strip() for wl in matched if (wl.email or "").strip()}
        for email in emails:
            buckets[email].append(item)
            change_by_email[email].append(ch)

    template = Template(_TEMPLATE)
    sent = 0
    for email, items in buckets.items():
        html = template.render(items=items)
        try:
            send_email(
                to_addr=email,
                subject=f"[DrugIntel] 管线变更 {len(items)} 条",
                html_body=html,
            )
            sent += 1
            for ch in change_by_email[email]:
                ch.notified = True
        except Exception as exc:
            logger.warning("管线变更邮件发送失败 %s: %s", email, exc)

    # 未进任何桶的已在上面标 notified；仍有未匹配的也标掉
    for ch in changes:
        if not ch.notified and not _match_watchlists(ch, watchlists):
            ch.notified = True
    session.flush()
    return {"sent": sent, "changes": len(changes)}
