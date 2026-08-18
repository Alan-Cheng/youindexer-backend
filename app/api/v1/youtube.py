"""YouTube search API routes."""

import asyncio
import json
from dataclasses import asdict
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import StreamingResponse

from app.alias.service import AliasServiceError, get_aliases
from app.database.session import SessionLocal
from app.system_config.service import (
    get_default_subtitle_languages,
    get_system_config,
)
from app.transcription.storage import SubtitleStorageError
from app.youtube import (
    YouTubeSearchError,
    YouTubeSuggestionError,
    get_youtube_suggestions,
    search_youtube,
)
from app.youtube.repository import (
    VideoIndexState,
    get_video_index_state,
    request_video_indexing,
    save_search_results,
)
from app.youtube.keyword_jobs import (
    create_keyword_search_job,
    get_keyword_search_job_snapshot,
)

router = APIRouter()


class YouTubeVideoResponse(BaseModel):
    video_id: str
    title: str
    url: str
    channel_name: str | None
    channel_url: str | None
    thumbnail_url: str | None
    duration: str | None
    published_text: str | None
    view_count_text: str | None
    description: str | None


class YouTubeSearchResponse(BaseModel):
    query: str
    count: int
    items: list[YouTubeVideoResponse]


class YouTubeSuggestionsResponse(BaseModel):
    query: str
    count: int
    items: list[str]


class TranscriptIndexStatusResponse(BaseModel):
    language: str
    status: str
    object_name: str | None
    segment_count: int | None
    last_error: str | None
    index_status: str | None
    indexed_at: datetime | None


class VideoIndexStatusResponse(BaseModel):
    video_id: str
    title: str
    transcripts: list[TranscriptIndexStatusResponse]


class SubtitleMatchResponse(BaseModel):
    video_id: str
    title: str
    language: str
    start_ms: int
    end_ms: int
    seek_seconds: float
    text: str
    score: float
    matched_keywords: list[str] = Field(default_factory=list)
    highlighted_text: str | None = None


class SubtitleSearchResponse(BaseModel):
    query: str
    count: int
    items: list[SubtitleMatchResponse]


class KeywordSearchJobRequest(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    locale: str = Field(
        default="zh-TW", pattern=r"^[A-Za-z]{2,3}(?:-[A-Za-z]{2,4})?$"
    )
    matches_per_video: int = Field(default=5, ge=1, le=20)


class KeywordSearchVideoResponse(BaseModel):
    status: str
    metadata: YouTubeVideoResponse
    keyword_matches: list[SubtitleMatchResponse]
    transcripts: list[dict]
    error: str | None


class KeywordSearchJobResponse(BaseModel):
    task_id: str
    query: str
    status: str
    requested_count: int
    video_count: int
    completed_count: int
    matched_count: int
    videos: dict[str, KeywordSearchVideoResponse]
    error: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


DEFAULT_STREAM_VIDEO_LIMIT = 3
DEFAULT_STREAM_POLL_INTERVAL_SECONDS = 1.0


def _save_search(query: str, locale: str, requested_limit: int, results: list) -> None:
    with SessionLocal() as session:
        save_search_results(
            session,
            query=query,
            locale=locale,
            requested_limit=requested_limit,
            results=results,
        )


def _request_index(video_id: str) -> VideoIndexState | None:
    with SessionLocal() as session:
        return request_video_indexing(
            session, video_id, languages=get_default_subtitle_languages()
        )


def _get_index_state(video_id: str) -> VideoIndexState | None:
    with SessionLocal() as session:
        return get_video_index_state(session, video_id)


def _configured_stream_limit() -> int:
    value = get_system_config(
        "DEFAULT_YOUTUBE_VIDEO_RESULT_LIMIT", DEFAULT_STREAM_VIDEO_LIMIT
    )
    if isinstance(value, bool):
        return DEFAULT_STREAM_VIDEO_LIMIT
    try:
        return min(max(int(value), 1), 100)
    except (TypeError, ValueError):
        return DEFAULT_STREAM_VIDEO_LIMIT


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _create_keyword_job(
    *,
    query: str,
    locale: str,
    requested_count: int,
    matches_per_video: int,
    results: list,
) -> str:
    with SessionLocal() as session:
        return create_keyword_search_job(
            session,
            query=query,
            locale=locale,
            requested_count=requested_count,
            matches_per_video=matches_per_video,
            results=results,
        )


def _get_keyword_job(task_id: str) -> dict | None:
    with SessionLocal() as session:
        return get_keyword_search_job_snapshot(session, task_id)


def _index_response(state: VideoIndexState) -> VideoIndexStatusResponse:
    return VideoIndexStatusResponse(
        video_id=state.youtube_video_id,
        title=state.title,
        transcripts=[
            TranscriptIndexStatusResponse(**asdict(transcript))
            for transcript in state.transcripts
        ],
    )


@router.get("/youtube/keyword-suggestions", response_model=YouTubeSuggestionsResponse)
async def youtube_suggestions(
    q: Annotated[
        str,
        Query(min_length=1, max_length=200, description="YouTube partial search query"),
    ],
    limit: Annotated[int, Query(ge=1, le=20, description="Maximum suggestions")] = 10,
    locale: Annotated[
        str,
        Query(
            min_length=2,
            max_length=20,
            pattern=r"^[A-Za-z]{2,3}(?:-[A-Za-z]{2,4})?$",
            description="Browser locale, for example zh-TW or en-US",
        ),
    ] = "zh-TW",
    timeout_ms: Annotated[
        int,
        Query(ge=5_000, le=120_000, description="Browser timeout in milliseconds"),
    ] = 30_000,
) -> YouTubeSuggestionsResponse:
    """Return the suggestions displayed by YouTube's web search box."""
    normalized_query = q.strip()
    if not normalized_query:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="q must not be blank",
        )

    try:
        suggestions = await asyncio.to_thread(
            get_youtube_suggestions,
            normalized_query,
            limit,
            headless=True,
            timeout_ms=timeout_ms,
            locale=locale,
        )
    except YouTubeSuggestionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return YouTubeSuggestionsResponse(
        query=normalized_query,
        count=len(suggestions),
        items=suggestions,
    )


