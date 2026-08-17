"""Celery tasks for the transcription queue."""

from app.transcription.service import process_youtube_subtitles
from app.transcription.storage import SubtitleStorageError
from app.transcription.youtube import YouTubeSubtitleError
from app.worker.celery_app import celery_app


@celery_app.task(
    bind=True,
    name="app.worker.tasks.store_youtube_subtitles",
    queue="transcription",
    acks_late=True,
    autoretry_for=(YouTubeSubtitleError, SubtitleStorageError),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def store_youtube_subtitles(self, video_url: str) -> dict:
    """Fetch zh-TW/English YouTube subtitles and store normalized JSON in MinIO."""
    return process_youtube_subtitles(video_url).as_dict()
