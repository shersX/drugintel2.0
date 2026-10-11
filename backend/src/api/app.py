"""FastAPI 应用：整合新闻、事件、问答、告警、统计、监控、报告。"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

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
    CrawlStartRequest,
    LlmProfileTest,
    LlmProfileWrite,
    LoginRequest,
    PasswordReset,
    ProfileUpdate,
    ReportExportRequest,
    UserCreate,
    WatchlistCreate,
)
from backend.src.clustering.service import run_clustering
from backend.src.core.logger import get_logger
from backend.src.crawl.schedule import (
    CrawlConfigError,
    config_payload,
    start_schedule,
    status_payload,
    stop_schedule,
)
from backend.src.db.schema import ensure_schema
from backend.src.db.session import session_scope
from backend.src.llm.profiles import (
    DimensionMismatch,
    LlmProfileError,
    activate_profile,
    create_profile,
    delete_profile,
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
def api_stats_overview(_actor: Actor = Depends(current_actor)):
    with session_scope() as session:
        return ok(overview_stats(session))


@app.get("/api/stats/stages")
def api_stats_stages(_actor: Actor = Depends(current_actor)):
    with session_scope() as session:
        return ok(development_stage_stats(session))


@app.get("/api/stats/trend")
def api_stats_trend(days: int = Query(14, ge=1, le=90), _actor: Actor = Depends(current_actor)):
    with session_scope() as session:
        return ok(news_trend_stats(session, days=days))


@app.get("/api/stats/keywords")
def api_stats_keywords(limit: int = Query(20, ge=1, le=100), _actor: Actor = Depends(current_actor)):
    with session_scope() as session:
        return ok(hot_keywords_stats(session, limit=limit))


def _like_term(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


@app.get("/api/news")
def api_news_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    crawler: Optional[str] = None,
    q: Optional[str] = None,
    _actor: Actor = Depends(current_actor),
):
    from sqlalchemy import func

    with session_scope() as session:
        base = select(News)
        if crawler:
            base = base.where(News.crawler == crawler)
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
                "publish_time": str(n.publish_time) if n.publish_time else None,
                "detail_url": n.detail_url,
                "event_id": n.event_id,
                "is_representative": n.is_representative,
            }
            for n in rows
        ]
        return ok({"total": int(total), "page": page, "page_size": page_size, "items": items})


@app.get("/api/news/{news_id}")
def api_news_detail(news_id: int, _actor: Actor = Depends(current_actor)):
    with session_scope() as session:
        news = session.get(News, news_id)
        if news is None:
            raise HTTPException(404, "news not found")
        related = []
        if news.event_id:
            related_rows = session.scalars(
                select(News)
                .where(News.event_id == news.event_id)
                .where(News.id != news.id)
                .limit(20)
            ).all()
            related = [{"id": r.id, "title": r.title} for r in related_rows]
        return ok(
            {
                "id": news.id,
                "title": news.title,
                "content": news.content,
                "abstract": news.abstract,
                "source": news.source,
                "crawler": news.crawler,
                "publish_time": str(news.publish_time) if news.publish_time else None,
                "detail_url": news.detail_url,
                "matched_keywords": news.matched_keywords,
                "event_id": news.event_id,
                "is_representative": news.is_representative,
                "related_news": related,
            }
        )


@app.get("/api/events")
def api_events(page: int = 1, page_size: int = 20, _actor: Actor = Depends(current_actor)):
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


@app.post("/api/chat/ask")
async def api_chat_ask(body: AskRequest, actor: Actor = Depends(current_actor)):
    try:
        consume_chat_quota(actor.id)
    except QuotaError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    result = await ask(body.query, top_k=body.top_k, session_id=body.session_id)
    return ok(
        {
            "session_id": result.session_id,
            "intent": result.intent.intent.value,
            "answer": result.answer,
            "sources": result.sources,
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
            async for event in ask_stream(
                query,
                top_k=int(payload.get("top_k") or 5),
                session_id=payload.get("session_id"),
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


@app.post("/api/crawl/start")
def api_crawl_start(body: CrawlStartRequest, actor: Actor = Depends(admin_actor)):
    try:
        payload = start_schedule(body.schedule_mode, body.daily_time, body.crawler_keys)
    except CrawlConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    record_audit(actor_id=actor.id, action="crawl_start", target="crawl")
    return ok(payload)


@app.post("/api/crawl/stop")
def api_crawl_stop(actor: Actor = Depends(admin_actor)):
    payload = stop_schedule()
    record_audit(actor_id=actor.id, action="crawl_stop", target="crawl")
    return ok(payload)


@app.get("/api/crawl/config")
def api_crawl_config(_actor: Actor = Depends(admin_actor)):
    return ok(config_payload())


@app.get("/api/crawl/status")
def api_crawl_status(_actor: Actor = Depends(current_actor)):
    return ok(status_payload())


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