@router.get("/youtube/search-metadata", response_model=YouTubeSearchResponse)
async def youtube_search(
    q: Annotated[
        str,
        Query(min_length=1, max_length=200, description="透過關鍵字取得 YouTube Web 搜尋結果的 Metadata"),
    ],
    limit: Annotated[
        int,
        Query(ge=1, le=100, description="最多回傳的影片數量"),
    ] = 10,
    locale: Annotated[
        str,
        Query(
            min_length=2,
            max_length=20,
            pattern=r"^[A-Za-z]{2,3}(?:-[A-Za-z]{2,4})?$",
            description="瀏覽器語系，例如 zh-TW 或 en-US",
        ),
    ] = "zh-TW",
    timeout_ms: Annotated[
        int,
        Query(ge=5_000, le=120_000, description="頁面等待逾時毫秒數"),
    ] = 30_000,
) -> YouTubeSearchResponse:
    """Use anonymous headless Chromium to search YouTube."""
    normalized_query = q.strip()
    if not normalized_query:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="q must not be blank",
        )

    try:
        results = await asyncio.to_thread(
            search_youtube,
            normalized_query,
            limit,
            headless=True,
            timeout_ms=timeout_ms,
            locale=locale,
        )
    except YouTubeSearchError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    try:
        await asyncio.to_thread(_save_search, normalized_query, locale, limit, results)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="failed to save YouTube search results",
        ) from exc

    return YouTubeSearchResponse(
        query=normalized_query,
        count=len(results),
        items=[YouTubeVideoResponse(**result.as_dict()) for result in results],
    )


@router.post(
    "/youtube/search-jobs",
    response_model=KeywordSearchJobResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_keyword_search(
    payload: KeywordSearchJobRequest,
) -> KeywordSearchJobResponse:
    """Create a durable search job after all selected metadata is available."""
    query = payload.query.strip()
    if not query:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="query must not be blank",
        )
    try:
        video_count = await asyncio.to_thread(_configured_stream_limit)
        results = await asyncio.to_thread(
            search_youtube,
            query,
            video_count,
            headless=True,
            timeout_ms=30_000,
            locale=payload.locale,
        )
        await asyncio.to_thread(
            _save_search, query, payload.locale, video_count, results
        )
        for result in results:
            await asyncio.to_thread(_request_index, result.video_id)
        task_id = await asyncio.to_thread(
            _create_keyword_job,
            query=query,
            locale=payload.locale,
            requested_count=video_count,
            matches_per_video=payload.matches_per_video,
            results=results,
        )
        snapshot = await asyncio.to_thread(_get_keyword_job, task_id)
    except YouTubeSearchError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="failed to create keyword search job",
        ) from exc
    assert snapshot is not None
    return KeywordSearchJobResponse.model_validate(snapshot)


