from app.indexing.opensearch import OpenSearchSubtitleIndexer, _segment_zh


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


class _HighlightedSearchClient(_SearchClient):
    def search(self, **kwargs) -> dict:
        self.search_request = kwargs
        return {
            "hits": {
                "hits": [
                    {
                        "_score": 3.5,
                        "_source": {
                            "video_id": "video-1",
                            "title": "Example",
                            "language": "zh-TW",
                            "start_ms": 100,
                            "end_ms": 200,
                            "text_zh": "人工智慧",
                        },
                        "matched_queries": ["keyword_1"],
                        "highlight": {"text_zh": ["人工<mark>智慧</mark>"]},
                    }
                ]
            }
        }


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
    assert captured[0]["_source"]["text_zh_tokens"]
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


def test_search_prioritizes_raw_query_before_aliases() -> None:
    client = _SearchClient()
    indexer = OpenSearchSubtitleIndexer(
        client, index_name="subtitle-segments-v1", index_alias="subtitle-segments"
    )

    indexer.search("robot", aliases=["AI", "machine intelligence"])

    assert client.search_request is not None
    should = client.search_request["body"]["query"]["bool"]["must"][0]["bool"]["should"]
    assert [item["multi_match"]["query"] for item in should] == [
        "robot",
        "AI",
        "machine intelligence",
        "robot",
        "AI",
        "machine intelligence",
    ]
    assert [item["multi_match"]["_name"] for item in should] == [
        "keyword_0",
        "keyword_1",
        "keyword_2",
        "token_0",
        "token_1",
        "token_2",
    ]
    assert [item["multi_match"]["boost"] for item in should] == [10, 10, 10, 1, 1, 1]
    assert all(
        item["multi_match"]["operator"] == "and" for item in should[3:]
    )
    assert should[0]["multi_match"]["type"] == "phrase"


def test_search_falls_back_to_raw_query_without_processed_alias() -> None:
    client = _SearchClient()
    indexer = OpenSearchSubtitleIndexer(
        client, index_name="subtitle-segments-v1", index_alias="subtitle-segments"
    )

    indexer.search("人工智慧", aliases=[])

    assert client.search_request is not None
    should = client.search_request["body"]["query"]["bool"]["must"][0]["bool"][
        "should"
    ]
    assert [item["multi_match"]["query"] for item in should] == [
        "人工智慧",
        _segment_zh("人工智慧"),
    ]
    assert should[0]["multi_match"]["type"] == "phrase"


def test_search_segments_chinese_terms_before_querying() -> None:
    client = _SearchClient()
    indexer = OpenSearchSubtitleIndexer(
        client, index_name="subtitle-segments-v1", index_alias="subtitle-segments"
    )

    indexer.search("人工智慧")

    assert client.search_request is not None
    should = client.search_request["body"]["query"]["bool"]["must"][0]["bool"][
        "should"
    ]
    assert " " in should[1]["multi_match"]["query"]


def test_search_returns_matched_keywords_and_highlight() -> None:
    client = _HighlightedSearchClient()
    indexer = OpenSearchSubtitleIndexer(
        client, index_name="subtitle-segments-v1", index_alias="subtitle-segments"
    )

    hits = indexer.search("AI", aliases=["人工智慧"])

    assert hits[0].matched_keywords == ("人工智慧",)
    assert hits[0].highlighted_text == "人工<mark>智慧</mark>"


def test_search_generates_highlight_when_opensearch_returns_no_fragment() -> None:
    client = _SearchClient()
    client.search = lambda **kwargs: {
        "hits": {
            "hits": [
                {
                    "_source": {
                        "video_id": "video-1",
                        "title": "Example",
                        "language": "zh-TW",
                        "start_ms": 100,
                        "end_ms": 200,
                        "text_zh": "剛臘腸狗那邊",
                    }
                }
            ]
        }
    }
    indexer = OpenSearchSubtitleIndexer(
        client, index_name="subtitle-segments-v1", index_alias="subtitle-segments"
    )

    hits = indexer.search("臘腸狗")

    assert hits[0].highlighted_text == "剛<mark>臘腸狗</mark>那邊"


def test_search_can_be_restricted_to_configured_languages() -> None:
    client = _SearchClient()
    indexer = OpenSearchSubtitleIndexer(
        client, index_name="subtitle-segments-v1", index_alias="subtitle-segments"
    )

    assert indexer.search("robot", languages=("zh-TW",)) == []

    assert client.search_request is not None
    filters = client.search_request["body"]["query"]["bool"]["filter"]
    assert {"terms": {"language": ["zh-TW"]}} in filters


def test_search_with_explicit_empty_video_ids_does_not_search() -> None:
    client = _SearchClient()
    indexer = OpenSearchSubtitleIndexer(
        client, index_name="subtitle-segments-v1", index_alias="subtitle-segments"
    )

    assert indexer.search("robot", video_ids=[]) == []
    assert client.search_request is None
