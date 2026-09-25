FROM python:3.12-slim AS base
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never PYTHONUNBUFFERED=1
WORKDIR /app

# спочатку лише залежності — шар кешується, поки не змінився lock-файл
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
# PORT задає хмарна платформа (Railway); FORWARDED_ALLOW_IPS — довірені проксі для X-Forwarded-For
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn tendoor.api.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
