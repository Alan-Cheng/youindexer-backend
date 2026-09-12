from fastapi.testclient import TestClient

from app.main import app
from app.threads import ThreadsCrawlError, ThreadsPost

client = TestClient(app)


def sample_post() -> ThreadsPost:
    return ThreadsPost(
        post_id="abc123",
        url="https://www.threads.com/@someone/post/abc123",
        username="someone",
        caption="hello world",
        thumbnail_url="https://example.com/thumb.jpg",
        published_at="2026-08-18T08:00:00+00:00",
        like_count=42,
    )


def test_crawl_by_keyword_wraps_result_in_envelope(monkeypatch) -> None:
    received: dict[str, object] = {}

    def fake_search(keyword: str, limit: int, **kwargs):
        received.update(keyword=keyword, limit=limit, **kwargs)
        return [sample_post()]

    monkeypatch.setattr("app.api.v1.threads.search_threads_posts", fake_search)
    response = client.post(
        "/api/v1/threads/crawl", json={"mode": "keyword", "keyword": "formula1", "limit": 5}
    )

    assert response.status_code == 200
    assert received == {"keyword": "formula1", "limit": 5, "storage_state_path": None}
    body = response.json()
    assert body["success"] is True
    assert body["data"]["mode"] == "keyword"
    assert body["data"]["count"] == 1
    assert body["data"]["items"][0]["like_count"] == 42


def test_crawl_by_profile_wraps_result_in_envelope(monkeypatch) -> None:
    received: dict[str, object] = {}

    def fake_fetch(username: str, limit: int, **kwargs):
        received.update(username=username, limit=limit, **kwargs)
        return [sample_post()]

    monkeypatch.setattr("app.api.v1.threads.fetch_threads_profile_posts", fake_fetch)
    response = client.post(
        "/api/v1/threads/crawl", json={"mode": "profile", "username": "zuck"}
    )

    assert response.status_code == 200
    assert received == {"username": "zuck", "limit": 10, "storage_state_path": None}
    body = response.json()
    assert body["data"]["mode"] == "profile"
    assert body["data"]["query"] == "zuck"


def test_crawl_requires_a_known_mode() -> None:
    response = client.post("/api/v1/threads/crawl", json={"mode": "unknown"})
    assert response.status_code == 422


def test_crawl_maps_value_error_to_422(monkeypatch) -> None:
    def fake_search(*args, **kwargs):
        raise ValueError("keyword must not be empty")

    monkeypatch.setattr("app.api.v1.threads.search_threads_posts", fake_search)
    response = client.post(
        "/api/v1/threads/crawl", json={"mode": "keyword", "keyword": "formula1"}
    )

    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False


def test_crawl_maps_crawl_error_to_bad_gateway(monkeypatch) -> None:
    def fake_search(*args, **kwargs):
        raise ThreadsCrawlError("Threads unavailable")

    monkeypatch.setattr("app.api.v1.threads.search_threads_posts", fake_search)
    response = client.post(
        "/api/v1/threads/crawl", json={"mode": "keyword", "keyword": "formula1"}
    )

    assert response.status_code == 502
    body = response.json()
    assert body["success"] is False
    assert body["message"] == "Threads unavailable"
