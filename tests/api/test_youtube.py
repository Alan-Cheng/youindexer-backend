from fastapi.testclient import TestClient

from app.main import app
from app.youtube import YouTubeSearchError, YouTubeSearchResult

client = TestClient(app)


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
