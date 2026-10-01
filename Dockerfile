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
# Stage 2: 构建后端（Python + uv）
# ============================================================
FROM python:3.12-slim AS backend-build

# 安装 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# 先复制依赖清单，利用 Docker 缓存层
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# 复制项目源码
COPY backend/ ./backend/
COPY config/ ./config/
COPY scripts/ ./scripts/
COPY main.py ./

# 从前端构建阶段复制产物
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

# ============================================================
# Stage 3: 运行阶段（精简镜像）
# ============================================================
FROM python:3.12-slim AS runtime

WORKDIR /app

# 复制虚拟环境和源代码
COPY --from=backend-build /app /app

# 激活虚拟环境
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# 环境变量默认值（可通过 docker-compose 或 .env 覆盖）
ENV DATABASE_URL="postgresql+psycopg://user:password@db:5432/drugintel"
ENV REDIS_URL="redis://redis:6379/0"

EXPOSE 8000

CMD ["uvicorn", "backend.src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