@router.get(
    "/youtube/search-jobs/{task_id}", response_model=KeywordSearchJobResponse
)
async def keyword_search_job(task_id: str) -> KeywordSearchJobResponse:
    """Return the latest durable snapshot for a keyword-search job."""
    try:
        snapshot = await asyncio.to_thread(_get_keyword_job, task_id)
    except (SQLAlchemyError, SubtitleStorageError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    if snapshot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="task not found")
    return KeywordSearchJobResponse.model_validate(snapshot)


@router.get("/youtube/search-jobs/{task_id}/events")
async def keyword_search_job_events(task_id: str):
    """Stream durable snapshots; reconnecting always starts with current state."""
    try:
        initial = await asyncio.to_thread(_get_keyword_job, task_id)
    except (SQLAlchemyError, SubtitleStorageError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    if initial is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="task not found")

    async def events():
        last_payload: str | None = None
        unchanged_polls = 0
        while True:
            try:
                snapshot = await asyncio.to_thread(_get_keyword_job, task_id)
            except (SQLAlchemyError, SubtitleStorageError) as exc:
                yield _sse("error", {"task_id": task_id, "detail": str(exc)})
                return
            if snapshot is None:
                yield _sse("error", {"task_id": task_id, "detail": "task not found"})
                return
            response = KeywordSearchJobResponse.model_validate(snapshot)
            payload = response.model_dump_json()
            if payload != last_payload:
                event = "snapshot" if last_payload is None else "update"
                yield f"event: {event}\ndata: {payload}\n\n"
                last_payload = payload
                unchanged_polls = 0
            else:
                unchanged_polls += 1
                if unchanged_polls >= 15:
                    yield ": keep-alive\n\n"
                    unchanged_polls = 0
            if response.status in {"completed", "failed"}:
                return
            await asyncio.sleep(DEFAULT_STREAM_POLL_INTERVAL_SECONDS)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post(
    "/youtube/videos/{video_id}/index",
    response_model=VideoIndexStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_video_index(video_id: str) -> VideoIndexStatusResponse:
    """Durably request subtitle retrieval and indexing for a discovered video."""
    try:
        state = await asyncio.to_thread(_request_index, video_id)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="failed to create video indexing request",
        ) from exc
    if state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="video must be discovered through YouTube search first",
        )
    return _index_response(state)


@router.get(
    "/youtube/videos/{video_id}/index",
    response_model=VideoIndexStatusResponse,
)
async def video_index_status(video_id: str) -> VideoIndexStatusResponse:
    """Return durable transcription and OpenSearch indexing progress."""
    try:
        state = await asyncio.to_thread(_get_index_state, video_id)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="failed to read video indexing status",
        ) from exc
    if state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="video not found"
        )
    return _index_response(state)


@router.get("/youtube/subtitles/search", response_model=SubtitleSearchResponse)
async def search_subtitles(
    q: Annotated[str, Query(min_length=1, max_length=200)],
    language: Annotated[str | None, Query(pattern=r"^(zh-TW|en)$")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
) -> SubtitleSearchResponse:
    """Search indexed subtitle segments and return their exact timestamp range."""
    from app.indexing import OpenSearchSubtitleIndexer, SubtitleIndexError

    normalized_query = q.strip()
    if not normalized_query:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="q must not be blank",
        )
    try:
        try:
            aliases = await get_aliases(normalized_query)
        except AliasServiceError:
            aliases = []
        indexer = OpenSearchSubtitleIndexer.from_settings()
        if language is not None:
            hits = await asyncio.to_thread(
                indexer.search,
                normalized_query,
                aliases=aliases,
                language=language,
                limit=limit,
            )
        else:
            hits = await asyncio.to_thread(
                indexer.search,
                normalized_query,
                aliases=aliases,
                languages=get_default_subtitle_languages(),
                limit=limit,
            )
    except SubtitleIndexError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    items = [
        SubtitleMatchResponse(
            video_id=hit.video_id,
            title=hit.title,
            language=hit.language,
            start_ms=hit.start_ms,
            end_ms=hit.end_ms,
            seek_seconds=hit.start_ms / 1000,
            text=hit.text,
            score=hit.score,
            matched_keywords=list(hit.matched_keywords),
            highlighted_text=hit.highlighted_text,
        )
        for hit in hits
    ]
    return SubtitleSearchResponse(query=normalized_query, count=len(items), items=items)
