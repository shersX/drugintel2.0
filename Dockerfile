# ============================================================
# Stage 1: 构建前端 (Vue 3 + Vite → dist)
# ============================================================
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ============================================================
# Stage 2: 运行镜像（Docker 本身隔离环境，用 pip 装依赖即可）
# ============================================================
FROM python:3.12-slim

WORKDIR /app

# 系统依赖（psycopg 等偶发需要）
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# 先装 Python 依赖，利用缓存层
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 复制后端与配置
COPY backend/ ./backend/
COPY config/ ./config/
COPY scripts/ ./scripts/
COPY main.py ./

# 从前端构建阶段复制产物
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

ENV DATABASE_URL="postgresql+psycopg://user:password@db:5432/drugintel"
ENV REDIS_URL="redis://redis:6379/0"
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "backend.src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
