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
# Stage 2: 构建后端（Python + pip）
# ============================================================
FROM python:3.12-slim AS backend-build

WORKDIR /app

# 国内镜像，避免 ghcr.io / 默认 PyPI 过慢或失败
ENV PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ENV PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_NO_CACHE_DIR=1

RUN python -m venv /app/.venv
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# 先只装依赖，利用 Docker 缓存层（不装项目本身，与原先 uv sync --no-install-project 一致）
COPY pyproject.toml ./
RUN pip install -U pip && \
    python -c "import subprocess, tomllib; from pathlib import Path; \
deps = tomllib.loads(Path('pyproject.toml').read_text())['project']['dependencies']; \
subprocess.check_call(['pip', 'install', *deps])"

# 复制项目源码
COPY backend/ ./backend/
COPY config/ ./config/
COPY scripts/ ./scripts/
COPY tasks/ ./tasks/
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
COPY docker/entrypoint.sh /entrypoint.sh
# Windows 检出常带 CRLF，shebang 会变成 /bin/sh\r，容器里表现为 entrypoint 找不到。
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

# 激活虚拟环境
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# 环境变量默认值（可通过 docker-compose 或 .env 覆盖）
ENV DATABASE_URL="postgresql+psycopg://user:password@db:5432/drugintel"
ENV REDIS_URL="redis://redis:6379/0"

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "backend.src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
