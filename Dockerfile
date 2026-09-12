FROM denoland/deno:bin-2.9.4 AS deno

FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

COPY --from=deno /deno /usr/local/bin/deno

WORKDIR /app

ENV PATH="/app/.venv/bin:$PATH" \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app

RUN useradd --create-home --uid 10001 worker
USER worker

CMD ["celery", "-A", "app.worker.celery_app:celery_app", "worker", "--queues=transcription", "--loglevel=INFO", "--concurrency=1"]
