import asyncio

import httpx

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
