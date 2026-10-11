# DrugIntel.ai 部署说明

## 1. 启动

```bash
uv sync
# .env 中设置 SILICONFLOW_* ；数据库与 Redis 地址可由 compose 覆盖
docker compose up -d
```

`docker compose up` 会构建镜像并启动数据库、Redis、API、Celery worker 和 beat。镜像内已经打包前端，页面与 API 都在 http://127.0.0.1:8000 。容器入口会自动建表。采集保持停止，不会在启动时爬取。

确认：

```bash
docker ps
# drugintel-db / drugintel-redis / drugintel-app / drugintel-worker / drugintel-beat
```

Swagger：http://127.0.0.1:8000/docs

## 2. 采集

打开 http://127.0.0.1:8000/monitor ，勾选爬虫，选择「每小时」或「每天」并指定时刻，然后点「启动」。第一次采集立刻执行（爬取、处理入库、聚类），之后按所选节奏持续运行。点「停止」后不再开始下一轮，已经在跑的那一轮会跑完。

每个爬虫的状态、条数和日志显示在同一页。

改页面并要热更新时，才在本机运行 `cd frontend && npm install && npm run dev`（开发服务器在 5173，并把 `/api` 代理到 8000）。

## 3. 本地只开 API

```bash
uv run uvicorn backend.src.api.app:app --host 0.0.0.0 --port 8000
```

进程启动时会建表。定时采集依赖 worker 与 beat；不用 compose 时：

```bash
uv run celery -A tasks.celery_app.celery_app worker -l info --concurrency 1
uv run celery -A tasks.celery_app.celery_app beat -l info
```

## 4. 手动补跑

```bash
uv run python scripts/init_db.py
uv run python main.py
uv run python main.py --cluster-only
uv run python scripts/ask.py "司美格鲁肽最新进展"
```

`main.py` 不读取监控页上的采集配置。
