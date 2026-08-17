"""YouTube search API routes."""

import asyncio
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.youtube import (
    YouTubeSearchError,
    YouTubeSuggestionError,
    get_youtube_suggestions,
    search_youtube,
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

    return YouTubeSearchResponse(
        query=normalized_query,
        count=len(results),
        items=[YouTubeVideoResponse(**result.as_dict()) for result in results],
    )
