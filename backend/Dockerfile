# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:0.13.0 AS uv

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY --from=uv /uv /uvx /bin/
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY app ./app

EXPOSE 8000

CMD ["sh", "-c", "python -m app.seed && exec gunicorn --workers 4 --worker-class sync --bind 0.0.0.0:8000 'app:criar_app()'"]

FROM runtime AS testes-base

RUN uv sync --locked --dev --no-install-project

FROM testes-base AS testes

COPY tests ./tests

FROM testes-base AS testes-navegador-base

ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

RUN uv sync --locked --group navegador --no-install-project \
    && playwright install --with-deps chromium

FROM testes-navegador-base AS testes-navegador

COPY tests ./tests
