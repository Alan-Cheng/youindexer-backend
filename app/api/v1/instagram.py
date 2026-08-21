"""Instagram public-post crawl trigger API."""

from __future__ import annotations

import asyncio
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.config import settings
from app.core.response import APIResponse
from app.instagram import (
    InstagramCrawlError,
    fetch_instagram_profile_posts,
    search_instagram_posts,
)

router = APIRouter()


class InstagramKeywordCrawlRequest(BaseModel):
    mode: Literal["keyword"] = "keyword"
    keyword: str = Field(min_length=1, max_length=100, description="搜尋關鍵字/hashtag")
    limit: int = Field(default=10, ge=1, le=50, description="最多回傳的貼文數量")


class InstagramProfileCrawlRequest(BaseModel):
    mode: Literal["profile"] = "profile"
    username: str = Field(min_length=1, max_length=30, description="Instagram 公開帳號名稱")
    limit: int = Field(default=10, ge=1, le=50, description="最多回傳的貼文數量")


InstagramCrawlRequest = Annotated[
    InstagramKeywordCrawlRequest | InstagramProfileCrawlRequest,
    Field(discriminator="mode"),
]


class InstagramPostResponse(BaseModel):
    post_id: str
    url: str
    username: str
    caption: str | None
    accessibility_caption: str | None
    thumbnail_url: str | None
    is_video: bool


class InstagramCrawlResult(BaseModel):
    mode: Literal["keyword", "profile"]
    query: str
    count: int
    items: list[InstagramPostResponse]


@router.post("/instagram/crawl", response_model=APIResponse[InstagramCrawlResult])
async def crawl_instagram(
    payload: InstagramCrawlRequest,
) -> APIResponse[InstagramCrawlResult]:
    """Trigger a single, synchronous Instagram public-post crawl."""
    try:
        if payload.mode == "keyword":
            posts = await asyncio.to_thread(
                search_instagram_posts,
                payload.keyword,
                payload.limit,
                storage_state_path=settings.instagram_storage_state_path,
            )
            query = payload.keyword
        else:
            posts = await asyncio.to_thread(
                fetch_instagram_profile_posts,
                payload.username,
                payload.limit,
                storage_state_path=settings.instagram_storage_state_path,
            )
            query = payload.username
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    except InstagramCrawlError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc

    result = InstagramCrawlResult(
        mode=payload.mode,
        query=query,
        count=len(posts),
        items=[InstagramPostResponse(**post.as_dict()) for post in posts],
    )
    return APIResponse.ok(result)
