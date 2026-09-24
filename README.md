# DrugIntel.ai（毕业设计完整基线）

医药情报智能监测系统：采集 → 处理 → 入库/聚类 → RAG 问答 → 告警/统计/监控 → API/前端。

## 快速开始

```bash
# 1) 依赖
uv sync

# 2) 基础设施（WSL）
export PGDATA_HOST_PATH=$HOME/drugintel-pgdata
docker compose up -d
uv run python scripts/init_db.py

# 3) 采集+处理+聚类
uv run python main.py

# 4) API
uv run uvicorn backend.src.api.app:app --host 0.0.0.0 --port 8000

# 5) 前端
cd frontend && npm install && npm run dev
```

文档：

- [部署说明](docs/DEPLOY.md)
- [用户指南](docs/USER_GUIDE.md)
- [实现计划](IMPLEMENTATION_PLAN.md)

## 模块地图

| 能力 | 路径 |
|------|------|
| 爬虫 | `backend/src/crawlers/` |
| 处理流水线 | `backend/src/processors/` |
| 聚类 | `backend/src/clustering/` |
| RAG/检索 | `backend/src/rag/`、`backend/src/search/` |
| 告警 | `backend/src/alerts/` |
| 报告 | `backend/src/reports/` |
| 统计/监控 | `backend/src/stats/`、`backend/src/monitor/` |
| API | `backend/src/api/app.py` |
| 前端 | `frontend/` |
| Celery | `tasks/celery_app.py` |

## API 摘要

- `GET /api/health` / `GET /api/monitor/status`
- `GET /api/news` / `GET /api/news/{id}` / `GET /api/events`
- `POST /api/chat/ask` / `WS /ws/chat`
- `CRUD /api/watchlist`
- `GET /api/stats/*`
- `POST /api/reports/export` / `GET /api/reports/download/{file}`
- Swagger: `/docs`
