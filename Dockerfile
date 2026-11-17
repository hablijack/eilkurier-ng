# syntax=docker/dockerfile:1

# ---- build: install locked dependencies + the project into /app/.venv ------------------------
FROM python:3.13-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --no-install-project
COPY README.md ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --no-editable

# ---- runtime ---------------------------------------------------------------------------------
FROM python:3.13-slim
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    EILKURIER_RESOURCE_ROOT=/app \
    XDG_CACHE_HOME=/app/.cache
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY layout ./layout
COPY assets ./assets
# Fetch the Typst packages once at build time: the container then renders offline
# and the cache can stay read-only at runtime.
RUN eilkurier render-sample --output /tmp/warmup.pdf && rm /tmp/warmup.pdf
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health/live', timeout=3)"]
CMD ["uvicorn", "eilkurier.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers"]
