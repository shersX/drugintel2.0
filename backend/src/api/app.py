"""FastAPI 应用：整合新闻、事件、问答、告警、统计、监控、报告。"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import or_, select
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.src.auth.deps import admin_actor, clear_session_cookie, current_actor, set_session_cookie
from backend.src.auth.service import (
    COOKIE_NAME,
    AccountError,
    Actor,
    AuthError,
    QuotaError,
    consume_chat_quota,
    create_user,
    list_users,
    login,
    record_audit,
    remember_report,
    reset_user_password,
    resolve_actor,
    revoke_token,
    revoke_user_sessions,
    set_chat_limit,
    set_user_status,
    update_profile as update_account,
    user_owns_report,
)
from backend.src.alerts.matcher import (
    create_watchlist,
    delete_watchlist,
    list_watchlists,
)
from backend.src.api.response import fail, ok
from backend.src.api.schemas import (
    AskRequest,
    ChatLimitUpdate,
    ConversationRename,
    CrawlerSettingUpdate,
    CrawlStartRequest,
    FilterKeywordCreate,
    FilterKeywordUpdate,
    KeywordReimportRequest,
    LlmProfileTest,
    LlmProfileWrite,
    LoginRequest,
    PasswordReset,
    PipelineAssetCreate,
    PipelineAssetPatch,
    PipelineCrawlConfigUpdate,
    PipelineSyncRequest,
    ProfileUpdate,
    RagConfigUpdate,
    ReportExportRequest,
    UserCreate,
    SmtpConfigUpdate,
    SmtpTestRequest,
    WatchlistCreate,
)
from backend.src.clustering.service import run_clustering
from backend.src.core.logger import get_logger
from backend.src.crawl.schedule import (
    CrawlConfigError,
    abandon_orphan_runs,
    config_payload,
    start_schedule,
    status_payload,
    stop_schedule,
)
from backend.src.db.crud.news import format_publish_time_cn
from backend.src.db.schema import ensure_schema
from backend.src.db.session import session_scope
from backend.src.core.config import vision_readiness
from backend.src.llm.profiles import (
    DimensionMismatch,
    LlmProfileError,
    activate_profile,
    create_profile,
    delete_profile,
    list_models,
    list_profiles,
    test_connection,
    update_profile as update_llm_profile,
)
from backend.src.models.event import Event
from backend.src.models.news import News
from backend.src.monitor.health import (
    health_check,
    processing_status,
    recent_crawler_tasks,
)
from backend.src.rag.qa import ask, ask_stream
from backend.src.reports.exporter import export_report
from backend.src.stats.service import (
    development_stage_stats,
    hot_keywords_stats,
    news_trend_stats,
    overview_stats,
)

logger = get_logger("api")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_schema()
    logger.info("数据库结构已检查")
    try:
        result = abandon_orphan_runs("API 启动：作废未完成的采集轮次")
        if result.get("abandoned"):
            logger.warning("启动时作废卡住采集轮次 %s", result)
    except Exception:
        logger.exception("启动时清理卡住采集轮次失败")
    yield


app = FastAPI(title="DrugIntel.ai API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIST = Path(__file__).resolve().parents[3] / "frontend" / "dist"


@app.get("/api/health")
def api_health():
    return ok(health_check())


@app.post("/api/auth/login")
def api_login(body: LoginRequest, response: Response):
    try:
        token, actor = login(body.email, body.password)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    set_session_cookie(response, token)
    return ok(actor.public())


@app.post("/api/auth/logout")
def api_logout(request: Request, response: Response, actor: Actor = Depends(current_actor)):
    revoke_token(request.cookies.get(COOKIE_NAME))
    clear_session_cookie(response)
    record_audit(actor_id=actor.id, action="logout", target=f"user:{actor.id}")
    return ok()


@app.get("/api/auth/me")
def api_me(actor: Actor = Depends(current_actor)):
    return ok(actor.public())


@app.put("/api/auth/profile")
def api_profile(body: ProfileUpdate, request: Request, actor: Actor = Depends(current_actor)):
    try:
        updated = update_account(
            actor,
            display_name=body.display_name,
            old_password=body.old_password,
            new_password=body.new_password,
            current_token=request.cookies.get(COOKIE_NAME),
        )
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except AccountError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(updated.public())


@app.get("/api/admin/users")
def api_admin_users(_actor: Actor = Depends(admin_actor)):
    return ok(list_users())


@app.post("/api/admin/users")
def api_admin_user_create(body: UserCreate, actor: Actor = Depends(admin_actor)):
    try:
        return ok(
            create_user(
                email=body.email,
                display_name=body.display_name,
                password=body.password,
                role=body.role,
                daily_chat_limit=body.daily_chat_limit,
                actor_id=actor.id,
            )
        )
    except AccountError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/admin/users/{user_id}/disable")
def api_admin_user_disable(user_id: int, actor: Actor = Depends(admin_actor)):
    try:
        return ok(set_user_status(user_id, "disabled", actor))
    except AccountError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/admin/users/{user_id}/enable")
def api_admin_user_enable(user_id: int, actor: Actor = Depends(admin_actor)):
    try:
        return ok(set_user_status(user_id, "active", actor))
    except AccountError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/admin/users/{user_id}/reset-password")
def api_admin_user_reset(user_id: int, body: PasswordReset, actor: Actor = Depends(admin_actor)):
    try:
        reset_user_password(user_id, body.password, actor.id)
    except AccountError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok({"id": user_id})


@app.post("/api/admin/users/{user_id}/kick")
def api_admin_user_kick(user_id: int, actor: Actor = Depends(admin_actor)):
    revoke_user_sessions(user_id)
    record_audit(actor_id=actor.id, action="session_revoke", target=f"user:{user_id}")
    return ok({"id": user_id})


@app.put("/api/admin/users/{user_id}/chat-limit")
def api_admin_user_limit(user_id: int, body: ChatLimitUpdate, actor: Actor = Depends(admin_actor)):
    try:
        return ok(set_chat_limit(user_id, body.daily_chat_limit, actor.id))
    except AccountError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/monitor/status")
def api_monitor_status(_actor: Actor = Depends(admin_actor)):
    return ok(
        {
            "processing": processing_status(),
            "crawler_tasks": recent_crawler_tasks(20),
            "health": health_check(),
        }
    )


@app.get("/api/stats/overview")
def api_stats_overview():
    with session_scope() as session:
        return ok(overview_stats(session))


@app.get("/api/stats/stages")
def api_stats_stages():
    with session_scope() as session:
        return ok(development_stage_stats(session))


@app.get("/api/stats/trend")
def api_stats_trend(days: int = Query(14, ge=1, le=90)):
    with session_scope() as session:
        return ok(news_trend_stats(session, days=days))


@app.get("/api/stats/keywords")
def api_stats_keywords(limit: int = Query(20, ge=1, le=100)):
    with session_scope() as session:
        return ok(hot_keywords_stats(session, limit=limit))


def _like_term(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


@app.get("/api/crawlers")
def api_crawlers():
    """来源筛选项（公开）。含已禁用爬虫，便于过滤历史入库数据；含 kind 区分新闻/管线。"""
    from backend.src.crawlers.registry import CRAWLER_REGISTRY

    return ok([
        {
            "key": key,
            "name": str(meta.get("name") or key),
            "kind": str(meta.get("kind") or "news"),
        }
        for key, meta in CRAWLER_REGISTRY.items()
    ])


_SHANGHAI = ZoneInfo("Asia/Shanghai")


def _shanghai_day_start(value: str) -> datetime:
    try:
        day = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="日期格式应为 YYYY-MM-DD") from exc
    return datetime.combine(day, time.min, tzinfo=_SHANGHAI)


@app.get("/api/news")
def api_news_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    crawler: Optional[str] = None,
    crawlers: Optional[list[str]] = Query(None),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    q: Optional[str] = None,
):
    from sqlalchemy import func
    from backend.src.crawlers.registry import news_crawler_keys

    allowed = set(news_crawler_keys())
    keys = [item.strip().lower() for item in (crawlers or []) if item and item.strip()]
    if not keys and crawler and crawler.strip():
        keys = [crawler.strip().lower()]
    unknown = [item for item in keys if item not in allowed]
    if unknown:
        raise HTTPException(status_code=400, detail="未知来源（管线爬虫不可用于新闻筛选）")
    start = _shanghai_day_start(date_from) if date_from else None
    end = _shanghai_day_start(date_to) + timedelta(days=1) if date_to else None

    with session_scope() as session:
        from backend.src.db.crud.news import news_ready_filter

        base = select(News).where(news_ready_filter())
        if keys:
            base = base.where(News.crawler.in_(keys))
        if start is not None:
            base = base.where(News.publish_time >= start)
        if end is not None:
            base = base.where(News.publish_time < end)
        term = (q or "").strip()
        if term:
            like = _like_term(term)
            base = base.where(or_(News.title.ilike(like), News.abstract.ilike(like)))
        total = session.scalar(select(func.count()).select_from(base.subquery())) or 0
        rows = session.scalars(
            base.order_by(News.publish_time.desc().nulls_last(), News.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        items = [
            {
                "id": n.id,
                "title": n.title,
                "abstract": n.abstract,
                "source": n.source,
                "crawler": n.crawler,
                "publish_time": format_publish_time_cn(n.publish_time),
                "detail_url": n.detail_url,
                "event_id": n.event_id,
                "is_representative": n.is_representative,
            }
            for n in rows
        ]
        return ok({"total": int(total), "page": page, "page_size": page_size, "items": items})


@app.get("/api/news/{news_id}")
def api_news_detail(news_id: int):
    from backend.src.db.crud.news import PROCESS_READY, news_ready_filter

    with session_scope() as session:
        news = session.get(News, news_id)
        if news is None or news.process_status != PROCESS_READY:
            raise HTTPException(404, "news not found")
        related = []
        if news.event_id:
            related_rows = session.scalars(
                select(News)
                .where(News.event_id == news.event_id)
                .where(News.id != news.id)
                .where(news_ready_filter())
                .limit(20)
            ).all()
            related = [{"id": r.id, "title": r.title} for r in related_rows]
        return ok(
            {
                "id": news.id,
                "title": news.title,
                "content": news.content,
                "content_html": news.content_html,
                "abstract": news.abstract,
                "source": news.source,
                "crawler": news.crawler,
                "publish_time": format_publish_time_cn(news.publish_time),
                "detail_url": news.detail_url,
                "matched_keywords": news.matched_keywords,
                "event_id": news.event_id,
                "is_representative": news.is_representative,
                "related_news": related,
            }
        )


@app.get("/api/events")
def api_events(page: int = 1, page_size: int = 20):
    with session_scope() as session:
        stmt = select(Event).order_by(Event.updated_at.desc())
        rows = session.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()
        items = [
            {
                "id": e.id,
                "title": e.title,
                "summary": e.summary,
                "news_count": e.news_count,
                "representative_news_id": e.representative_news_id,
                "updated_at": str(e.updated_at) if e.updated_at else None,
            }
            for e in rows
        ]
        return ok({"items": items, "page": page, "page_size": page_size})


@app.post("/api/cluster/run")
def api_cluster_run(_actor: Actor = Depends(admin_actor)):
    return ok(run_clustering())


@app.get("/api/chat/conversations")
def api_chat_conversations(actor: Actor = Depends(current_actor), limit: int = Query(50, ge=1, le=100)):
    from backend.src.db.crud.chat import conversation_to_dict, list_conversations

    with session_scope() as session:
        rows = list_conversations(session, user_id=actor.id, limit=limit)
        return ok([conversation_to_dict(r) for r in rows])


@app.post("/api/chat/conversations")
def api_chat_conversation_create(actor: Actor = Depends(current_actor)):
    from backend.src.db.crud.chat import conversation_to_dict, create_conversation

    with session_scope() as session:
        row = create_conversation(session, user_id=actor.id)
        return ok(conversation_to_dict(row))


@app.get("/api/chat/conversations/{conversation_id}")
def api_chat_conversation_detail(conversation_id: str, actor: Actor = Depends(current_actor)):
    from backend.src.db.crud.chat import (
        conversation_to_dict,
        get_conversation_for_user,
        list_messages,
        message_to_dict,
    )

    with session_scope() as session:
        row = get_conversation_for_user(
            session, conversation_id=conversation_id, user_id=actor.id
        )
        if row is None:
            raise HTTPException(status_code=404, detail="conversation not found")
        messages = list_messages(session, conversation_id=row.id)
        return ok(
            {
                **conversation_to_dict(row),
                "messages": [message_to_dict(m) for m in messages],
            }
        )


@app.patch("/api/chat/conversations/{conversation_id}")
def api_chat_conversation_rename(
    conversation_id: str,
    body: ConversationRename,
    actor: Actor = Depends(current_actor),
):
    from backend.src.db.crud.chat import conversation_to_dict, rename_conversation

    with session_scope() as session:
        row = rename_conversation(
            session,
            conversation_id=conversation_id,
            user_id=actor.id,
            title=body.title,
        )
        if row is None:
            raise HTTPException(status_code=404, detail="conversation not found")
        return ok(conversation_to_dict(row))


@app.delete("/api/chat/conversations/{conversation_id}")
def api_chat_conversation_delete(conversation_id: str, actor: Actor = Depends(current_actor)):
    from backend.src.db.crud.chat import delete_conversation

    with session_scope() as session:
        if not delete_conversation(
            session, conversation_id=conversation_id, user_id=actor.id
        ):
            raise HTTPException(status_code=404, detail="conversation not found")
        return ok({"deleted": conversation_id})


@app.post("/api/chat/ask")
async def api_chat_ask(body: AskRequest, actor: Actor = Depends(current_actor)):
    try:
        consume_chat_quota(actor.id)
    except QuotaError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    result = await ask(
        body.query,
        user_id=actor.id,
        top_k=body.top_k,
        conversation_id=body.conversation_id,
        session_id=body.session_id,
        news_id=body.news_id,
    )
    return ok(
        {
            "session_id": result.session_id,
            "conversation_id": result.conversation_id,
            "intent": result.intent.intent.value,
            "answer": result.answer,
            "sources": result.sources,
            "search_query": result.search_query,
            "clarify": result.clarify,
        }
    )


@app.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket):
    actor = resolve_actor(websocket.cookies.get(COOKIE_NAME))
    if actor is None:
        await websocket.close(code=4401)
        return
    await websocket.accept()
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "invalid json"})
                continue
            query = (payload.get("query") or "").strip()
            if not query:
                await websocket.send_json({"type": "error", "message": "empty query"})
                continue
            try:
                consume_chat_quota(actor.id)
            except QuotaError as exc:
                await websocket.send_json({"type": "error", "message": str(exc)})
                continue
            raw_news_id = payload.get("news_id")
            news_id = None
            if raw_news_id is not None and raw_news_id != "":
                try:
                    news_id = int(raw_news_id)
                except (TypeError, ValueError):
                    news_id = None
            async for event in ask_stream(
                query,
                user_id=actor.id,
                conversation_id=payload.get("conversation_id"),
                session_id=payload.get("session_id"),
                news_id=news_id,
            ):
                await websocket.send_json(event)
    except WebSocketDisconnect:
        return


@app.get("/api/watchlist")
def api_watchlist_list(actor: Actor = Depends(current_actor)):
    with session_scope() as session:
        rows = list_watchlists(session, user_id=actor.id)
        return ok(
            [
                {
                    "id": r.id,
                    "user_id": r.user_id,
                    "entity_type": r.entity_type,
                    "entity_name": r.entity_name,
                    "email": r.email,
                    "enabled": r.enabled,
                }
                for r in rows
            ]
        )


@app.post("/api/watchlist")
def api_watchlist_create(body: WatchlistCreate, actor: Actor = Depends(current_actor)):
    with session_scope() as session:
        row = create_watchlist(
            session,
            user_id=actor.id,
            entity_type=body.entity_type,
            entity_name=body.entity_name,
            email=body.email,
            enabled=body.enabled,
        )
        return ok({"id": row.id})


@app.delete("/api/watchlist/{watchlist_id}")
def api_watchlist_delete(watchlist_id: int, actor: Actor = Depends(current_actor)):
    with session_scope() as session:
        if not delete_watchlist(session, watchlist_id, actor.id):
            raise HTTPException(404, "watchlist not found")
        return ok({"deleted": watchlist_id})


@app.get("/api/alerts/mail-status")
def api_alerts_mail_status(_actor: Actor = Depends(current_actor)):
    from backend.src.alerts.smtp_settings import mail_status_dict

    return ok(mail_status_dict())


@app.get("/api/admin/smtp-config")
def api_admin_smtp_config_get(_actor: Actor = Depends(admin_actor)):
    from backend.src.alerts.smtp_settings import (
        get_or_create_smtp_config,
        smtp_config_to_admin_dict,
    )

    with session_scope() as session:
        row = get_or_create_smtp_config(session)
        return ok(smtp_config_to_admin_dict(row))


@app.put("/api/admin/smtp-config")
def api_admin_smtp_config_put(body: SmtpConfigUpdate, actor: Actor = Depends(admin_actor)):
    from backend.src.alerts.smtp_settings import (
        smtp_config_to_admin_dict,
        update_smtp_settings,
    )

    with session_scope() as session:
        row = update_smtp_settings(
            session,
            host=body.host,
            port=body.port,
            user=body.user,
            from_addr=body.from_addr,
            use_tls=body.use_tls,
            enabled=body.enabled,
            password=body.password,
        )
        payload = smtp_config_to_admin_dict(row)
    record_audit(
        actor_id=actor.id,
        action="smtp_config_update",
        target="smtp_config",
        detail=f"host={payload.get('host') or '-'},ready={payload.get('ready')}",
    )
    return ok(payload)


@app.post("/api/admin/smtp-config/test")
def api_admin_smtp_config_test(body: SmtpTestRequest, actor: Actor = Depends(admin_actor)):
    from backend.src.alerts.matcher import send_email
    from backend.src.alerts.smtp_settings import is_smtp_ready, load_smtp_settings

    to_email = (body.to_email or "").strip()
    if "@" not in to_email:
        raise HTTPException(status_code=400, detail="请填写有效的测试收件邮箱")
    cfg = load_smtp_settings()
    if not is_smtp_ready(cfg):
        raise HTTPException(status_code=400, detail="邮件通道未就绪，请先保存有效的 SMTP 配置")
    ok_send = send_email(
        to_addr=to_email,
        subject="[DrugIntel] SMTP 测试邮件",
        html_body=(
            "<p>这是一封 DrugIntel 告警通道测试邮件。</p>"
            "<p>若你收到此信，说明 SMTP 配置可用。</p>"
        ),
    )
    record_audit(
        actor_id=actor.id,
        action="smtp_config_test",
        target="smtp_config",
        detail=f"to={to_email},ok={ok_send}",
    )
    if not ok_send:
        raise HTTPException(status_code=502, detail="测试邮件发送失败，请检查 SMTP 主机、账号与密码")
    return ok({"sent": True, "to": to_email})


@app.post("/api/crawl/start")
def api_crawl_start(body: CrawlStartRequest, actor: Actor = Depends(admin_actor)):
    try:
        payload = start_schedule(
            body.schedule_mode,
            body.daily_time,
            body.crawler_keys,
            interval_minutes=body.interval_minutes,
        )
    except CrawlConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    record_audit(actor_id=actor.id, action="crawl_start", target="crawl")
    return ok(payload)


@app.post("/api/crawl/stop")
def api_crawl_stop(actor: Actor = Depends(admin_actor)):
    payload = stop_schedule()
    record_audit(actor_id=actor.id, action="crawl_stop", target="crawl")
    return ok(payload)


@app.post("/api/crawl/abandon")
def api_crawl_abandon(actor: Actor = Depends(admin_actor)):
    """手动作废卡住的 running 轮次（进程崩溃后「本轮进行中」无法自行消失时用）。"""
    result = abandon_orphan_runs("管理员手动清除卡死状态")
    record_audit(
        actor_id=actor.id,
        action="crawl_abandon",
        target="crawl",
        detail=f"abandoned={result.get('abandoned', 0)}",
    )
    return ok({**result, **status_payload()})


@app.get("/api/crawl/config")
def api_crawl_config(_actor: Actor = Depends(admin_actor)):
    return ok(config_payload())


@app.get("/api/crawl/status")
def api_crawl_status(_actor: Actor = Depends(current_actor)):
    return ok(status_payload())


@app.post("/api/crawl/reprocess")
async def api_crawl_reprocess(
    limit: int = Query(50, ge=1, le=200),
    actor: Actor = Depends(admin_actor),
):
    """手动补跑积压的 raw/failed 新闻（摘要+向量）。"""
    from backend.src.processors.pipeline import reprocess_pending_news

    stats = await reprocess_pending_news(limit=limit)
    record_audit(
        actor_id=actor.id,
        action="crawl_reprocess",
        target="news",
        detail=f"limit={limit}",
    )
    return ok(stats)


@app.get("/api/llm/profiles")
def api_llm_profiles(_actor: Actor = Depends(admin_actor)):
    return ok(list_profiles())


def _llm_http_error(exc: LlmProfileError) -> HTTPException:
    if isinstance(exc, DimensionMismatch):
        return HTTPException(
            status_code=409,
            detail={
                "code": "dimension_mismatch",
                "current_dim": exc.current_dim,
                "next_dim": exc.next_dim,
                "message": str(exc),
            },
        )
    return HTTPException(status_code=400, detail=str(exc))


@app.post("/api/llm/profiles")
def api_llm_profile_create(body: LlmProfileWrite, actor: Actor = Depends(admin_actor)):
    try:
        created = create_profile(
                name=body.name,
                api_key=body.api_key or "",
                base_url=body.base_url,
                chat_model=body.chat_model,
                embedding_api_key=body.embedding_api_key or "",
                embedding_base_url=body.embedding_base_url,
                embedding_model=body.embedding_model,
                embedding_dim=body.embedding_dim,
                reranker_api_key=body.reranker_api_key or "",
                reranker_base_url=body.reranker_base_url,
                reranker_model=body.reranker_model,
                vision_api_key=body.vision_api_key or "",
                vision_base_url=body.vision_base_url or "",
                vision_model=body.vision_model or "",
            )
    except LlmProfileError as exc:
        raise _llm_http_error(exc) from exc
    record_audit(actor_id=actor.id, action="llm_create", target=f"llm:{created.get('id', '')}", detail=body.name)
    return ok(created)


@app.post("/api/llm/profiles/test")
async def api_llm_profile_test(body: LlmProfileTest, _actor: Actor = Depends(admin_actor)):
    try:
        return ok(
            await test_connection(
                base_url=body.base_url,
                api_key=body.api_key,
                profile_id=body.profile_id,
                slot=body.slot,
                include_models=body.include_models,
            )
        )
    except LlmProfileError as exc:
        raise _llm_http_error(exc) from exc


@app.post("/api/llm/profiles/list-models")
async def api_llm_list_models(body: LlmProfileTest, _actor: Actor = Depends(admin_actor)):
    try:
        return ok(
            await list_models(
                base_url=body.base_url,
                api_key=body.api_key,
                profile_id=body.profile_id,
                slot=body.slot,
            )
        )
    except LlmProfileError as exc:
        raise _llm_http_error(exc) from exc


@app.put("/api/llm/profiles/{profile_id}")
def api_llm_profile_update(profile_id: int, body: LlmProfileWrite, actor: Actor = Depends(admin_actor)):
    try:
        updated = update_llm_profile(
                profile_id,
                name=body.name,
                api_key=body.api_key,
                base_url=body.base_url,
                chat_model=body.chat_model,
                embedding_api_key=body.embedding_api_key,
                embedding_base_url=body.embedding_base_url,
                embedding_model=body.embedding_model,
                embedding_dim=body.embedding_dim,
                reranker_api_key=body.reranker_api_key,
                reranker_base_url=body.reranker_base_url,
                reranker_model=body.reranker_model,
                vision_api_key=body.vision_api_key,
                vision_base_url=body.vision_base_url or "",
                vision_model=body.vision_model or "",
                rebuild=body.rebuild,
            )
    except LlmProfileError as exc:
        raise _llm_http_error(exc) from exc
    record_audit(actor_id=actor.id, action="llm_update", target=f"llm:{profile_id}", detail=body.name)
    return ok(updated)


@app.delete("/api/llm/profiles/{profile_id}")
def api_llm_profile_delete(profile_id: int, actor: Actor = Depends(admin_actor)):
    try:
        delete_profile(profile_id)
    except LlmProfileError as exc:
        raise _llm_http_error(exc) from exc
    record_audit(actor_id=actor.id, action="llm_delete", target=f"llm:{profile_id}")
    return ok({"deleted": profile_id})


@app.post("/api/llm/profiles/{profile_id}/activate")
def api_llm_profile_activate(profile_id: int, rebuild: bool = Query(False), actor: Actor = Depends(admin_actor)):
    try:
        payload = activate_profile(profile_id, rebuild=rebuild)
    except LlmProfileError as exc:
        raise _llm_http_error(exc) from exc
    record_audit(actor_id=actor.id, action="llm_activate", target=f"llm:{profile_id}")
    return ok(payload)


@app.get("/api/pipeline/vision-status")
def api_pipeline_vision_status(_actor: Actor = Depends(current_actor)):
    return ok(vision_readiness())


@app.get("/api/pipeline/facets")
def api_pipeline_facets(
    status: str = "active",
    _actor: Actor = Depends(current_actor),
):
    from backend.src.pipeline_intel.queries import list_facets

    with session_scope() as session:
        return ok(list_facets(session, status=status))


@app.get("/api/pipeline/analytics/target-compare")
def api_pipeline_target_compare(
    target: str = "",
    _actor: Actor = Depends(current_actor),
):
    from backend.src.pipeline_intel.queries import analytics_target_compare

    with session_scope() as session:
        return ok(analytics_target_compare(session, target=target))


@app.get("/api/pipeline/analytics/competition")
def api_pipeline_competition(
    limit: int = Query(10, ge=1, le=50),
    _actor: Actor = Depends(current_actor),
):
    from backend.src.pipeline_intel.queries import analytics_competition

    with session_scope() as session:
        return ok(analytics_competition(session, limit=limit))


@app.get("/api/pipeline/assets/export")
def api_pipeline_assets_export(
    q: str = "",
    target: str = "",
    indication: str = "",
    company: str = "",
    stages: str = "",
    stage: str = "",
    modality: str = "",
    status: str = "active",
    watched_only: bool = False,
    actor: Actor = Depends(current_actor),
):
    from backend.src.pipeline_intel.queries import export_assets_csv

    with session_scope() as session:
        csv_text = export_assets_csv(
            session,
            q=q,
            target=target,
            indication=indication,
            company=company,
            stages=stages,
            stage=stage,
            modality=modality,
            status=status,
            watched_only=watched_only,
            user_id=actor.id,
        )
    return Response(
        content="\ufeff" + csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="pipeline_assets.csv"'},
    )


@app.get("/api/pipeline/assets")
def api_pipeline_assets(    q: str = "",
    target: str = "",
    indication: str = "",
    company: str = "",
    stages: str = "",
    stage: str = "",
    modality: str = "",
    status: str = "active",
    watched_only: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=5000),
    actor: Actor = Depends(current_actor),
):
    from backend.src.pipeline_intel.queries import list_assets

    with session_scope() as session:
        return ok(
            list_assets(
                session,
                q=q,
                target=target,
                indication=indication,
                company=company,
                stages=stages,
                stage=stage,
                modality=modality,
                status=status,
                watched_only=watched_only,
                user_id=actor.id,
                page=page,
                page_size=page_size,
            )
        )


@app.post("/api/pipeline/assets")
def api_pipeline_asset_create(
    body: PipelineAssetCreate,
    actor: Actor = Depends(admin_actor),
):
    from backend.src.pipeline_intel.queries import create_asset

    with session_scope() as session:
        try:
            data = create_asset(session, payload=body.model_dump(), actor_id=actor.id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail={"code": "invalid", "message": str(exc)}) from exc
    record_audit(actor_id=actor.id, action="pipeline_asset_create", target=f"pipeline:{data.get('id')}")
    return ok(data)


@app.get("/api/pipeline/assets/{asset_id}")
def api_pipeline_asset_detail(asset_id: int, _actor: Actor = Depends(current_actor)):
    from backend.src.pipeline_intel.queries import get_asset

    with session_scope() as session:
        data = get_asset(session, asset_id)
    if data is None:
        raise HTTPException(status_code=404, detail="管线资产不存在")
    return ok(data)


@app.patch("/api/pipeline/assets/{asset_id}")
def api_pipeline_asset_patch(
    asset_id: int,
    body: PipelineAssetPatch,
    actor: Actor = Depends(admin_actor),
):
    from backend.src.pipeline_intel.queries import patch_asset

    payload = body.model_dump(exclude_unset=True)
    with session_scope() as session:
        data = patch_asset(session, asset_id, payload=payload, actor_id=actor.id)
    if data is None:
        raise HTTPException(status_code=404, detail="管线资产不存在")
    record_audit(actor_id=actor.id, action="pipeline_asset_patch", target=f"pipeline:{asset_id}")
    return ok(data)


@app.delete("/api/pipeline/assets/{asset_id}")
def api_pipeline_asset_delete(asset_id: int, actor: Actor = Depends(admin_actor)):
    from backend.src.pipeline_intel.queries import soft_delete_asset

    with session_scope() as session:
        ok_del = soft_delete_asset(session, asset_id)
    if not ok_del:
        raise HTTPException(status_code=404, detail="管线资产不存在")
    record_audit(actor_id=actor.id, action="pipeline_asset_delete", target=f"pipeline:{asset_id}")
    return ok({"id": asset_id, "status": "inactive"})


@app.get("/api/pipeline/changes")
def api_pipeline_changes(
    limit: int = Query(50, ge=1, le=200),
    change_kind: str = "",
    source: str = "",
    asset_id: Optional[int] = None,
    _actor: Actor = Depends(current_actor),
):
    from backend.src.pipeline_intel.queries import list_changes

    with session_scope() as session:
        return ok(
            {
                "items": list_changes(
                    session,
                    limit=limit,
                    change_kind=change_kind,
                    source=source,
                    asset_id=asset_id,
                )
            }
        )


@app.get("/api/pipeline/deals")
def api_pipeline_deals(
    limit: int = Query(50, ge=1, le=200),
    _actor: Actor = Depends(current_actor),
):
    from backend.src.pipeline_intel.queries import list_deals

    with session_scope() as session:
        return ok({"items": list_deals(session, limit=limit)})


@app.post("/api/pipeline/deals/sync")
def api_pipeline_deals_sync(actor: Actor = Depends(admin_actor)):
    from backend.src.pipeline_intel.news_deals import sync_deals_from_news

    with session_scope() as session:
        stats = sync_deals_from_news(session)
    record_audit(actor_id=actor.id, action="pipeline_deals_sync", target="pipeline", detail=str(stats))
    return ok(stats)


@app.get("/api/pipeline/snapshots/{snapshot_id}")
def api_pipeline_snapshot(snapshot_id: int, _actor: Actor = Depends(current_actor)):
    from backend.src.pipeline_intel.queries import get_snapshot

    with session_scope() as session:
        data = get_snapshot(session, snapshot_id)
    if data is None:
        raise HTTPException(status_code=404, detail="快照不存在")
    return ok(data)


@app.get("/api/pipeline/snapshots/{snapshot_id}/images/{index}")
def api_pipeline_snapshot_image(
    snapshot_id: int,
    index: int,
    _actor: Actor = Depends(current_actor),
):
    from backend.src.pipeline_intel.queries import resolve_snapshot_image

    with session_scope() as session:
        path = resolve_snapshot_image(session, snapshot_id, index)
    if path is None:
        raise HTTPException(status_code=404, detail="图片不存在")
    return FileResponse(path)


@app.get("/api/pipeline/crawl-config")
def api_pipeline_crawl_config_get(_actor: Actor = Depends(admin_actor)):
    from backend.src.pipeline_intel.schedule import get_pipeline_crawl_config

    return ok(get_pipeline_crawl_config())


@app.put("/api/pipeline/crawl-config")
def api_pipeline_crawl_config_put(
    body: PipelineCrawlConfigUpdate,
    actor: Actor = Depends(admin_actor),
):
    from backend.src.pipeline_intel.schedule import update_pipeline_crawl_config

    try:
        payload = update_pipeline_crawl_config(
            running=body.running,
            schedule_mode=body.schedule_mode,
            interval_minutes=body.interval_minutes,
            daily_time=body.daily_time,
            weekly_day=body.weekly_day,
            crawler_keys=body.crawler_keys,
            source_url=body.source_url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    record_audit(actor_id=actor.id, action="pipeline_crawl_config", target="pipeline", detail=str(payload))
    return ok(payload)


@app.post("/api/pipeline/sync")
async def api_pipeline_sync(
    body: PipelineSyncRequest,
    actor: Actor = Depends(admin_actor),
):
    ready = vision_readiness()
    if not ready.get("ready"):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "vision_not_configured",
                "message": ready.get("message")
                or "请先在设置 → 大模型中配置并启用视觉模型",
            },
        )
    from backend.src.pipeline_intel.service import run_pipeline_sync

    try:
        result = await run_pipeline_sync(force=body.force, source_url=body.source_url)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)[:500]) from exc
    record_audit(
        actor_id=actor.id,
        action="pipeline_sync",
        target="pipeline",
        detail=f"force={body.force}",
    )
    return ok(result)


@app.get("/api/admin/rag-config")
def api_admin_rag_config_get(_actor: Actor = Depends(admin_actor)):
    from backend.src.rag.settings import get_or_create_rag_config, rag_config_to_dict

    with session_scope() as session:
        row = get_or_create_rag_config(session)
        return ok(rag_config_to_dict(row))


@app.put("/api/admin/rag-config")
def api_admin_rag_config_put(body: RagConfigUpdate, actor: Actor = Depends(admin_actor)):
    from backend.src.rag.settings import rag_config_to_dict, update_rag_settings

    with session_scope() as session:
        row = update_rag_settings(
            session,
            top_k=body.top_k,
            min_relevance_score=body.min_relevance_score,
            hybrid_vector_weight=body.hybrid_vector_weight,
            rerank_pool_multiplier=body.rerank_pool_multiplier,
            history_turns=body.history_turns,
            temperature=body.temperature,
        )
        payload = rag_config_to_dict(row)
    record_audit(
        actor_id=actor.id,
        action="rag_config_update",
        target="rag_config",
        detail=(
            f"top_k={payload['top_k']},min_score={payload['min_relevance_score']},"
            f"vec_w={payload['hybrid_vector_weight']},mult={payload['rerank_pool_multiplier']},"
            f"hist={payload['history_turns']},temp={payload['temperature']}"
        ),
    )
    return ok(payload)


@app.get("/api/admin/crawlers")
def api_admin_crawlers_list(_actor: Actor = Depends(admin_actor)):
    from backend.src.crawlers.settings_store import list_crawler_settings, seed_crawler_settings

    with session_scope() as session:
        seed_crawler_settings(session)
        return ok(list_crawler_settings(session))


@app.put("/api/admin/crawlers/{crawler_key}")
def api_admin_crawler_update(
    crawler_key: str,
    body: CrawlerSettingUpdate,
    actor: Actor = Depends(admin_actor),
):
    from backend.src.crawlers.settings_store import update_crawler_setting

    try:
        with session_scope() as session:
            payload = update_crawler_setting(
                session,
                crawler_key,
                enabled=body.enabled,
                page_count=body.page_count,
                concurrency=body.concurrency,
                fetch_details=body.fetch_details,
            )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    record_audit(
        actor_id=actor.id,
        action="crawler_setting_update",
        target=f"crawler:{crawler_key}",
        detail=str(payload),
    )
    return ok(payload)


@app.get("/api/admin/keywords")
def api_admin_keywords_list(
    category: Optional[str] = None,
    q: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _actor: Actor = Depends(admin_actor),
):
    from backend.src.processors.keyword_store import list_keywords

    with session_scope() as session:
        return ok(list_keywords(session, category=category, q=q, page=page, page_size=page_size))


@app.post("/api/admin/keywords")
def api_admin_keywords_create(body: FilterKeywordCreate, actor: Actor = Depends(admin_actor)):
    from backend.src.processors.filter import invalidate_keyword_cache
    from backend.src.processors.keyword_store import create_keyword, keyword_to_dict

    try:
        with session_scope() as session:
            row = create_keyword(
                session,
                category=body.category,
                canonical=body.canonical,
                aliases=body.aliases,
            )
            payload = keyword_to_dict(row)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    invalidate_keyword_cache()
    record_audit(
        actor_id=actor.id,
        action="keyword_create",
        target=f"keyword:{payload['id']}",
        detail=payload["canonical"],
    )
    return ok(payload)


@app.put("/api/admin/keywords/{keyword_id}")
def api_admin_keywords_update(
    keyword_id: int,
    body: FilterKeywordUpdate,
    actor: Actor = Depends(admin_actor),
):
    from backend.src.processors.filter import invalidate_keyword_cache
    from backend.src.processors.keyword_store import keyword_to_dict, update_keyword

    try:
        with session_scope() as session:
            row = update_keyword(
                session,
                keyword_id,
                category=body.category,
                canonical=body.canonical,
                aliases=body.aliases,
            )
            payload = keyword_to_dict(row)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    invalidate_keyword_cache()
    record_audit(
        actor_id=actor.id,
        action="keyword_update",
        target=f"keyword:{keyword_id}",
        detail=payload["canonical"],
    )
    return ok(payload)


@app.delete("/api/admin/keywords/{keyword_id}")
def api_admin_keywords_delete(keyword_id: int, actor: Actor = Depends(admin_actor)):
    from backend.src.processors.filter import invalidate_keyword_cache
    from backend.src.processors.keyword_store import delete_keyword

    try:
        with session_scope() as session:
            delete_keyword(session, keyword_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    invalidate_keyword_cache()
    record_audit(
        actor_id=actor.id,
        action="keyword_delete",
        target=f"keyword:{keyword_id}",
    )
    return ok({"deleted": keyword_id})


@app.post("/api/admin/keywords/reimport")
def api_admin_keywords_reimport(
    body: KeywordReimportRequest,
    actor: Actor = Depends(admin_actor),
):
    from backend.src.processors.filter import invalidate_keyword_cache
    from backend.src.processors.keyword_store import import_keywords_from_yaml
    from backend.src.models.filter_keyword import FilterKeyword
    from sqlalchemy import delete, func, select

    with session_scope() as session:
        count = session.scalar(select(func.count()).select_from(FilterKeyword)) or 0
        if count > 0 and not body.confirm_overwrite:
            raise HTTPException(
                status_code=400,
                detail="表非空；需 confirm_overwrite=true 才会清空并重新从 YAML 导入",
            )
        if count > 0 and body.confirm_overwrite:
            session.execute(delete(FilterKeyword))
            session.flush()
        inserted = import_keywords_from_yaml(session, only_if_empty=False)
    invalidate_keyword_cache()
    record_audit(
        actor_id=actor.id,
        action="keyword_reimport",
        target="filter_keyword",
        detail=f"inserted={inserted}",
    )
    return ok({"inserted": inserted})


@app.post("/api/reports/export")
async def api_report_export(body: ReportExportRequest, actor: Actor = Depends(current_actor)):
    path = await export_report(
        question=body.question,
        answer=body.answer,
        sources=body.sources,
        fmt=body.fmt,
    )
    remember_report(actor.id, path.name)
    return ok({"path": str(path), "filename": path.name})


@app.get("/api/reports/download/{filename}")
def api_report_download(filename: str, actor: Actor = Depends(current_actor)):
    if "/" in filename or "\\" in filename or not user_owns_report(actor.id, filename):
        raise HTTPException(404, "file not found")
    base = Path(__file__).resolve().parents[3] / "outjson" / "reports"
    path = (base / filename).resolve()
    if not str(path).startswith(str(base.resolve())) or not path.exists():
        raise HTTPException(404, "file not found")
    return FileResponse(path, filename=path.name)


class SPAStaticFiles(StaticFiles):
    """构建产物里没有的前端路由回退到 index.html。带后缀的静态文件仍返回 404。"""

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404 and "." not in Path(path).name:
                return await super().get_response("index.html", scope)
            raise


if FRONTEND_DIST.exists():
    app.mount("/", SPAStaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
