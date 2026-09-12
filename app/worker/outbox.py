"""Transactional outbox publisher for Celery tasks."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from kombu.exceptions import KombuError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import OutboxEvent, SearchIndexJob
from app.worker.celery_app import celery_app

EVENT_TASKS = {
    "youtube.transcription.requested": (
        "app.worker.tasks.store_youtube_subtitles",
        "transcription",
    ),
    "subtitle.index.requested": (
        "app.worker.tasks.index_subtitle",
        "indexing",
    ),
}


def dispatch_pending_events(session: Session, *, batch_size: int = 50) -> int:
    """Publish pending rows; duplicates are safe because consumers are idempotent."""
    now = datetime.now(UTC)
    events = list(
        session.scalars(
            select(OutboxEvent)
            .where(
                OutboxEvent.status == "pending",
                OutboxEvent.available_at <= now,
            )
            .order_by(OutboxEvent.id)
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
    )
    published = 0
    for event in events:
        route = EVENT_TASKS.get(event.event_type)
        if route is None:
            event.status = "failed"
            event.last_error = f"unsupported outbox event type: {event.event_type}"
            continue
        task_name, queue = route
        try:
            celery_app.send_task(task_name, kwargs=event.payload, queue=queue)
        except (KombuError, OSError) as exc:
            event.attempt_count += 1
            event.last_error = str(exc)[:4000]
            delay_seconds = min(300, 2 ** min(event.attempt_count, 8))
            event.available_at = now + timedelta(seconds=delay_seconds)
            continue
        event.status = "published"
        event.published_at = now
        event.last_error = None
        published += 1
        if event.event_type == "subtitle.index.requested":
            job = session.get(SearchIndexJob, int(event.payload["index_job_id"]))
            if job is not None and job.status == "pending":
                job.status = "queued"
    session.commit()
    return published
