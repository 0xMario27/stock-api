# 后端 Dockerfile：多阶段构建，uv 安装依赖 + slim 运行时
# Layer 1: 依赖清单（仅 pyproject.toml/uv.lock 变化时重建）
# Layer 2: 源代码（变更时快速重构建，不重装依赖）
FROM python:3.12-slim AS builder

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.6 /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --no-dev --no-install-project

COPY src/ ./src/
COPY gunicorn_conf.py ./
RUN uv sync --no-dev

# 第二阶段：运行时镜像
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN groupadd -r appuser && useradd -r -g appuser appuser

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/pyproject.toml /app/pyproject.toml
COPY --from=builder /app/gunicorn_conf.py /app/gunicorn_conf.py

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

# 生产环境用 gunicorn 多 worker，开发用 uvicorn 单进程热重载
CMD ["gunicorn", "-c", "gunicorn_conf.py", "stock_api.api.app:app"]
