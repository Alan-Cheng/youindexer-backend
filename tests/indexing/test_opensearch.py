from app.indexing.opensearch import OpenSearchSubtitleIndexer


class _Indices:
    def __init__(self) -> None:
        self.created = False
        self.aliased = False

    def exists(self, *, index: str) -> bool:
        return self.created

    def create(self, *, index: str, body: dict) -> None:
        self.created = True

    def exists_alias(self, *, name: str) -> bool:
        return self.aliased

    def put_alias(self, **kwargs) -> None:
        self.aliased = True


class _Client:
    def __init__(self) -> None:
        self.indices = _Indices()
        self.deleted_query: dict | None = None

    def delete_by_query(self, **kwargs) -> None:
        self.deleted_query = kwargs


class _SearchClient(_Client):
    def __init__(self) -> None:
        super().__init__()
        self.search_request: dict | None = None

    def search(self, **kwargs) -> dict:
        self.search_request = kwargs
        return {"hits": {"hits": []}}


def subtitle_document() -> dict:
    return {
        "version": 1,
        "video_id": "abc123",
        "video_url": "https://www.youtube.com/watch?v=abc123",
        "title": "Example",
        "language": "zh-TW",
        "source": "youtube_manual",
        "fetched_at": "2026-08-17T00:00:00+00:00",
        "segments": [
            {"start_ms": 1200, "end_ms": 2600, "text": "介紹 OpenSearch"},
            {"start_ms": 3000, "end_ms": 4100, "text": "精確搜尋字幕"},
        ],
    }


def test_indexes_each_subtitle_segment_with_timestamp(monkeypatch) -> None:
    client = _Client()
    captured: list[dict] = []

    def fake_bulk(_client, actions, **kwargs):
        captured.extend(actions)
        return len(actions), []

    monkeypatch.setattr("app.indexing.opensearch.bulk", fake_bulk)
    indexer = OpenSearchSubtitleIndexer(
        client, index_name="subtitle-segments-v1", index_alias="subtitle-segments"
    )

    count = indexer.index_document(
        subtitle_document(),
        object_name="transcripts/abc123/zh-TW.json",
        generation_id="hash1",
    )

    assert count == 2
    assert captured[0]["_id"] == "abc123:zh-TW:0"
    assert captured[0]["_source"]["start_ms"] == 1200
    assert captured[0]["_source"]["text_zh"] == "介紹 OpenSearch"
    assert client.deleted_query is not None


def test_search_can_be_restricted_to_selected_video_ids() -> None:
    client = _SearchClient()
    indexer = OpenSearchSubtitleIndexer(
        client, index_name="subtitle-segments-v1", index_alias="subtitle-segments"
    )

    assert indexer.search("robot", video_ids=["video-1", "video-2"]) == []

    assert client.search_request is not None
    filters = client.search_request["body"]["query"]["bool"]["filter"]
    assert {"terms": {"video_id": ["video-1", "video-2"]}} in filters
    assert client.search_request["body"]["size"] == 2


def test_search_with_explicit_empty_video_ids_does_not_search() -> None:
    client = _SearchClient()
    indexer = OpenSearchSubtitleIndexer(
        client, index_name="subtitle-segments-v1", index_alias="subtitle-segments"
    )

    assert indexer.search("robot", video_ids=[]) == []
    assert client.search_request is None
