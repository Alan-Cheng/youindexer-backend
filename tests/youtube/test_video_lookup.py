import pytest

from app.youtube.video_lookup import (
    YouTubeVideoLookupError,
    _format_duration,
    _format_published,
    fetch_youtube_video_metadata,
    parse_youtube_video_id,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://www.youtube.com/watch?v=abc123XYZ90", "abc123XYZ90"),
        ("https://youtu.be/abc123XYZ90", "abc123XYZ90"),
        ("https://youtu.be/abc123XYZ90?si=tracking", "abc123XYZ90"),
        ("https://www.youtube.com/shorts/abc123XYZ90", "abc123XYZ90"),
        ("https://m.youtube.com/watch?v=abc123XYZ90&t=30s", "abc123XYZ90"),
        ("abc123XYZ90", "abc123XYZ90"),
        ("https://www.youtube.com/results?search_query=test", None),
        ("not a url", None),
    ],
)
def test_parse_youtube_video_id(value: str, expected: str | None) -> None:
    assert parse_youtube_video_id(value) == expected


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(45, "0:45"), (125, "2:05"), (3725, "1:02:05"), (None, None), ("bad", None)],
)
def test_format_duration(seconds, expected: str | None) -> None:
    assert _format_duration(seconds) == expected


@pytest.mark.parametrize(
    ("upload_date", "expected"),
    [("20260115", "2026-01-15"), (None, None), ("not-a-date", None)],
)
def test_format_published(upload_date, expected: str | None) -> None:
    assert _format_published(upload_date) == expected


class _FakeYoutubeDL:
    def __init__(self, info: dict) -> None:
        self._info = info

    def __enter__(self) -> "_FakeYoutubeDL":
        return self

    def __exit__(self, *exc_info) -> None:
        return None

    def extract_info(self, url: str, download: bool = False) -> dict:
        return self._info


def test_fetch_youtube_video_metadata_maps_info_fields(monkeypatch) -> None:
    info = {
        "id": "abc123XYZ90",
        "title": "測試影片標題",
        "webpage_url": "https://www.youtube.com/watch?v=abc123XYZ90",
        "channel": "測試頻道",
        "channel_url": "https://www.youtube.com/@test",
        "thumbnail": "https://i.ytimg.com/vi/abc123XYZ90/hqdefault.jpg",
        "duration": 754,
        "upload_date": "20260115",
        "view_count": 12345,
        "description": "測試說明",
    }
    monkeypatch.setattr(
        "app.youtube.video_lookup.YoutubeDL", lambda options: _FakeYoutubeDL(info)
    )

    result = fetch_youtube_video_metadata("abc123XYZ90")

    assert result.video_id == "abc123XYZ90"
    assert result.title == "測試影片標題"
    assert result.channel_name == "測試頻道"
    assert result.duration == "12:34"
    assert result.published_text == "2026-01-15"
    assert result.view_count_text == "12,345 次觀看"


def test_fetch_youtube_video_metadata_wraps_download_error(monkeypatch) -> None:
    from yt_dlp.utils import DownloadError

    class _RaisingYoutubeDL(_FakeYoutubeDL):
        def extract_info(self, url: str, download: bool = False) -> dict:
            raise DownloadError("video unavailable")

    monkeypatch.setattr(
        "app.youtube.video_lookup.YoutubeDL", lambda options: _RaisingYoutubeDL({})
    )

    with pytest.raises(YouTubeVideoLookupError, match="failed to fetch"):
        fetch_youtube_video_metadata("abc123XYZ90")
