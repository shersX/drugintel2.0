"""告警：Watchlist 匹配与邮件发送。"""

from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from jinja2 import Template
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.src.core.config import SmtpEnvConfig
from backend.src.core.logger import get_logger
from backend.src.models.entities import Watchlist
from backend.src.models.news import News

logger = get_logger("alerts")

TEMPLATE_PATH = (
    Path(__file__).resolve().parents[1] / "alerts" / "templates" / "alert_email.html"
)


def list_watchlists(
    session: Session,
    *,
    user_id: Optional[int] = None,
    enabled_only: bool = False,
) -> List[Watchlist]:
    stmt = select(Watchlist)
    if user_id is not None:
        stmt = stmt.where(Watchlist.user_id == user_id)
    if enabled_only:
        stmt = stmt.where(Watchlist.enabled.is_(True))
    return list(session.scalars(stmt.order_by(Watchlist.id.desc())).all())


def create_watchlist(
    session: Session,
    *,
    user_id: int,
    entity_type: str,
    entity_name: str,
    email: Optional[str] = None,
    enabled: bool = True,
) -> Watchlist:
    row = Watchlist(
        user_id=user_id,
        entity_type=entity_type,
        entity_name=entity_name,
        email=email,
        enabled=enabled,
    )
    session.add(row)
    session.flush()
    return row


def delete_watchlist(session: Session, watchlist_id: int) -> bool:
    row = session.get(Watchlist, watchlist_id)
    if row is None:
        return False
    session.delete(row)
    return True


def match_news_to_watchlists(
    news: News,
    watchlists: Sequence[Watchlist],
) -> List[Watchlist]:
    text = f"{news.title or ''} {news.abstract or ''} {news.content or ''}".lower()
    matched: List[Watchlist] = []
    for wl in watchlists:
        if not wl.enabled:
            continue
        name = (wl.entity_name or "").strip().lower()
        if name and name in text:
            matched.append(wl)
    return matched


def render_alert_email(news: News, watchlist: Watchlist) -> str:
    tpl = TEMPLATE_PATH.read_text(encoding="utf-8")
    return Template(tpl).render(
        entity_name=watchlist.entity_name,
        title=news.title,
        source=news.source or news.crawler or "-",
        publish_time=str(news.publish_time or ""),
        abstract=news.abstract or "",
        detail_url=news.detail_url or "",
    )


def send_email(*, to_addr: str, subject: str, html_body: str) -> bool:
    cfg = SmtpEnvConfig.load()
    if not cfg.host or not to_addr:
        logger.warning("SMTP 未配置或收件人为空，跳过发送 subject=%s", subject)
        return False
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg.from_addr or cfg.user
    msg["To"] = to_addr
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    try:
        with smtplib.SMTP(cfg.host, cfg.port, timeout=30) as server:
            if cfg.use_tls:
                server.starttls()
            if cfg.user:
                server.login(cfg.user, cfg.password)
            server.sendmail(msg["From"], [to_addr], msg.as_string())
        logger.info("邮件已发送 to=%s subject=%s", to_addr, subject)
        return True
    except Exception as e:
        logger.error("邮件发送失败: %s", e)
        return False


def process_alerts_for_news(session: Session, news_items: Sequence[News]) -> Dict[str, Any]:
    watchlists = list_watchlists(session, enabled_only=True)
    sent = 0
    matched_pairs = 0
    for news in news_items:
        hits = match_news_to_watchlists(news, watchlists)
        for wl in hits:
            matched_pairs += 1
            if not wl.email:
                continue
            html = render_alert_email(news, wl)
            ok = send_email(
                to_addr=wl.email,
                subject=f"[DrugIntel] 关注动态：{news.title[:60]}",
                html_body=html,
            )
            if ok:
                sent += 1
    return {"matched": matched_pairs, "sent": sent}
