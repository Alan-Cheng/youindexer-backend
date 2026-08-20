"""Authenticated user-scoped API routes."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse

from app.auth.dependencies import get_current_user
from app.database.models import KeywordSearchJob, User
from app.database.session import SessionLocal, get_session
from app.youtube.keyword_jobs import delete_user_search_job, get_user_search_history

router = APIRouter()


class SearchHistoryItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: str
    query: str
    locale: str
    status: str
    requested_count: int
    video_count: int
    completed_count: int
    matched_count: int
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class SearchHistoryListResponse(BaseModel):
    items: list[SearchHistoryItemResponse]
    total: int
    limit: int
    offset: int


def _history_response(
    session: Session,
    *,
    user_id: int,
    limit: int,
    offset: int,
) -> SearchHistoryListResponse:
    jobs, total = get_user_search_history(
        session,
        user_id=user_id,
        limit=limit,
        offset=offset,
    )
    items: list[SearchHistoryItemResponse] = []
    for job in jobs:
        completed_count = sum(item.status != "loading" for item in job.videos)
        matched_count = sum(item.status == "matched" for item in job.videos)
        items.append(
            SearchHistoryItemResponse(
                task_id=job.id,
                query=job.query,
                locale=job.locale,
                status=job.status,
                requested_count=job.requested_count,
                video_count=len(job.videos),
                completed_count=completed_count,
                matched_count=matched_count,
                created_at=job.created_at,
                updated_at=job.updated_at,
                completed_at=job.completed_at,
            )
        )
    return SearchHistoryListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


def _load_history_response(
    *,
    user_id: int,
    limit: int,
    offset: int,
) -> SearchHistoryListResponse:
    with SessionLocal() as session:
        return _history_response(
            session,
            user_id=user_id,
            limit=limit,
            offset=offset,
        )


@router.get("/me/search-history", response_model=SearchHistoryListResponse)
async def list_search_history(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SearchHistoryListResponse:
    """Return the current user's keyword-search job history, newest first."""
    return _history_response(
        session,
        user_id=current_user.id,
        limit=limit,
        offset=offset,
    )


@router.delete("/me/search-history/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_search_history_item(
    task_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> None:
    """Delete one search job belonging to the current user."""
    if not delete_user_search_job(
        session, user_id=current_user.id, task_id=task_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="search history item not found",
        )


@router.get("/me/search-history/events")
async def search_history_events(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """Stream the current user's search history snapshots."""

    async def events():
        last_payload: str | None = None
        unchanged_polls = 0
        while True:
            snapshot = await asyncio.to_thread(
                _load_history_response,
                user_id=current_user.id,
                limit=limit,
                offset=offset,
            )
            payload = snapshot.model_dump_json()
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
            await asyncio.sleep(1)
            if await request.is_disconnected():
                return

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
        status_code=status.HTTP_200_OK,
    )
