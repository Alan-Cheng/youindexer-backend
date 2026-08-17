"""Retrieve and normalize selected YouTube subtitle tracks."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from yt_dlp import YoutubeDL
from yt_dlp.networking.exceptions import RequestError
from yt_dlp.utils import DownloadError

SUPPORTED_LANGUAGES = ("zh-TW", "en")
_LANGUAGE_ALIASES = {
    "zh-TW": ("zh-TW", "zh-Hant"),
    "en": ("en", "en-US", "en-GB"),
}


class YouTubeSubtitleError(RuntimeError):
    """Raised when YouTube metadata or subtitle content cannot be retrieved."""


@dataclass(frozen=True, slots=True)
class SubtitleTrack:
    language: str
    source_language: str
    source: str
    url: str


@dataclass(frozen=True, slots=True)
class SubtitleSegment:
    start_ms: int
    end_ms: int
    text: str


@dataclass(frozen=True, slots=True)
class SubtitleDocument:
    version: int
    video_id: str
    video_url: str
    title: str | None
    language: str
    source_language: str
    source: str
    fetched_at: str
    segments: tuple[SubtitleSegment, ...]

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["segment_count"] = len(self.segments)
        return data


@dataclass(frozen=True, slots=True)
class SubtitleFetchResult:
    video_id: str
    video_url: str
    title: str | None
    documents: tuple[SubtitleDocument, ...]
    unavailable_languages: tuple[str, ...]


def _json3_format_url(formats: list[dict[str, Any]]) -> str | None:
    for subtitle_format in formats:
        if subtitle_format.get("ext") == "json3" and subtitle_format.get("url"):
            return str(subtitle_format["url"])
    return None


def _matching_key(tracks: dict[str, Any], language: str) -> str | None:
    aliases = _LANGUAGE_ALIASES[language]
    for alias in aliases:
        if alias in tracks:
            return alias
    for alias in aliases:
        translated = sorted(key for key in tracks if key.startswith(f"{alias}-"))
        if translated:
            return translated[0]
    return None


def _translated_url(url: str, language: str) -> str:
    target = "zh-Hant" if language == "zh-TW" else "en"
    parts = urlsplit(url)
    query = [(key, value) for key, value in parse_qsl(parts.query) if key != "tlang"]
    query.append(("tlang", target))
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
    )


def _translation_source(
    subtitles: dict[str, list[dict[str, Any]]],
    automatic_captions: dict[str, list[dict[str, Any]]],
) -> tuple[str, str] | None:
    for tracks in (subtitles, automatic_captions):
        for source_language, formats in tracks.items():
            if source_language == "live_chat":
                continue
            if url := _json3_format_url(formats):
                return source_language, url
    return None


def select_subtitle_track(
    subtitles: dict[str, list[dict[str, Any]]],
    automatic_captions: dict[str, list[dict[str, Any]]],
    language: str,
) -> SubtitleTrack | None:
    """Select a JSON3 track, preferring creator-provided subtitles."""
    if language not in _LANGUAGE_ALIASES:
        raise ValueError(f"unsupported subtitle language: {language}")

    manual_key = _matching_key(subtitles, language)
    if manual_key:
        url = _json3_format_url(subtitles[manual_key])
        if url:
            return SubtitleTrack(language, manual_key, "youtube_manual", url)

    automatic_key = _matching_key(automatic_captions, language)
    if automatic_key:
        url = _json3_format_url(automatic_captions[automatic_key])
        if url:
            aliases = _LANGUAGE_ALIASES[language]
            source = (
                "youtube_auto"
                if automatic_key in aliases
                else "youtube_auto_translated"
            )
            return SubtitleTrack(language, automatic_key, source, url)

    translation_source = _translation_source(subtitles, automatic_captions)
    if not translation_source:
        return None
    source_language, source_url = translation_source
    return SubtitleTrack(
        language,
        f"{language}-{source_language}",
        "youtube_auto_translated",
        _translated_url(source_url, language),
    )


def parse_json3_segments(
    payload: bytes | str | dict[str, Any],
) -> tuple[SubtitleSegment, ...]:
    """Convert YouTube JSON3 events into stable millisecond subtitle segments."""
    if isinstance(payload, bytes):
        data = json.loads(payload.decode("utf-8"))
    elif isinstance(payload, str):
        data = json.loads(payload)
    else:
        data = payload

    segments: list[SubtitleSegment] = []
    for event in data.get("events", []):
        event_segments = event.get("segs") or []
        text = "".join(str(segment.get("utf8", "")) for segment in event_segments)
        text = " ".join(text.replace("\n", " ").split())
        if not text:
            continue
        start_ms = max(0, int(event.get("tStartMs", 0)))
        duration_ms = max(0, int(event.get("dDurationMs", 0)))
        segments.append(
            SubtitleSegment(
                start_ms=start_ms,
                end_ms=start_ms + duration_ms,
                text=text,
            )
        )
    return tuple(segments)


class YouTubeSubtitleFetcher:
    def __init__(
        self,
        *,
        cookies_file: str | None = None,
        youtube_dl_factory: Callable[[dict[str, Any]], YoutubeDL] = YoutubeDL,
    ) -> None:
        self.cookies_file = cookies_file
        self.youtube_dl_factory = youtube_dl_factory

    def fetch(
        self,
        video_url: str,
        languages: tuple[str, ...] = SUPPORTED_LANGUAGES,
    ) -> SubtitleFetchResult:
        unsupported = set(languages) - set(SUPPORTED_LANGUAGES)
        if unsupported:
            raise ValueError(f"unsupported subtitle languages: {sorted(unsupported)}")

        options: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "writeautomaticsub": True,
            "noplaylist": True,
            "socket_timeout": 30,
            "retries": 2,
        }
        if self.cookies_file:
            options["cookiefile"] = self.cookies_file

        try:
            with self.youtube_dl_factory(options) as downloader:
                info = downloader.extract_info(video_url, download=False)
                video_id = str(info["id"])
                canonical_url = str(
                    info.get("webpage_url")
                    or f"https://www.youtube.com/watch?v={video_id}"
                )
                title = str(info["title"]) if info.get("title") else None
                manual = info.get("subtitles") or {}
                automatic = info.get("automatic_captions") or {}

                documents: list[SubtitleDocument] = []
                unavailable: list[str] = []
                fetched_at = datetime.now(UTC).isoformat()
                for language in languages:
                    track = select_subtitle_track(manual, automatic, language)
                    if not track:
                        unavailable.append(language)
                        continue
                    with downloader.urlopen(track.url) as response:
                        segments = parse_json3_segments(response.read())
                    if not segments:
                        unavailable.append(language)
                        continue
                    documents.append(
                        SubtitleDocument(
                            version=1,
                            video_id=video_id,
                            video_url=canonical_url,
                            title=title,
                            language=track.language,
                            source_language=track.source_language,
                            source=track.source,
                            fetched_at=fetched_at,
                            segments=segments,
                        )
                    )
        except (
            DownloadError,
            RequestError,
            OSError,
            KeyError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            raise YouTubeSubtitleError(
                f"failed to retrieve YouTube subtitles: {exc}"
            ) from exc

        return SubtitleFetchResult(
            video_id=video_id,
            video_url=canonical_url,
            title=title,
            documents=tuple(documents),
            unavailable_languages=tuple(unavailable),
        )
