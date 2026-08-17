"""Application service for fetching and storing complete subtitle documents."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Protocol

from app.config import Settings, settings
from app.transcription.storage import MinioSubtitleStorage
from app.transcription.youtube import (
    SUPPORTED_LANGUAGES,
    SubtitleFetchResult,
    YouTubeSubtitleFetcher,
)


class SubtitleStorage(Protocol):
    def put_json(self, object_name: str, document: dict[str, Any]) -> None: ...


@dataclass(frozen=True, slots=True)
class StoredSubtitle:
    language: str
    source: str
    object_name: str
    segment_count: int


@dataclass(frozen=True, slots=True)
class SubtitleWorkerResult:
    status: str
    video_id: str
    video_url: str
    title: str | None
    stored_subtitles: tuple[StoredSubtitle, ...]
    unavailable_languages: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _status(fetch_result: SubtitleFetchResult) -> str:
    if not fetch_result.documents:
        return "subtitle_unavailable"
    if fetch_result.unavailable_languages:
        return "partial"
    return "stored"


def process_youtube_subtitles(
    video_url: str,
    *,
    fetcher: YouTubeSubtitleFetcher | None = None,
    storage: SubtitleStorage | None = None,
    config: Settings = settings,
) -> SubtitleWorkerResult:
    fetcher = fetcher or YouTubeSubtitleFetcher(
        cookies_file=config.youtube_cookies_file
    )
    storage = storage or MinioSubtitleStorage.from_settings(config)
    fetch_result = fetcher.fetch(video_url, SUPPORTED_LANGUAGES)

    stored: list[StoredSubtitle] = []
    for document in fetch_result.documents:
        object_name = f"transcripts/{document.video_id}/{document.language}.json"
        storage.put_json(object_name, document.as_dict())
        stored.append(
            StoredSubtitle(
                language=document.language,
                source=document.source,
                object_name=object_name,
                segment_count=len(document.segments),
            )
        )

    return SubtitleWorkerResult(
        status=_status(fetch_result),
        video_id=fetch_result.video_id,
        video_url=fetch_result.video_url,
        title=fetch_result.title,
        stored_subtitles=tuple(stored),
        unavailable_languages=fetch_result.unavailable_languages,
    )
