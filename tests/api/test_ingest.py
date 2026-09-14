import asyncio

import pytest
from fastapi import HTTPException

from app.api.v1.ingest import IngestByUrlRequest, ingest_by_url
from app.ingest.youtube import UnrecognizedYouTubeUrlError, YouTubeIngestResult
from app.youtube import YouTubeVideoLookupError
from app.youtube.repository import TranscriptState, VideoIndexState
from app.youtube.search import YouTubeSearchResult


@pytest.fixture(autouse=True)
def _run_thread_calls_inline(monkeypatch):
    """Avoid Python 3.14 ASGITransport/thread shutdown deadlocks in API tests."""

    async def immediate_to_thread(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr("app.api.v1.ingest.asyncio.to_thread", immediate_to_thread)


def sample_metadata() -> YouTubeSearchResult:
    return YouTubeSearchResult(
        video_id="abc123XYZ90",
        title="測試影片標題",
        url="https://www.youtube.com/watch?v=abc123XYZ90",
        channel_name="測試頻道",
        channel_url="https://www.youtube.com/@test",
        thumbnail_url="https://i.ytimg.com/vi/abc123XYZ90/hqdefault.jpg",
        duration="12:34",
        published_text="2026-01-15",
        view_count_text="12,345 次觀看",
        description="測試說明",
    )


def sample_state() -> VideoIndexState:
    return VideoIndexState(
        youtube_video_id="abc123XYZ90",
        title="測試影片標題",
        transcripts=(
            TranscriptState(
                language="zh-TW",
                status="pending",
                object_name=None,
                segment_count=None,
                last_error=None,
                index_status=None,
                indexed_at=None,
            ),
        ),
    )


def sample_ingest_result() -> YouTubeIngestResult:
    return YouTubeIngestResult(metadata=sample_metadata(), index_state=sample_state())


def test_ingest_by_url_dispatches_youtube(monkeypatch) -> None:
    ingested = sample_ingest_result()
    monkeypatch.setattr("app.api.v1.ingest._ingest_youtube", lambda url: ingested)

    response = asyncio.run(
        ingest_by_url(IngestByUrlRequest(url="https://www.youtube.com/watch?v=abc123XYZ90"))
    )

    assert response.data.source == "youtube"
    assert response.data.video_id == "abc123XYZ90"
    assert response.data.title == "測試影片標題"
    assert response.data.channel_name == "測試頻道"
    assert response.data.thumbnail_url == "https://i.ytimg.com/vi/abc123XYZ90/hqdefault.jpg"
    assert response.data.published_text == "2026-01-15"
    assert response.data.view_count_text == "12,345 次觀看"
    assert response.data.transcripts[0].language == "zh-TW"


@pytest.mark.parametrize(
    "url",
    [
        "https://www.instagram.com/p/Cxyz123/",
        "https://www.threads.net/@user/post/Cxyz123",
    ],
)
def test_ingest_by_url_rejects_unimplemented_sources(url: str) -> None:
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(ingest_by_url(IngestByUrlRequest(url=url)))

    assert exc_info.value.status_code == 501


def test_ingest_by_url_rejects_unknown_host() -> None:
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(ingest_by_url(IngestByUrlRequest(url="https://example.com/watch?v=abc123")))

    assert exc_info.value.status_code == 422


def test_ingest_by_url_maps_unrecognized_youtube_url_to_422(monkeypatch) -> None:
    def fake_ingest(url: str):
        raise UnrecognizedYouTubeUrlError("no video id")

    monkeypatch.setattr("app.api.v1.ingest._ingest_youtube", fake_ingest)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            ingest_by_url(
                IngestByUrlRequest(url="https://www.youtube.com/results?search_query=test")
            )
        )

    assert exc_info.value.status_code == 422


def test_ingest_by_url_maps_lookup_failure_to_bad_gateway(monkeypatch) -> None:
    def fake_ingest(url: str):
        raise YouTubeVideoLookupError("video unavailable")

    monkeypatch.setattr("app.api.v1.ingest._ingest_youtube", fake_ingest)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            ingest_by_url(IngestByUrlRequest(url="https://www.youtube.com/watch?v=abc123XYZ90"))
        )

    assert exc_info.value.status_code == 502
