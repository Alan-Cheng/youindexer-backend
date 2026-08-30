"""YouTube branch of the multi-source URL ingestion pipeline.

Resolves a video URL to metadata (via yt-dlp, see ``app.youtube.video_lookup``),
persists it, and requests the same transcription+OpenSearch indexing pipeline the
keyword-search flow already uses (``app.youtube.repository.request_video_indexing``).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.youtube.repository import VideoIndexState, request_video_indexing, save_search_results
from app.youtube.video_lookup import fetch_youtube_video_metadata, parse_youtube_video_id


class UnrecognizedYouTubeUrlError(ValueError):
    """Raised when a YouTube-hosted URL doesn't contain a recognizable video ID."""


def ingest_youtube_video(session: Session, url: str) -> VideoIndexState:
    """Resolve, persist, and request transcription+indexing for one YouTube video."""
    video_id = parse_youtube_video_id(url)
    if video_id is None:
        raise UnrecognizedYouTubeUrlError(f"could not find a video ID in url: {url!r}")

    result = fetch_youtube_video_metadata(video_id)
    save_search_results(session, query=url, locale="zh-TW", requested_limit=1, results=[result])
    state = request_video_indexing(session, result.video_id)
    assert state is not None, "just persisted above, so it must be discoverable"
    return state
