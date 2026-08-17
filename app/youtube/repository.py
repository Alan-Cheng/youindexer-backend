"""Persistence operations for YouTube discovery and processing state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.database.models import (
    OutboxEvent,
    SearchIndexJob,
    SearchQuery,
    SearchQueryResult,
    Transcript,
    YouTubeVideo,
)
from app.transcription.service import SubtitleWorkerResult
from app.transcription.youtube import SUPPORTED_LANGUAGES
from app.youtube.search import YouTubeSearchResult


class YouTubeRepositoryError(RuntimeError):
    """Raised when a YouTube workflow record cannot be persisted."""


@dataclass(frozen=True, slots=True)
class TranscriptState:
    language: str
    status: str
    object_name: str | None
    segment_count: int | None
    last_error: str | None
    index_status: str | None
    indexed_at: datetime | None


@dataclass(frozen=True, slots=True)
class VideoIndexState:
    youtube_video_id: str
    title: str
    transcripts: tuple[TranscriptState, ...]


def save_search_results(
    session: Session,
    *,
    query: str,
    locale: str,
    requested_limit: int,
    results: list[YouTubeSearchResult],
) -> None:
    """Upsert discovered videos and preserve this search result ordering."""
    search_record = SearchQuery(
        query=query,
        locale=locale,
        requested_limit=requested_limit,
        result_count=len(results),
    )
    session.add(search_record)
    session.flush()

    for position, result in enumerate(results):
        statement = (
            insert(YouTubeVideo)
            .values(
                youtube_video_id=result.video_id,
                canonical_url=result.url,
                title=result.title,
                channel_name=result.channel_name,
                channel_url=result.channel_url,
                thumbnail_url=result.thumbnail_url,
                duration_text=result.duration,
                published_text=result.published_text,
                view_count_text=result.view_count_text,
                description=result.description,
            )
            .on_conflict_do_update(
                index_elements=[YouTubeVideo.youtube_video_id],
                set_={
                    "canonical_url": result.url,
                    "title": result.title,
                    "channel_name": result.channel_name,
                    "channel_url": result.channel_url,
                    "thumbnail_url": result.thumbnail_url,
                    "duration_text": result.duration,
                    "published_text": result.published_text,
                    "view_count_text": result.view_count_text,
                    "description": result.description,
                    "last_seen_at": datetime.now(UTC),
                },
            )
            .returning(YouTubeVideo.id)
        )
        video_id = session.execute(statement).scalar_one()
        session.add(
            SearchQueryResult(
                search_query_id=search_record.id,
                video_id=video_id,
                position=position,
            )
        )
    session.commit()


def request_video_indexing(
    session: Session, youtube_video_id: str
) -> VideoIndexState | None:
    """Create one durable transcription request for a discovered video."""
    video = session.scalar(
        select(YouTubeVideo)
        .where(YouTubeVideo.youtube_video_id == youtube_video_id)
        .with_for_update()
    )
    if video is None:
        return None

    transcripts = {
        transcript.language: transcript
        for transcript in session.scalars(
            select(Transcript).where(Transcript.video_id == video.id)
        )
    }
    languages_to_fetch: list[str] = []
    for language in SUPPORTED_LANGUAGES:
        transcript = transcripts.get(language)
        if transcript is None:
            transcript = Transcript(
                video_id=video.id, language=language, status="pending"
            )
            session.add(transcript)
            transcripts[language] = transcript
            languages_to_fetch.append(language)
        elif transcript.status == "failed":
            transcript.status = "pending"
            transcript.last_error = None
            languages_to_fetch.append(language)

        if transcript.status == "stored" and transcript.content_hash:
            job = session.scalar(
                select(SearchIndexJob)
                .where(
                    SearchIndexJob.transcript_id == transcript.id,
                    SearchIndexJob.index_alias == settings.opensearch_subtitle_alias,
                )
                .with_for_update()
            )
            needs_indexing = job is None
            if job is None:
                job = SearchIndexJob(
                    transcript_id=transcript.id,
                    index_alias=settings.opensearch_subtitle_alias,
                    status="pending",
                )
                session.add(job)
                session.flush()
            if job.status == "failed":
                job.status = "pending"
                job.last_error = None
                needs_indexing = True
            if needs_indexing:
                session.add(
                    OutboxEvent(
                        event_type="subtitle.index.requested",
                        aggregate_type="search_index_job",
                        aggregate_id=str(job.id),
                        deduplication_key=(f"subtitle-reindex:{job.id}:{uuid4().hex}"),
                        payload={"index_job_id": job.id},
                        status="pending",
                    )
                )

    for language in languages_to_fetch:
        session.add(
            OutboxEvent(
                event_type="youtube.transcription.requested",
                aggregate_type="transcript",
                aggregate_id=f"{video.id}:{language}",
                deduplication_key=(
                    f"youtube-transcription:{video.id}:{language}:{uuid4().hex}"
                ),
                payload={
                    "video_id": video.id,
                    "video_url": video.canonical_url,
                    "language": language,
                },
                status="pending",
            )
        )
    session.commit()
    return get_video_index_state(session, youtube_video_id)


def mark_transcription_running(
    session: Session,
    video_id: int,
    requested_languages: tuple[str, ...],
    *,
    include_running: bool = False,
) -> tuple[str, ...]:
    transcripts = session.scalars(
        select(Transcript)
        .where(
            Transcript.video_id == video_id,
            Transcript.language.in_(requested_languages),
        )
        .with_for_update()
    )
    languages: list[str] = []
    for transcript in transcripts:
        if transcript.status == "pending" or (
            include_running and transcript.status == "running"
        ):
            transcript.status = "running"
            transcript.attempt_count += 1
            transcript.last_error = None
            languages.append(transcript.language)
    session.commit()
    return tuple(languages)


def mark_transcription_failed(
    session: Session, video_id: int, languages: tuple[str, ...], error: str
) -> None:
    transcripts = session.scalars(
        select(Transcript).where(Transcript.video_id == video_id).with_for_update()
    )
    for transcript in transcripts:
        if transcript.language in languages and transcript.status not in {
            "stored",
            "unavailable",
        }:
            transcript.status = "failed"
            transcript.last_error = error[:4000]
    session.commit()


def record_transcription_result(
    session: Session, video_id: int, result: SubtitleWorkerResult
) -> None:
    """Atomically save MinIO results, index jobs, and indexing outbox events."""
    transcripts = {
        transcript.language: transcript
        for transcript in session.scalars(
            select(Transcript).where(Transcript.video_id == video_id).with_for_update()
        )
    }
    stored_languages = {item.language for item in result.stored_subtitles}
    now = datetime.now(UTC)

    for stored in result.stored_subtitles:
        transcript = transcripts[stored.language]
        transcript.status = "stored"
        transcript.source_language = stored.source_language
        transcript.source = stored.source
        transcript.object_name = stored.object_name
        transcript.content_hash = stored.content_hash
        transcript.segment_count = stored.segment_count
        transcript.fetched_at = datetime.fromisoformat(stored.fetched_at)
        transcript.stored_at = now
        transcript.last_error = None
        session.flush()

        job = session.scalar(
            select(SearchIndexJob)
            .where(
                SearchIndexJob.transcript_id == transcript.id,
                SearchIndexJob.index_alias == settings.opensearch_subtitle_alias,
            )
            .with_for_update()
        )
        if job is None:
            job = SearchIndexJob(
                transcript_id=transcript.id,
                index_alias=settings.opensearch_subtitle_alias,
                status="pending",
            )
            session.add(job)
            session.flush()
        elif job.status == "indexed" and job.generation_id == stored.content_hash:
            continue
        else:
            job.status = "pending"
            job.last_error = None

        session.execute(
            insert(OutboxEvent)
            .values(
                event_type="subtitle.index.requested",
                aggregate_type="search_index_job",
                aggregate_id=str(job.id),
                deduplication_key=f"subtitle-index:{job.id}:{stored.content_hash}",
                payload={"index_job_id": job.id},
                status="pending",
            )
            .on_conflict_do_nothing(index_elements=[OutboxEvent.deduplication_key])
        )

    for language in result.unavailable_languages:
        transcript = transcripts[language]
        if language not in stored_languages:
            transcript.status = "unavailable"
            transcript.last_error = None
    session.commit()


def get_video_index_state(
    session: Session, youtube_video_id: str
) -> VideoIndexState | None:
    video = session.scalar(
        select(YouTubeVideo)
        .where(YouTubeVideo.youtube_video_id == youtube_video_id)
        .options(
            selectinload(YouTubeVideo.transcripts).selectinload(Transcript.index_jobs)
        )
    )
    if video is None:
        return None
    transcript_states = []
    for transcript in sorted(video.transcripts, key=lambda item: item.language):
        job = next(
            (
                item
                for item in transcript.index_jobs
                if item.index_alias == settings.opensearch_subtitle_alias
            ),
            None,
        )
        transcript_states.append(
            TranscriptState(
                language=transcript.language,
                status=transcript.status,
                object_name=transcript.object_name,
                segment_count=transcript.segment_count,
                last_error=transcript.last_error,
                index_status=job.status if job else None,
                indexed_at=job.indexed_at if job else None,
            )
        )
    return VideoIndexState(
        youtube_video_id=video.youtube_video_id,
        title=video.title,
        transcripts=tuple(transcript_states),
    )
