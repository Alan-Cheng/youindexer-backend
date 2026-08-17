"""Celery tasks for transcription, outbox dispatch, and subtitle indexing."""

import random

from app.database.session import SessionLocal
from app.indexing import OpenSearchSubtitleIndexer
from app.indexing.repository import (
    complete_index_job,
    fail_index_job,
    start_index_job,
)
from app.transcription.service import process_youtube_subtitles
from app.transcription.storage import MinioSubtitleStorage
from app.transcription.youtube import SUPPORTED_LANGUAGES, YouTubeRateLimitError
from app.worker.celery_app import celery_app
from app.worker.outbox import dispatch_pending_events
from app.youtube.repository import (
    mark_transcription_failed,
    mark_transcription_running,
    record_transcription_result,
)


@celery_app.task(
    bind=True,
    name="app.worker.tasks.store_youtube_subtitles",
    queue="transcription",
    acks_late=True,
    max_retries=5,
    rate_limit="6/m",
    ignore_result=True,
)
def store_youtube_subtitles(
    self,
    video_url: str,
    video_id: int | None = None,
    language: str | None = None,
) -> dict:
    """Fetch zh-TW/English YouTube subtitles and store normalized JSON in MinIO."""
    languages = (language,) if language else SUPPORTED_LANGUAGES
    try:
        if video_id is not None:
            with SessionLocal() as session:
                languages = mark_transcription_running(
                    session,
                    video_id,
                    languages,
                    include_running=self.request.retries > 0,
                )
            if not languages:
                return {"status": "cached", "video_url": video_url}
        result = process_youtube_subtitles(video_url, languages=languages)
        if video_id is not None:
            with SessionLocal() as session:
                record_transcription_result(session, video_id, result)
        return result.as_dict()
    except Exception as exc:
        retrying = self.request.retries < self.max_retries
        if video_id is not None and not retrying:
            with SessionLocal() as session:
                mark_transcription_failed(session, video_id, languages, str(exc))
        if retrying:
            base_delay = 60 if isinstance(exc, YouTubeRateLimitError) else 10
            countdown = base_delay * (2**self.request.retries) + random.randint(0, 15)
            raise self.retry(exc=exc, countdown=countdown) from exc
        raise


@celery_app.task(
    bind=True,
    name="app.worker.tasks.index_subtitle",
    queue="indexing",
    acks_late=True,
    max_retries=5,
    ignore_result=True,
)
def index_subtitle(self, index_job_id: int) -> dict:
    """Load a normalized subtitle from MinIO and bulk-upsert its segments."""
    try:
        with SessionLocal() as session:
            job = start_index_job(session, index_job_id)
        document = MinioSubtitleStorage.from_settings().get_json(job.object_name)
        indexed = OpenSearchSubtitleIndexer.from_settings().index_document(
            document,
            object_name=job.object_name,
            generation_id=job.generation_id,
        )
        with SessionLocal() as session:
            complete_index_job(session, index_job_id, job.generation_id, indexed)
        return {"index_job_id": index_job_id, "indexed_segments": indexed}
    except Exception as exc:
        retrying = self.request.retries < self.max_retries
        with SessionLocal() as session:
            fail_index_job(session, index_job_id, str(exc), retrying=retrying)
        if retrying:
            raise self.retry(exc=exc, countdown=2**self.request.retries) from exc
        raise


@celery_app.task(
    name="app.worker.tasks.dispatch_outbox_events",
    queue="outbox",
    ignore_result=True,
)
def dispatch_outbox_events() -> dict:
    """Publish a batch of durable outbox events to their Celery queues."""
    with SessionLocal() as session:
        published = dispatch_pending_events(session)
    return {"published": published}
