# DrugIntel.ai

医药情报智能监测系统（毕业设计基线）：**采集 → 处理 → 入库/聚类 → RAG 问答 → 监测订阅/告警 → 统计与监控**。

技术栈：PostgreSQL（pgvector）· FastAPI · Celery · Vue 3 · SiliconFlow（对话 / 嵌入 / 重排）。

## 功能概览

| 能力 | 说明 |
|------|------|
| 多源采集 | bioon / GlobeNewswire / PR Newswire 等；监控页选爬虫与节奏后启动 |
| 处理入库 | 关键词过滤、摘要、向量化、增量采集 |
| 事件聚类 | 相似新闻归并为事件簇并选出代表稿 |
| RAG 问答 | 意图识别 → 原句检索 →（不足则改写补检索 / 澄清）→ 流式回答；支持引用与报告导出 |
| 页面感知浮窗 | 全站右下角问答（`/chat`、`/login` 除外）；新闻详情页会带上当前 `news_id` 优先作答 |
| 监测订阅 | Watchlist 关键词命中后邮件通知 |
| 系统设置 | 大模型配置、RAG 参数、**邮件 SMTP**、爬虫注册表、过滤关键词（管理员） |

## 快速开始

### 方式 A：一键 Docker（推荐演示）

```bash
# 复制并填写 .env（至少 SILICONFLOW_API_KEY、ADMIN_EMAIL、ADMIN_PASSWORD）
cp .env.example .env

docker compose up -d --build
```

浏览器打开 http://127.0.0.1:8000 。镜像内已打包前端；容器启动时自动建表；采集默认停止，在 **爬虫监控** 页勾选来源并启动。

### 方式 B：本机热更新开发（`start.py`）

数据库与 Redis 仍用 Docker，前后端在本机：

```bash
# 需已配置 .venv / 依赖，以及 .env
python start.py
```

- 页面：http://127.0.0.1:5173  
- API：http://127.0.0.1:8000  
- 结束：`Ctrl+C`

仅改前端时也可：`cd frontend && npm install && npm run dev`（开发服代理 `/api` 到 8000）。

### 首次使用

1. 用 `.env` 中的管理员账号登录  
2. **系统设置 → 大模型**：配置并启用一套接口（或依赖 `.env` 中的 SiliconFlow 默认）  
3. **爬虫监控**：勾选来源、选择节奏，点启动  
4. **系统设置 → 邮件服务**（可选）：填写 SMTP；网易等服务商若 587 超时，改用 **端口 465**（自动 SSL）  
5. **监测订阅**：添加关注实体与通知邮箱  

## 环境变量（摘要）

详见 [`.env.example`](.env.example)。常用项：

| 变量 | 说明 |
|------|------|
| `SILICONFLOW_*` | 对话 / 嵌入 / 重排模型与密钥（也可在管理端「大模型」配置并加密入库） |
| `DATABASE_URL` / `REDIS_URL` | 本机直连；Compose 内会覆盖为主机名 |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | 首个管理员（库中已有管理员时不覆盖密码） |
| `SMTP_*` | 告警邮件回退配置；**优先使用管理端「邮件服务」写入的库配置** |
| `RAG_MIN_RELEVANCE_SCORE` | RAG 相关度阈值回退；正式以管理端 RAG 配置为准 |

## 模块地图

| 能力 | 路径 |
|------|------|
| 爬虫 | `backend/src/crawlers/` |
| 处理流水线 | `backend/src/processors/` |
| 聚类 | `backend/src/clustering/` |
| RAG / 检索 | `backend/src/rag/`、`backend/src/search/` |
| 告警 / SMTP | `backend/src/alerts/` |
| 报告 | `backend/src/reports/` |
| 统计 / 监控 | `backend/src/stats/`、`backend/src/monitor/` |
| API | `backend/src/api/app.py` |
| 前端 | `frontend/` |
| Celery | `tasks/celery_app.py` |

## API 摘要

- 健康 / 监控：`GET /api/health`、`GET /api/monitor/status`
- 采集：`GET/POST /api/crawl/*`
- 新闻 / 事件：`GET /api/news`、`GET /api/news/{id}`、`GET /api/events`
- 问答：`POST /api/chat/ask`、`WS /ws/chat`（可带 `news_id`）
- 订阅：`CRUD /api/watchlist`、`GET /api/alerts/mail-status`
- 管理端：`/api/admin/rag-config`、`/api/admin/smtp-config`、`/api/admin/crawlers`、`/api/admin/keywords`、`/api/llm/profiles*`
- 统计 / 报告：`GET /api/stats/*`、`POST /api/reports/export`
- Swagger：`/docs`

## 文档

- [部署说明](docs/DEPLOY.md)
- [用户指南](docs/USER_GUIDE.md)
- [实现计划](IMPLEMENTATION_PLAN.md)
- [项目结构](docs/PROJECT_STRUCTURE.md)

## 常见问题

- **问答无结果**：先完成采集入库，确认新闻已向量化；可在系统设置调整 RAG `top_k` / 相关度阈值。  
- **邮件测试超时**：网易 126/163 等在部分网络下 587+STARTTLS 易超时，改用 **465**（系统会走 SSL）。密码多为邮箱**授权码**。  
- **Windows 连库卡住**：`DATABASE_URL` 使用 `127.0.0.1`，避免 `localhost` 解析到 IPv6。  
- **定时告警 / 采集**：依赖 Celery worker 与 beat（Compose 已包含；`start.py` 也会拉起相关进程）。  
