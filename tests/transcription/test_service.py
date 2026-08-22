from app.transcription.service import process_youtube_subtitles
from app.transcription.youtube import (
    SubtitleDocument,
    SubtitleFetchResult,
    SubtitleSegment,
)


class _FakeFetcher:
    def __init__(self, result: SubtitleFetchResult) -> None:
        self.result = result
        self.requested_languages: tuple[str, ...] | None = None

    def fetch(
        self, _video_url: str, _languages: tuple[str, ...]
    ) -> SubtitleFetchResult:
        self.requested_languages = _languages
        return self.result


class _FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, dict] = {}

    def put_json(self, object_name: str, document: dict) -> None:
        self.objects[object_name] = document


def test_process_youtube_subtitles_stores_language_documents() -> None:
    document = SubtitleDocument(
        version=1,
        video_id="video123",
        video_url="https://www.youtube.com/watch?v=video123",
        title="Example",
        language="zh-TW",
        source_language="zh-Hant",
        source="youtube_manual",
        fetched_at="2026-08-17T00:00:00+00:00",
        segments=(SubtitleSegment(start_ms=0, end_ms=1000, text="字幕"),),
    )
    fetch_result = SubtitleFetchResult(
        video_id="video123",
        video_url=document.video_url,
        title=document.title,
        documents=(document,),
        unavailable_languages=("en",),
    )
    storage = _FakeStorage()

    result = process_youtube_subtitles(
        document.video_url,
        fetcher=_FakeFetcher(fetch_result),
        storage=storage,
    )

    assert result.status == "partial"
    assert result.stored_subtitles[0].object_name == "transcripts/video123/zh-TW.json"
    assert storage.objects["transcripts/video123/zh-TW.json"]["segment_count"] == 1


def test_process_youtube_subtitles_does_not_write_when_unavailable() -> None:
    fetch_result = SubtitleFetchResult(
        video_id="video123",
        video_url="https://www.youtube.com/watch?v=video123",
        title="Example",
        documents=(),
        unavailable_languages=("zh-TW", "en"),
    )
    storage = _FakeStorage()

    result = process_youtube_subtitles(
        fetch_result.video_url,
        fetcher=_FakeFetcher(fetch_result),
        storage=storage,
    )

    assert result.status == "subtitle_unavailable"
    assert storage.objects == {}


def test_process_youtube_subtitles_requests_only_selected_language() -> None:
    fetch_result = SubtitleFetchResult(
        video_id="video123",
        video_url="https://www.youtube.com/watch?v=video123",
        title="Example",
        documents=(),
        unavailable_languages=("en",),
    )
    fetcher = _FakeFetcher(fetch_result)

    process_youtube_subtitles(
        fetch_result.video_url,
        languages=("en",),
        fetcher=fetcher,
        storage=_FakeStorage(),
    )

    assert fetcher.requested_languages == ("en",)
