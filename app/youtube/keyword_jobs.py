"""Persistent orchestration for keyword searches across selected videos."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.alias.service import AliasServiceError, get_aliases
from app.database.models import (
    KeywordSearchJob,
    KeywordSearchJobVideo,
    YouTubeVideo,
)
from app.indexing import OpenSearchSubtitleIndexer
from app.system_config.service import get_default_subtitle_languages
from app.transcription.storage import MinioSubtitleStorage
from app.youtube.repository import get_video_index_state
from app.youtube.search import YouTubeSearchResult

logger = logging.getLogger(__name__)


def create_keyword_search_job(
    session: Session,
    *,
    query: str,
    locale: str,
    requested_count: int,
    matches_per_video: int,
    results: list[YouTubeSearchResult],
) -> str:
    videos = {
        video.youtube_video_id: video
        for video in session.scalars(
            select(YouTubeVideo).where(
                YouTubeVideo.youtube_video_id.in_([item.video_id for item in results])
            )
        )
    }
    job = KeywordSearchJob(
        query=query,
        locale=locale,
        requested_count=requested_count,
        matches_per_video=matches_per_video,
        status="processing",
    )
    session.add(job)
    session.flush()
    for position, result in enumerate(results):
        session.add(
            KeywordSearchJobVideo(
                job_id=job.id,
                video_id=videos[result.video_id].id,
                position=position,
                status="loading",
                keyword_matches=[],
            )
        )
    if not results:
        job.status = "completed"
        job.completed_at = datetime.now(UTC)
    session.commit()
    return job.id


def _finished(state) -> bool:
    if state is None or not state.transcripts:
        return False
    for transcript in state.transcripts:
        if transcript.status in {"pending", "running"}:
            return False
        if transcript.status == "stored" and transcript.index_status in {
            None,
            "pending",
            "running",
        }:
            return False
    return True


def _search_aliases(query: str) -> list[str]:
    """Get aliases once per job; search still works if the alias service is unavailable."""
    try:
        aliases = asyncio.run(get_aliases(query))
    except AliasServiceError as exc:
        logger.warning("Alias generation failed for keyword search %r: %s", query, exc)
        return []
    return list(dict.fromkeys(alias.strip() for alias in aliases if alias.strip()))


def reconcile_keyword_search_jobs(session: Session) -> int:
    """Persist OpenSearch results for every newly finished job video."""
    jobs = list(
        session.scalars(
            select(KeywordSearchJob)
            .where(KeywordSearchJob.status == "processing")
            .options(
                selectinload(KeywordSearchJob.videos).selectinload(
                    KeywordSearchJobVideo.video
                )
            )
        )
    )
    changed = 0
    indexer = OpenSearchSubtitleIndexer.from_settings()
    languages = get_default_subtitle_languages()
    now = datetime.now(UTC)
    for job in jobs:
        aliases: list[str] | None = None
        for item in job.videos:
            if item.status != "loading":
                continue
            state = get_video_index_state(session, item.video.youtube_video_id)
            if not _finished(state):
                continue
            indexed = any(
                transcript.index_status == "indexed"
                for transcript in state.transcripts
            )
            if not indexed:
                processing_error = next(
                    (
                        transcript.last_error
                        for transcript in state.transcripts
                        if transcript.status == "failed"
                        or (
                            transcript.status == "stored"
                            and transcript.index_status == "failed"
                        )
                    ),
                    None,
                )
                item.status = "failed" if processing_error else "no_match"
                item.last_error = processing_error
                item.completed_at = now
                changed += 1
                continue
            try:
                if aliases is None:
                    aliases = _search_aliases(job.query)
                hits = indexer.search(
                    job.query,
                    aliases=aliases,
                    video_ids=[item.video.youtube_video_id],
                    languages=languages,
                    limit=1,
                    matches_per_video=job.matches_per_video,
                )
                item.keyword_matches = [
                    {
                        "video_id": hit.video_id,
                        "title": hit.title,
                        "language": hit.language,
                        "start_ms": hit.start_ms,
                        "end_ms": hit.end_ms,
                        "seek_seconds": hit.start_ms / 1000,
                        "text": hit.text,
                        "score": hit.score,
                        "matched_keywords": list(hit.matched_keywords),
                        "highlighted_text": hit.highlighted_text,
                    }
                    for hit in hits
                ]
                item.status = "matched" if hits else "no_match"
            except Exception as exc:
                item.status = "failed"
                item.last_error = str(exc)[:4000]
            item.completed_at = now
            changed += 1
        if job.videos and all(item.status != "loading" for item in job.videos):
            job.status = "completed"
            job.completed_at = now
    session.commit()
    return changed


def get_keyword_search_job_snapshot(session: Session, job_id: str) -> dict | None:
    job = session.scalar(
        select(KeywordSearchJob)
        .where(KeywordSearchJob.id == job_id)
        .options(
            selectinload(KeywordSearchJob.videos)
            .selectinload(KeywordSearchJobVideo.video)
            .selectinload(YouTubeVideo.transcripts)
        )
    )
    if job is None:
        return None

    storage = MinioSubtitleStorage.from_settings()
    videos: dict[str, dict[str, Any]] = {}
    for item in sorted(job.videos, key=lambda value: value.position):
        video = item.video
        transcripts = []
        if item.status != "loading":
            for transcript in sorted(video.transcripts, key=lambda value: value.language):
                if transcript.status == "stored" and transcript.object_name:
                    transcripts.append(storage.get_json(transcript.object_name))
        videos[video.youtube_video_id] = {
            "status": item.status,
            "metadata": {
                "video_id": video.youtube_video_id,
                "title": video.title,
                "url": video.canonical_url,
                "channel_name": video.channel_name,
                "channel_url": video.channel_url,
                "thumbnail_url": video.thumbnail_url,
                "duration": video.duration_text,
                "published_text": video.published_text,
                "view_count_text": video.view_count_text,
                "description": video.description,
            },
            "keyword_matches": item.keyword_matches or [],
            "transcripts": transcripts,
            "error": item.last_error,
        }
    completed_count = sum(item.status != "loading" for item in job.videos)
    return {
        "task_id": job.id,
        "query": job.query,
        "status": job.status,
        "requested_count": job.requested_count,
        "video_count": len(job.videos),
        "completed_count": completed_count,
        "matched_count": sum(item.status == "matched" for item in job.videos),
        "videos": videos,
        "error": job.last_error,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "completed_at": job.completed_at,
    }
