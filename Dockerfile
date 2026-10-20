# Build stage: resolve dependencies from uv.lock into a virtual environment.
FROM python:3.13-slim AS build

COPY --from=ghcr.io/astral-sh/uv:0.9.17 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Dependencies first, so code changes do not invalidate this layer.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-dev --no-install-project

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable


# Runtime stage: only the virtual environment, no build tools or sources.
FROM python:3.13-slim

RUN useradd --system --create-home --uid 1000 app \
    && mkdir /data \
    && chown app:app /data

COPY --from=build --chown=app:app /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    CACHE_TEST_DATABASE_URL=sqlite:////data/cache.db

USER app
WORKDIR /data
VOLUME /data
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"]

CMD ["cache-test"]
