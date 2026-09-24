"""FastAPI 应用：整合新闻、事件、问答、告警、统计、监控、报告。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from backend.src.alerts.matcher import (
    create_watchlist,
    delete_watchlist,
    list_watchlists,
)
from backend.src.api.response import fail, ok
from backend.src.api.schemas import AskRequest, ReportExportRequest, WatchlistCreate
from backend.src.clustering.service import run_clustering
from backend.src.db.session import session_scope
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

app = FastAPI(title="DrugIntel.ai API", version="1.0.0")
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


@app.get("/api/monitor/status")
def api_monitor_status():
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


@app.get("/api/news")
def api_news_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    crawler: Optional[str] = None,
):
    from sqlalchemy import func

    with session_scope() as session:
        base = select(News)
        if crawler:
            base = base.where(News.crawler == crawler)
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
def api_news_detail(news_id: int):
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
def api_cluster_run():
    return ok(run_clustering())


@app.post("/api/chat/ask")
async def api_chat_ask(body: AskRequest):
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
            async for event in ask_stream(
                query,
                top_k=int(payload.get("top_k") or 5),
                session_id=payload.get("session_id"),
            ):
                await websocket.send_json(event)
    except WebSocketDisconnect:
        return


@app.get("/api/watchlist")
def api_watchlist_list(user_id: Optional[int] = None):
    with session_scope() as session:
        rows = list_watchlists(session, user_id=user_id)
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
def api_watchlist_create(body: WatchlistCreate):
    with session_scope() as session:
        row = create_watchlist(
            session,
            user_id=body.user_id,
            entity_type=body.entity_type,
            entity_name=body.entity_name,
            email=body.email,
            enabled=body.enabled,
        )
        return ok({"id": row.id})


@app.delete("/api/watchlist/{watchlist_id}")
def api_watchlist_delete(watchlist_id: int):
    with session_scope() as session:
        if not delete_watchlist(session, watchlist_id):
            raise HTTPException(404, "watchlist not found")
        return ok({"deleted": watchlist_id})


@app.post("/api/reports/export")
async def api_report_export(body: ReportExportRequest):
    path = await export_report(
        question=body.question,
        answer=body.answer,
        sources=body.sources,
        fmt=body.fmt,
    )
    return ok({"path": str(path), "filename": path.name})


@app.get("/api/reports/download/{filename}")
def api_report_download(filename: str):
    base = Path(__file__).resolve().parents[3] / "outjson" / "reports"
    path = (base / filename).resolve()
    if not str(path).startswith(str(base.resolve())) or not path.exists():
        raise HTTPException(404, "file not found")
    return FileResponse(path, filename=path.name)


if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
