from app.ingest.youtube import UnrecognizedYouTubeUrlError, ingest_youtube_video
from app.youtube.repository import TranscriptState, VideoIndexState
from app.youtube.search import YouTubeSearchResult

import pytest


def sample_result() -> YouTubeSearchResult:
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


def test_ingest_youtube_video_persists_and_requests_indexing(monkeypatch) -> None:
    result = sample_result()
    state = sample_state()
    save_calls: dict[str, object] = {}
    index_calls: dict[str, object] = {}

    monkeypatch.setattr(
        "app.ingest.youtube.fetch_youtube_video_metadata", lambda video_id: result
    )

    def fake_save(session, *, query, locale, requested_limit, results):
        save_calls.update(
            session=session, query=query, locale=locale, requested_limit=requested_limit, results=results
        )

    def fake_request_index(session, video_id, **kwargs):
        index_calls.update(session=session, video_id=video_id)
        return state

    monkeypatch.setattr("app.ingest.youtube.save_search_results", fake_save)
    monkeypatch.setattr("app.ingest.youtube.request_video_indexing", fake_request_index)

    fake_session = object()
    url = "https://www.youtube.com/watch?v=abc123XYZ90"
    returned = ingest_youtube_video(fake_session, url)

    assert returned is state
    assert save_calls == {
        "session": fake_session,
        "query": url,
        "locale": "zh-TW",
        "requested_limit": 1,
        "results": [result],
    }
    assert index_calls == {"session": fake_session, "video_id": "abc123XYZ90"}


def test_ingest_youtube_video_rejects_unrecognized_url() -> None:
    with pytest.raises(UnrecognizedYouTubeUrlError):
        ingest_youtube_video(object(), "https://www.youtube.com/results?search_query=test")
