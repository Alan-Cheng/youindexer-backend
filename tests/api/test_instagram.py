from fastapi.testclient import TestClient

from app.instagram import InstagramCrawlError, InstagramPost
from app.main import app

client = TestClient(app)


def sample_post() -> InstagramPost:
    return InstagramPost(
        post_id="abc123",
        url="https://www.instagram.com/p/abc123/",
        username="someone",
        caption="hello world",
        accessibility_caption=None,
        thumbnail_url="https://example.com/thumb.jpg",
        is_video=False,
    )


def test_crawl_by_keyword_wraps_result_in_envelope(monkeypatch) -> None:
    received: dict[str, object] = {}

    def fake_search(keyword: str, limit: int, **kwargs):
        received.update(keyword=keyword, limit=limit, **kwargs)
        return [sample_post()]

    monkeypatch.setattr("app.api.v1.instagram.search_instagram_posts", fake_search)
    response = client.post(
        "/api/v1/instagram/crawl", json={"mode": "keyword", "keyword": "cats", "limit": 5}
    )

    assert response.status_code == 200
    assert received == {"keyword": "cats", "limit": 5, "storage_state_path": None}
    body = response.json()
    assert body["success"] is True
    assert body["data"]["mode"] == "keyword"
    assert body["data"]["query"] == "cats"
    assert body["data"]["count"] == 1
    assert body["data"]["items"][0]["post_id"] == "abc123"


def test_crawl_by_profile_wraps_result_in_envelope(monkeypatch) -> None:
    received: dict[str, object] = {}

    def fake_fetch(username: str, limit: int, **kwargs):
        received.update(username=username, limit=limit, **kwargs)
        return [sample_post()]

    monkeypatch.setattr("app.api.v1.instagram.fetch_instagram_profile_posts", fake_fetch)
    response = client.post(
        "/api/v1/instagram/crawl", json={"mode": "profile", "username": "instagram"}
    )

    assert response.status_code == 200
    assert received == {"username": "instagram", "limit": 10, "storage_state_path": None}
    body = response.json()
    assert body["data"]["mode"] == "profile"
    assert body["data"]["query"] == "instagram"


def test_crawl_requires_a_known_mode() -> None:
    response = client.post("/api/v1/instagram/crawl", json={"mode": "unknown"})
    assert response.status_code == 422


def test_crawl_maps_value_error_to_422(monkeypatch) -> None:
    def fake_search(*args, **kwargs):
        raise ValueError("keyword must not be empty")

    monkeypatch.setattr("app.api.v1.instagram.search_instagram_posts", fake_search)
    response = client.post(
        "/api/v1/instagram/crawl", json={"mode": "keyword", "keyword": "cats"}
    )

    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["message"] == "keyword must not be empty"


def test_crawl_maps_crawl_error_to_bad_gateway(monkeypatch) -> None:
    def fake_search(*args, **kwargs):
        raise InstagramCrawlError("Instagram unavailable")

    monkeypatch.setattr("app.api.v1.instagram.search_instagram_posts", fake_search)
    response = client.post(
        "/api/v1/instagram/crawl", json={"mode": "keyword", "keyword": "cats"}
    )

    assert response.status_code == 502
    body = response.json()
    assert body["success"] is False
    assert body["message"] == "Instagram unavailable"
