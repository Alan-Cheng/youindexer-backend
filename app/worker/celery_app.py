"""Celery application shared by API producers and workers."""

from celery import Celery

from app.config import settings

celery_app = Celery(
    "youindexer",
    broker=settings.redis_url,
    backend=settings.celery_result_backend,
    include=["app.worker.tasks"],
)
celery_app.conf.update(
    accept_content=["json"],
    broker_connection_retry_on_startup=True,
    result_serializer="json",
    task_default_queue="transcription",
    task_routes={
        "app.worker.tasks.store_youtube_subtitles": {"queue": "transcription"}
    },
    task_serializer="json",
    timezone="UTC",
    worker_prefetch_multiplier=1,
)
