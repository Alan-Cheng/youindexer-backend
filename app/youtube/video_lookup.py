"""Resolve a single YouTube video's metadata directly from its URL via yt-dlp.

Unlike ``search_youtube`` (Playwright, used for keyword discovery), this skips the
browser entirely: yt-dlp already knows how to fetch a single video's metadata, and
it is a pre-existing dependency used for subtitle retrieval (see
``app.transcription.youtube``).
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from app.youtube.search import YOUTUBE_ORIGIN, YouTubeSearchResult

_RAW_ID_PATTERN = re.compile(r"^[0-9A-Za-z_-]{11}$")
_URL_ID_PATTERN = re.compile(r"(?:v=|/shorts/|/embed/|youtu\.be/)([0-9A-Za-z_-]{11})")


class YouTubeVideoLookupError(RuntimeError):
    """Raised when a YouTube URL cannot be resolved to video metadata."""


def parse_youtube_video_id(value: str) -> str | None:
    """Extract an 11-character video ID from a URL, or a bare ID string."""
    value = value.strip()
    if _RAW_ID_PATTERN.match(value):
        return value
    match = _URL_ID_PATTERN.search(value)
    return match.group(1) if match else None


def _format_duration(seconds: Any) -> str | None:
    try:
        total = int(seconds)
    except (TypeError, ValueError):
        return None
    hrs, remainder = divmod(total, 3600)
    mins, secs = divmod(remainder, 60)
    return f"{hrs}:{mins:02d}:{secs:02d}" if hrs else f"{mins}:{secs:02d}"


def _format_published(upload_date: Any) -> str | None:
    if not upload_date:
        return None
    try:
        return datetime.strptime(str(upload_date), "%Y%m%d").strftime("%Y-%m-%d")
    except ValueError:
        return None


def fetch_youtube_video_metadata(video_id: str) -> YouTubeSearchResult:
    """Fetch one video's metadata without launching a browser."""
    url = f"{YOUTUBE_ORIGIN}/watch?v={video_id}"
    options: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "socket_timeout": 30,
        "retries": 2,
    }
    try:
        with YoutubeDL(options) as downloader:
            info = downloader.extract_info(url, download=False)
    except DownloadError as exc:
        raise YouTubeVideoLookupError(
            f"failed to fetch YouTube video metadata: {exc}"
        ) from exc

    resolved_id = str(info.get("id") or video_id)
    view_count = info.get("view_count")
    return YouTubeSearchResult(
        video_id=resolved_id,
        title=str(info.get("title") or resolved_id),
        url=str(info.get("webpage_url") or url),
        channel_name=info.get("channel") or info.get("uploader"),
        channel_url=info.get("channel_url") or info.get("uploader_url"),
        thumbnail_url=info.get("thumbnail")
        or f"https://i.ytimg.com/vi/{resolved_id}/hqdefault.jpg",
        duration=_format_duration(info.get("duration")),
        published_text=_format_published(info.get("upload_date")),
        view_count_text=f"{view_count:,} 次觀看" if isinstance(view_count, int) else None,
        description=info.get("description"),
    )
