# DrugIntel.ai（毕业设计完整基线）

医药情报智能监测系统：采集 → 处理 → 入库/聚类 → RAG 问答 → 告警/统计/监控 → API/前端。

## 快速开始

```bash
# .env 中填写 SILICONFLOW_API_KEY
docker compose up -d
```

浏览器打开 http://127.0.0.1:8000 。镜像构建时已经执行前端打包，页面和 API 由同一个容器提供，不需要再 `npm install`。容器启动时自动建表，采集保持停止。

在监控页选好爬虫和节奏（每小时，或每天的某个时刻）后点「启动」。第一次采集立刻开始，之后按该节奏持续运行。`scripts/init_db.py` 与 `python main.py` 只用于手动补跑。

只在改前端、需要热更新时，才在本机另开开发服务器（API 仍可由上面的容器提供）：

```bash
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
- `GET /api/crawl/config` / `GET /api/crawl/status`
- `POST /api/crawl/start` / `POST /api/crawl/stop`
- `GET /api/news` / `GET /api/news/{id}` / `GET /api/events`
- `POST /api/chat/ask` / `WS /ws/chat`
- `CRUD /api/watchlist`
- `GET /api/stats/*`
- `POST /api/reports/export` / `GET /api/reports/download/{file}`
- Swagger: `/docs`
