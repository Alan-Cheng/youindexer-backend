"""Threads public-post crawl trigger API."""

from __future__ import annotations

import asyncio
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.config import settings
from app.core.response import APIResponse
from app.threads import (
    ThreadsCrawlError,
    fetch_threads_profile_posts,
    search_threads_posts,
)

router = APIRouter()


class ThreadsKeywordCrawlRequest(BaseModel):
    mode: Literal["keyword"] = "keyword"
    keyword: str = Field(min_length=1, max_length=100, description="搜尋關鍵字")
    limit: int = Field(default=10, ge=1, le=50, description="最多回傳的貼文數量")


class ThreadsProfileCrawlRequest(BaseModel):
    mode: Literal["profile"] = "profile"
    username: str = Field(min_length=1, max_length=30, description="Threads 公開帳號名稱")
    limit: int = Field(default=10, ge=1, le=50, description="最多回傳的貼文數量")


ThreadsCrawlRequest = Annotated[
    ThreadsKeywordCrawlRequest | ThreadsProfileCrawlRequest,
    Field(discriminator="mode"),
]


class ThreadsPostResponse(BaseModel):
    post_id: str
    url: str
    username: str
    caption: str | None
    thumbnail_url: str | None
    published_at: str | None
    like_count: int | None


class ThreadsCrawlResult(BaseModel):
    mode: Literal["keyword", "profile"]
    query: str
    count: int
    items: list[ThreadsPostResponse]


@router.post("/threads/crawl", response_model=APIResponse[ThreadsCrawlResult])
async def crawl_threads(payload: ThreadsCrawlRequest) -> APIResponse[ThreadsCrawlResult]:
    """Trigger a single, synchronous Threads public-post crawl."""
    try:
        if payload.mode == "keyword":
            posts = await asyncio.to_thread(
                search_threads_posts,
                payload.keyword,
                payload.limit,
                storage_state_path=settings.threads_storage_state_path,
            )
            query = payload.keyword
        else:
            posts = await asyncio.to_thread(
                fetch_threads_profile_posts,
                payload.username,
                payload.limit,
                storage_state_path=settings.threads_storage_state_path,
            )
            query = payload.username
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    except ThreadsCrawlError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc

    result = ThreadsCrawlResult(
        mode=payload.mode,
        query=query,
        count=len(posts),
        items=[ThreadsPostResponse(**post.as_dict()) for post in posts],
    )
    return APIResponse.ok(result)
