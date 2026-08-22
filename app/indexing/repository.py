"""Persistence operations for OpenSearch indexing jobs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import SearchIndexJob, Transcript, YouTubeVideo


@dataclass(frozen=True, slots=True)
class IndexJobInput:
    job_id: int
    object_name: str
    generation_id: str
    youtube_video_id: str


def start_index_job(session: Session, job_id: int) -> IndexJobInput:
    row = session.execute(
        select(SearchIndexJob, Transcript, YouTubeVideo)
        .join(Transcript, SearchIndexJob.transcript_id == Transcript.id)
        .join(YouTubeVideo, Transcript.video_id == YouTubeVideo.id)
        .where(SearchIndexJob.id == job_id)
        .with_for_update(of=SearchIndexJob)
    ).one_or_none()
    if row is None:
        raise LookupError(f"index job {job_id} does not exist")
    job, transcript, video = row
    if not transcript.object_name or not transcript.content_hash:
        raise ValueError(f"index job {job_id} has no stored subtitle")
    job.status = "running"
    job.started_at = datetime.now(UTC)
    job.attempt_count += 1
    job.last_error = None
    session.commit()
    return IndexJobInput(
        job_id=job.id,
        object_name=transcript.object_name,
        generation_id=transcript.content_hash,
        youtube_video_id=video.youtube_video_id,
    )


def complete_index_job(
    session: Session, job_id: int, generation_id: str, segment_count: int
) -> None:
    job = session.get(SearchIndexJob, job_id)
    if job is None:
        raise LookupError(f"index job {job_id} does not exist")
    job.status = "indexed"
    job.generation_id = generation_id
    job.chunk_count = segment_count
    job.indexed_at = datetime.now(UTC)
    job.last_error = None
    session.commit()


def fail_index_job(
    session: Session, job_id: int, error: str, *, retrying: bool
) -> None:
    job = session.get(SearchIndexJob, job_id)
    if job is None:
        return
    job.status = "pending" if retrying else "failed"
    job.last_error = error[:4000]
    session.commit()
