import asyncio
import json
from datetime import UTC, datetime

import httpx
import pytest

from app.api.v1.youtube import (
    KeywordSearchJobRequest,
    create_keyword_search,
    keyword_search_job,
    keyword_search_job_events,
)
from app.main import app
from app.youtube import YouTubeSearchError, YouTubeSearchResult, YouTubeSuggestionError


class _ASGIClient:
    """Synchronous facade avoiding Starlette TestClient's Python 3.14 deadlock."""

    def get(self, path: str, *, params: dict | None = None) -> httpx.Response:
        async def request() -> httpx.Response:
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as client:
                return await client.get(path, params=params)

        return asyncio.run(request())


client = _ASGIClient()


@pytest.fixture(autouse=True)
def _run_thread_calls_inline(monkeypatch):
    """Avoid Python 3.14 ASGITransport/thread shutdown deadlocks in API tests."""

    async def immediate_to_thread(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr("app.api.v1.youtube.asyncio.to_thread", immediate_to_thread)


def _ignore_search_persistence(*args, **kwargs) -> None:
    return None


def test_youtube_suggestions_uses_headless_browser(monkeypatch) -> None:
    received: dict[str, object] = {}

    def fake_suggestions(query: str, limit: int, **kwargs):
        received.update(query=query, limit=limit, **kwargs)
        return ["python tutorial", "python tutorial 中文"]

    monkeypatch.setattr("app.api.v1.youtube.get_youtube_suggestions", fake_suggestions)
    response = client.get(
        "/api/v1/youtube/suggestions",
        params={"q": " python ", "limit": 5, "locale": "en-US", "timeout_ms": 45000},
    )

    assert response.status_code == 200
    assert received == {
        "query": "python",
        "limit": 5,
        "headless": True,
        "timeout_ms": 45000,
        "locale": "en-US",
    }
    assert response.json() == {
        "query": "python",
        "count": 2,
        "items": ["python tutorial", "python tutorial 中文"],
    }


def test_youtube_suggestions_rejects_blank_query() -> None:
    response = client.get("/api/v1/youtube/suggestions", params={"q": "   "})
    assert response.status_code == 422


def test_youtube_suggestions_maps_failure_to_bad_gateway(monkeypatch) -> None:
    def fake_suggestions(*args, **kwargs):
        raise YouTubeSuggestionError("YouTube suggestions unavailable")

    monkeypatch.setattr("app.api.v1.youtube.get_youtube_suggestions", fake_suggestions)
    response = client.get("/api/v1/youtube/suggestions", params={"q": "python"})

    assert response.status_code == 502
    assert response.json() == {"detail": "YouTube suggestions unavailable"}


def sample_result() -> YouTubeSearchResult:
    return YouTubeSearchResult(
        video_id="abc123",
        title="Playwright 教學",
        url="https://www.youtube.com/watch?v=abc123",
        channel_name="測試頻道",
        channel_url="https://www.youtube.com/@test",
        thumbnail_url="https://i.ytimg.com/vi/abc123/hqdefault.jpg",
        duration="10:00",
        published_text="1 年前",
        view_count_text="觀看次數：1000次",
        description="測試說明",
    )


def test_youtube_search_uses_headless_browser(monkeypatch) -> None:
    received: dict[str, object] = {}

    def fake_search(query: str, limit: int, **kwargs):
        received.update(query=query, limit=limit, **kwargs)
        return [sample_result()]

    monkeypatch.setattr("app.api.v1.youtube.search_youtube", fake_search)
    monkeypatch.setattr("app.api.v1.youtube._save_search", _ignore_search_persistence)
    response = client.get(
        "/api/v1/youtube/search",
        params={
            "q": " Playwright ",
            "limit": 3,
            "locale": "en-US",
            "timeout_ms": 45000,
        },
    )

    assert response.status_code == 200
    assert received == {
        "query": "Playwright",
        "limit": 3,
        "headless": True,
        "timeout_ms": 45000,
        "locale": "en-US",
    }
    assert response.json()["count"] == 1
    assert response.json()["items"][0]["video_id"] == "abc123"


def test_youtube_search_rejects_invalid_limit() -> None:
    response = client.get(
        "/api/v1/youtube/search",
        params={"q": "Playwright", "limit": 101},
    )
    assert response.status_code == 422


def test_youtube_search_rejects_blank_query() -> None:
    response = client.get(
        "/api/v1/youtube/search",
        params={"q": "   "},
    )
    assert response.status_code == 422


def test_youtube_search_maps_playwright_failure_to_bad_gateway(monkeypatch) -> None:
    def fake_search(*args, **kwargs):
        raise YouTubeSearchError("YouTube unavailable")

    monkeypatch.setattr("app.api.v1.youtube.search_youtube", fake_search)
    response = client.get(
        "/api/v1/youtube/search",
        params={"q": "Playwright"},
    )

    assert response.status_code == 502
    assert response.json() == {"detail": "YouTube unavailable"}


def _job_snapshot(*, status: str = "processing") -> dict:
    now = datetime(2026, 8, 18, tzinfo=UTC)
    return {
        "task_id": "task-123",
        "query": "robot",
        "status": status,
        "requested_count": 1,
        "video_count": 1,
        "completed_count": 1 if status == "completed" else 0,
        "matched_count": 1 if status == "completed" else 0,
        "videos": {
            "abc123": {
                "status": "matched" if status == "completed" else "loading",
                "metadata": sample_result().as_dict(),
                "keyword_matches": [],
                "transcripts": [],
                "error": None,
            }
        },
        "error": None,
        "created_at": now,
        "updated_at": now,
        "completed_at": now if status == "completed" else None,
    }


def test_create_keyword_job_returns_all_metadata_as_loading(monkeypatch) -> None:
    result = sample_result()
    snapshot = _job_snapshot()
    monkeypatch.setattr("app.api.v1.youtube._configured_stream_limit", lambda: 1)
    monkeypatch.setattr("app.api.v1.youtube.search_youtube", lambda *a, **k: [result])
    monkeypatch.setattr("app.api.v1.youtube._save_search", lambda *a, **k: None)
    monkeypatch.setattr("app.api.v1.youtube._request_index", lambda *a, **k: None)
    monkeypatch.setattr(
        "app.api.v1.youtube._create_keyword_job", lambda **kwargs: "task-123"
    )
    monkeypatch.setattr("app.api.v1.youtube._get_keyword_job", lambda task_id: snapshot)

    response = asyncio.run(
        create_keyword_search(
            KeywordSearchJobRequest(query=" robot ", matches_per_video=5)
        )
    )

    assert response.task_id == "task-123"
    assert response.video_count == 1
    assert response.videos["abc123"].status == "loading"
    assert response.videos["abc123"].metadata.title == "Playwright 教學"


def test_job_api_and_sse_snapshot_share_response_body(monkeypatch) -> None:
    snapshot = _job_snapshot(status="completed")
    monkeypatch.setattr("app.api.v1.youtube._get_keyword_job", lambda task_id: snapshot)

    async def collect():
        api_response = await keyword_search_job("task-123")
        stream_response = await keyword_search_job_events("task-123")
        chunks = [chunk async for chunk in stream_response.body_iterator]
        return api_response, "".join(chunks)

    api_response, stream_body = asyncio.run(collect())
    data_line = next(
        line.removeprefix("data: ")
        for line in stream_body.splitlines()
        if line.startswith("data: ")
    )

    assert json.loads(data_line) == json.loads(api_response.model_dump_json())
