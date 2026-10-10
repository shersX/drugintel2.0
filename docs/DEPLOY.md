# DrugIntel.ai 部署说明

## 1. 基础设施

在 WSL 中：

```bash
export PGDATA_HOST_PATH=$HOME/drugintel-pgdata
mkdir -p "$PGDATA_HOST_PATH"
cd /mnt/d/desktop/new\ drugintel
docker compose up -d
```

确认：

```bash
docker ps
# drugintel-db / drugintel-redis
```

## 2. 后端初始化

```bash
uv sync
# .env 中设置 SILICONFLOW_* / DATABASE_URL / REDIS_URL
uv run python scripts/init_db.py
```

## 3. 采集与处理

```bash
uv run python main.py
# 或只聚类
uv run python main.py --cluster-only
```

## 4. 启动 API

```bash
uv run uvicorn backend.src.api.app:app --host 0.0.0.0 --port 8000
```

Swagger：http://127.0.0.1:8000/docs

## 5. 前端

```bash
cd frontend
npm install
npm run dev
# 或构建后由 FastAPI 静态托管
npm run build
```

## 6. Celery 定时告警（可选）

```bash
uv run celery -A tasks.celery_app.celery_app worker -l info
uv run celery -A tasks.celery_app.celery_app beat -l info
```

## 7. 问答 CLI

```bash
uv run python scripts/ask.py "司美格鲁肽最新进展"
```
