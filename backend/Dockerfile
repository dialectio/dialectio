# Dialectio API. Build from the repository root: docker build -f backend/Dockerfile .
FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev
COPY backend/ ./

ENV PATH=/app/.venv/bin:$PATH \
    MEDIA_DIR=/data/media
EXPOSE 8000
# Behind Caddy: trust its X-Forwarded-For, so the rate limit sees visitors' addresses.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
