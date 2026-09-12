import json

from app.threads.client import extract_thread_posts, post_to_thread


def _wrap_script(payload: object) -> str:
    return f'<script type="application/json">{json.dumps(payload)}</script>'


def test_extract_thread_posts_finds_nested_posts_and_dedupes() -> None:
    payload = {
        "require": [
            {
                "result": {
                    "edges": [
                        {
                            "node": {
                                "thread_items": [
                                    {
                                        "post": {"code": "abc123", "pk": "1"},
                                        "__typename": "XDTThreadItem",
                                    },
                                    # Duplicated code must be de-duplicated.
                                    {
                                        "post": {"code": "abc123", "pk": "1"},
                                        "__typename": "XDTThreadItem",
                                    },
                                ]
                            }
                        }
                    ]
                }
            }
        ]
    }
    html = _wrap_script(payload) + _wrap_script({"not": "a thread item"})

    posts = extract_thread_posts(html)

    assert len(posts) == 1
    assert posts[0]["code"] == "abc123"


def test_extract_thread_posts_ignores_malformed_json_blocks() -> None:
    html = '<script type="application/json">{not valid json</script>'
    assert extract_thread_posts(html) == []


def test_extract_thread_posts_requires_thread_item_typename() -> None:
    payload = {"post": {"code": "xyz"}, "__typename": "SomethingElse"}
    html = _wrap_script(payload)
    assert extract_thread_posts(html) == []


def test_post_to_thread_maps_fields() -> None:
    post = {
        "code": "abc123",
        "caption": {"text": "hello world"},
        "user": {"username": "someone"},
        "taken_at": 1755504000,
        "like_count": 42,
        "image_versions2": {"candidates": [{"url": "https://example.com/thumb.jpg"}]},
    }

    thread_post = post_to_thread(post)

    assert thread_post.post_id == "abc123"
    assert thread_post.url == "https://www.threads.com/@someone/post/abc123"
    assert thread_post.username == "someone"
    assert thread_post.caption == "hello world"
    assert thread_post.like_count == 42
    assert thread_post.thumbnail_url == "https://example.com/thumb.jpg"
    assert thread_post.published_at == "2025-08-18T08:00:00+00:00"


def test_post_to_thread_uses_fallback_username_and_handles_missing_fields() -> None:
    post = {"code": "abc123", "caption": None}

    thread_post = post_to_thread(post, fallback_username="profile_owner")

    assert thread_post.username == "profile_owner"
    assert thread_post.caption is None
    assert thread_post.thumbnail_url is None
    assert thread_post.published_at is None
    assert thread_post.like_count is None
