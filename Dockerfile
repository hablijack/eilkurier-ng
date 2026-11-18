# syntax=docker/dockerfile:1

# ---- web UI: SvelteKit static build (platform-independent output, so build it natively) -----
FROM --platform=$BUILDPLATFORM node:22-slim AS web
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund
COPY assets /src/assets
COPY frontend ./
RUN npm run build

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

# ---- runtime: one image for app, worker, migrate (and the simulator) -------------------------
FROM python:3.13-slim
ARG VERSION=dev
ARG REVISION=unknown
LABEL org.opencontainers.image.title="Eilkurier" \
      org.opencontainers.image.version=$VERSION \
      org.opencontainers.image.revision=$REVISION \
      org.opencontainers.image.source="https://github.com/hablijack/eilkurier-ng" \
      org.opencontainers.image.licenses="GPL-3.0-or-later"
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    EILKURIER_RESOURCE_ROOT=/app \
    EILKURIER_WEB_ROOT=/app/web \
    XDG_CACHE_HOME=/app/.cache
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY layout ./layout
COPY assets ./assets
COPY prompts ./prompts
COPY --from=web /src/frontend/build ./web
# Fetch the Typst packages once at build time: the container then renders offline
# and the cache can stay read-only at runtime.
RUN eilkurier render-sample --output /tmp/warmup.pdf && rm /tmp/warmup.pdf
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health/live', timeout=3)"]
CMD ["uvicorn", "eilkurier.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers"]
