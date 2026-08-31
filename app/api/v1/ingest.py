"""Multi-source URL ingestion API."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core.response import APIResponse
from app.database.session import SessionLocal
from app.ingest.dispatch import UnknownUrlSourceError, detect_url_source
from app.ingest.youtube import UnrecognizedYouTubeUrlError, ingest_youtube_video
from app.youtube import YouTubeVideoLookupError
from app.youtube.repository import VideoIndexState

router = APIRouter()
logger = logging.getLogger(__name__)

_UNSUPPORTED_SOURCE_DETAIL = {
    "instagram": "instagram 來源尚未支援，待 YOUINDEXER-22（IG/Threads 可搜尋、可索引）完成後再接上",
    "threads": "threads 來源尚未支援，待 YOUINDEXER-22（IG/Threads 可搜尋、可索引）完成後再接上",
}


class IngestByUrlRequest(BaseModel):
    url: str = Field(min_length=1, max_length=500, description="要擷取的內容網址")


class TranscriptIndexStatusResponse(BaseModel):
    language: str
    status: str
    object_name: str | None
    segment_count: int | None
    last_error: str | None
    index_status: str | None
    indexed_at: datetime | None


class IngestByUrlResponse(BaseModel):
    source: str
    video_id: str
    title: str
    transcripts: list[TranscriptIndexStatusResponse]


def _ingest_youtube(url: str) -> VideoIndexState:
    with SessionLocal() as session:
        return ingest_youtube_video(session, url)


@router.post(
    "/ingest/by-url",
    response_model=APIResponse[IngestByUrlResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_by_url(payload: IngestByUrlRequest) -> APIResponse[IngestByUrlResponse]:
    """Detect a URL's source platform, then extract and index its content."""
    url = payload.url.strip()
    if not url:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="url must not be blank"
        )

    try:
        source = detect_url_source(url)
    except UnknownUrlSourceError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    if source != "youtube":
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=_UNSUPPORTED_SOURCE_DETAIL[source],
        )

    logger.info("ingesting url source=%s url=%r", source, url)
    try:
        state = await asyncio.to_thread(_ingest_youtube, url)
    except UnrecognizedYouTubeUrlError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    except YouTubeVideoLookupError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return APIResponse.ok(
        IngestByUrlResponse(
            source=source,
            video_id=state.youtube_video_id,
            title=state.title,
            transcripts=[
                TranscriptIndexStatusResponse(**asdict(transcript))
                for transcript in state.transcripts
            ],
        )
    )
