from io import BytesIO

from app.transcription.youtube import (
    YouTubeSubtitleFetcher,
    parse_json3_segments,
    select_subtitle_track,
)


def _formats(url: str) -> list[dict[str, str]]:
    return [
        {"ext": "vtt", "url": f"{url}.vtt"},
        {"ext": "json3", "url": f"{url}.json3"},
    ]


def test_select_subtitle_track_prefers_manual_traditional_chinese() -> None:
    track = select_subtitle_track(
        {"zh-Hant": _formats("https://example.test/manual")},
        {"zh-TW": _formats("https://example.test/auto")},
        "zh-TW",
    )

    assert track is not None
    assert track.source_language == "zh-Hant"
    assert track.source == "youtube_manual"
    assert track.url == "https://example.test/manual.json3"


def test_select_subtitle_track_accepts_translated_english_track() -> None:
    track = select_subtitle_track(
        {},
        {"en-zh-Hant": _formats("https://example.test/translated")},
        "en",
    )

    assert track is not None
    assert track.source_language == "en-zh-Hant"
    assert track.source == "youtube_auto_translated"


def test_select_subtitle_track_builds_translation_from_manual_track() -> None:
    track = select_subtitle_track(
        {"zh-Hant": _formats("https://example.test/caption?fmt=json3")},
        {},
        "en",
    )

    assert track is not None
    assert track.source_language == "en-zh-Hant"
    assert track.source == "youtube_auto_translated"
    assert "tlang=en" in track.url


def test_parse_json3_segments_normalizes_text_and_timing() -> None:
    segments = parse_json3_segments(
        {
            "events": [
                {
                    "tStartMs": 1200,
                    "dDurationMs": 3300,
                    "segs": [{"utf8": "Hello\n"}, {"utf8": " world"}],
                },
                {"tStartMs": 4500, "dDurationMs": 500, "segs": []},
            ]
        }
    )

    assert len(segments) == 1
    assert segments[0].start_ms == 1200
    assert segments[0].end_ms == 4500
    assert segments[0].text == "Hello world"


class _FakeDownloader:
    def __init__(self, options: dict, info: dict, payloads: dict[str, bytes]) -> None:
        self.options = options
        self.info = info
        self.payloads = payloads

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def extract_info(self, _url: str, *, download: bool) -> dict:
        assert download is False
        return self.info

    def urlopen(self, url: str) -> BytesIO:
        return BytesIO(self.payloads[url])


def test_fetcher_returns_documents_and_unavailable_languages() -> None:
    subtitle_url = "https://example.test/zh.json3"
    info = {
        "id": "video123",
        "title": "Example",
        "webpage_url": "https://www.youtube.com/watch?v=video123",
        "subtitles": {"zh-Hant": [{"ext": "json3", "url": subtitle_url}]},
        "automatic_captions": {},
    }
    payload = b'{"events":[{"tStartMs":10,"dDurationMs":20,"segs":[{"utf8":"text"}]}]}'

    def factory(options: dict) -> _FakeDownloader:
        return _FakeDownloader(
            options,
            info,
            {
                subtitle_url: payload,
                f"{subtitle_url}?tlang=en": payload,
            },
        )

    result = YouTubeSubtitleFetcher(youtube_dl_factory=factory).fetch(
        "https://www.youtube.com/watch?v=video123"
    )

    assert result.video_id == "video123"
    assert [document.language for document in result.documents] == ["zh-TW", "en"]
    assert result.unavailable_languages == ()
    assert result.documents[0].segments[0].text == "text"


def test_fetcher_treats_no_tracks_as_successful_unavailable_result() -> None:
    info = {
        "id": "video123",
        "title": "Example",
        "webpage_url": "https://www.youtube.com/watch?v=video123",
        "subtitles": {},
        "automatic_captions": {},
    }

    def factory(options: dict) -> _FakeDownloader:
        return _FakeDownloader(options, info, {})

    result = YouTubeSubtitleFetcher(youtube_dl_factory=factory).fetch(
        "https://www.youtube.com/watch?v=video123"
    )

    assert result.documents == ()
    assert result.unavailable_languages == ("zh-TW", "en")
