"""YouTube search API routes."""

import asyncio
from dataclasses import asdict
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from app.database.session import SessionLocal
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


class SubtitleSearchResponse(BaseModel):
    query: str
    count: int
    items: list[SubtitleMatchResponse]


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
        return request_video_indexing(session, video_id)


def _get_index_state(video_id: str) -> VideoIndexState | None:
    with SessionLocal() as session:
        return get_video_index_state(session, video_id)


def _index_response(state: VideoIndexState) -> VideoIndexStatusResponse:
    return VideoIndexStatusResponse(
        video_id=state.youtube_video_id,
        title=state.title,
        transcripts=[
            TranscriptIndexStatusResponse(**asdict(transcript))
            for transcript in state.transcripts
        ],
    )


@router.get("/youtube/suggestions", response_model=YouTubeSuggestionsResponse)
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


@router.get("/youtube/search", response_model=YouTubeSearchResponse)
async def youtube_search(
    q: Annotated[
        str,
        Query(min_length=1, max_length=200, description="YouTube 搜尋關鍵字"),
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
        hits = await asyncio.to_thread(
            OpenSearchSubtitleIndexer.from_settings().search,
            normalized_query,
            language=language,
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
        )
        for hit in hits
    ]
    return SubtitleSearchResponse(query=normalized_query, count=len(items), items=items)
