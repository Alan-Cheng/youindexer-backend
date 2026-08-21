import json

from app.instagram.client import extract_media_nodes, node_to_post


def _wrap_script(payload: object) -> str:
    return f'<script type="application/json">{json.dumps(payload)}</script>'


def test_extract_media_nodes_finds_nested_nodes_and_dedupes() -> None:
    payload = {
        "require": [
            {
                "result": {
                    "edges": [
                        {
                            "node": {
                                "__typename": "XIGPolarisVideoMedia",
                                "code": "abc123",
                                "caption": {"text": "hello world"},
                                "display_uri": "https://example.com/thumb.jpg",
                                "user": {"username": "someone"},
                            }
                        },
                        # Same code appearing again (e.g. duplicated in another
                        # payload) must be de-duplicated.
                        {
                            "node": {
                                "__typename": "XIGPolarisVideoMedia",
                                "code": "abc123",
                                "caption": {"text": "hello world"},
                                "display_uri": "https://example.com/thumb.jpg",
                            }
                        },
                    ]
                }
            }
        ]
    }
    html = _wrap_script(payload) + _wrap_script({"not": "a media node"})

    nodes = extract_media_nodes(html)

    assert len(nodes) == 1
    assert nodes[0]["code"] == "abc123"


def test_extract_media_nodes_ignores_malformed_json_blocks() -> None:
    html = '<script type="application/json">{not valid json</script>'
    assert extract_media_nodes(html) == []


def test_extract_media_nodes_requires_caption_or_display_uri() -> None:
    payload = {"node": {"code": "xyz", "unrelated": "field"}}
    html = _wrap_script(payload)
    assert extract_media_nodes(html) == []


def test_node_to_post_maps_fields() -> None:
    node = {
        "__typename": "XIGPolarisVideoMedia",
        "code": "abc123",
        "caption": {"text": "hello world"},
        "accessibility_caption": "Video by someone.",
        "display_uri": "https://example.com/thumb.jpg",
        "user": {"username": "someone"},
    }

    post = node_to_post(node)

    assert post.post_id == "abc123"
    assert post.url == "https://www.instagram.com/p/abc123/"
    assert post.username == "someone"
    assert post.caption == "hello world"
    assert post.accessibility_caption == "Video by someone."
    assert post.thumbnail_url == "https://example.com/thumb.jpg"
    assert post.is_video is True


def test_node_to_post_uses_fallback_username_when_missing() -> None:
    node = {"code": "abc123", "caption": None, "display_uri": None}

    post = node_to_post(node, fallback_username="profile_owner")

    assert post.username == "profile_owner"
    assert post.caption is None
    assert post.is_video is False
