"""OpenSearch storage and retrieval for timestamped subtitle segments."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from opensearchpy import OpenSearch
from opensearchpy.exceptions import OpenSearchException
from opensearchpy.helpers import bulk

from app.config import Settings, settings


class SubtitleIndexError(RuntimeError):
    """Raised when subtitle documents cannot be indexed or searched."""


@dataclass(frozen=True, slots=True)
class SubtitleSearchHit:
    video_id: str
    title: str
    language: str
    start_ms: int
    end_ms: int
    text: str
    score: float
    matched_keywords: tuple[str, ...] = ()
    highlighted_text: str | None = None


def _client(config: Settings) -> OpenSearch:
    parsed = urlparse(config.opensearch_url)
    return OpenSearch(
        hosts=[
            {
                "host": parsed.hostname or "localhost",
                "port": parsed.port or (443 if parsed.scheme == "https" else 9200),
                "scheme": parsed.scheme or "http",
            }
        ],
        http_compress=True,
        timeout=30,
    )


INDEX_BODY: dict[str, Any] = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "dynamic": "strict",
        "properties": {
            "video_id": {"type": "keyword"},
            "language": {"type": "keyword"},
            "segment_no": {"type": "integer"},
            "start_ms": {"type": "long"},
            "end_ms": {"type": "long"},
            "text_zh": {"type": "text", "analyzer": "cjk"},
            "text_en": {"type": "text", "analyzer": "english"},
            "title": {"type": "text"},
            "video_url": {"type": "keyword", "index": False},
            "source": {"type": "keyword"},
            "object_name": {"type": "keyword"},
            "generation_id": {"type": "keyword"},
            "fetched_at": {"type": "date"},
            "indexed_at": {"type": "date"},
        },
    },
}


class OpenSearchSubtitleIndexer:
    def __init__(
        self,
        client: OpenSearch,
        *,
        index_name: str,
        index_alias: str,
    ) -> None:
        self.client = client
        self.index_name = index_name
        self.index_alias = index_alias

    @classmethod
    def from_settings(cls, config: Settings = settings) -> OpenSearchSubtitleIndexer:
        return cls(
            _client(config),
            index_name=config.opensearch_subtitle_index,
            index_alias=config.opensearch_subtitle_alias,
        )

    def ensure_index(self) -> None:
        try:
            if not self.client.indices.exists(index=self.index_name):
                self.client.indices.create(index=self.index_name, body=INDEX_BODY)
            if not self.client.indices.exists_alias(name=self.index_alias):
                self.client.indices.put_alias(
                    index=self.index_name,
                    name=self.index_alias,
                    body={"is_write_index": True},
                )
        except OpenSearchException as exc:
            raise SubtitleIndexError(
                f"failed to prepare subtitle index: {exc}"
            ) from exc

    def index_document(
        self,
        document: dict[str, Any],
        *,
        object_name: str,
        generation_id: str,
    ) -> int:
        self.ensure_index()
        segments = document.get("segments")
        if document.get("version") != 1 or not isinstance(segments, list):
            raise SubtitleIndexError("unsupported or invalid subtitle document schema")
        video_id = str(document.get("video_id") or "")
        language = str(document.get("language") or "")
        if not video_id or language not in {"zh-TW", "en"}:
            raise SubtitleIndexError(
                "subtitle document has invalid video_id or language"
            )

        indexed_at = datetime.now(UTC).isoformat()
        actions: list[dict[str, Any]] = []
        text_field = "text_zh" if language == "zh-TW" else "text_en"
        for segment_no, segment in enumerate(segments):
            if not isinstance(segment, dict):
                raise SubtitleIndexError(f"segment {segment_no} is not an object")
            text = str(segment.get("text") or "").strip()
            if not text:
                continue
            start_ms = int(segment["start_ms"])
            end_ms = int(segment["end_ms"])
            if start_ms < 0 or end_ms < start_ms:
                raise SubtitleIndexError(
                    f"segment {segment_no} has an invalid time range"
                )
            source: dict[str, Any] = {
                "video_id": video_id,
                "language": language,
                "segment_no": segment_no,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "text_zh": text if text_field == "text_zh" else None,
                "text_en": text if text_field == "text_en" else None,
                "title": document.get("title") or "",
                "video_url": document.get("video_url") or "",
                "source": document.get("source") or "unknown",
                "object_name": object_name,
                "generation_id": generation_id,
                "fetched_at": document.get("fetched_at"),
                "indexed_at": indexed_at,
            }
            actions.append(
                {
                    "_op_type": "index",
                    "_index": self.index_alias,
                    "_id": f"{video_id}:{language}:{segment_no}",
                    "_source": source,
                }
            )
        if not actions:
            raise SubtitleIndexError(
                "subtitle document contains no searchable segments"
            )

        try:
            succeeded, errors = bulk(
                self.client,
                actions,
                raise_on_error=False,
                raise_on_exception=False,
                refresh="wait_for",
            )
            if errors:
                raise SubtitleIndexError(
                    f"OpenSearch rejected {len(errors)} subtitle segment(s)"
                )
            self.client.delete_by_query(
                index=self.index_alias,
                body={
                    "query": {
                        "bool": {
                            "filter": [
                                {"term": {"video_id": video_id}},
                                {"term": {"language": language}},
                            ],
                            "must_not": [{"term": {"generation_id": generation_id}}],
                        }
                    }
                },
                conflicts="proceed",
                refresh=True,
            )
        except OpenSearchException as exc:
            raise SubtitleIndexError(
                f"failed to index subtitle segments: {exc}"
            ) from exc
        return succeeded

    def search(
        self,
        query: str,
        *,
        aliases: list[str] | tuple[str, ...] | None = None,
        video_ids: list[str] | tuple[str, ...] | None = None,
        language: str | None = None,
        languages: tuple[str, ...] | None = None,
        limit: int | None = None,
        matches_per_video: int = 5,
    ) -> list[SubtitleSearchHit]:
        """Search subtitle segments, optionally restricted to selected videos."""
        fields = ["text_zh^5", "text_en^5"]
        if language is not None and languages is not None:
            raise ValueError("language and languages cannot both be specified")
        filters = [{"term": {"language": language}}] if language else []
        if languages is not None:
            filters.append({"terms": {"language": list(languages)}})
        normalized_video_ids = list(dict.fromkeys(video_ids or ()))
        if video_ids is not None:
            if not normalized_video_ids:
                return []
            filters.append({"terms": {"video_id": normalized_video_ids}})
        result_limit = (
            limit
            if limit is not None
            else (len(normalized_video_ids) if video_ids is not None else 10)
        )
        search_terms = list(dict.fromkeys([query, *(aliases or ())]))
        named_terms = {
            f"keyword_{index}": term for index, term in enumerate(search_terms)
        }
        body: dict[str, Any] = {
            "size": result_limit,
            "query": {
                "bool": {
                    "must": [
                        {
                            "bool": {
                                "should": [
                                    {
                                        "multi_match": {
                                            "_name": name,
                                            "query": term,
                                            "fields": fields,
                                        }
                                    }
                                    for name, term in named_terms.items()
                                ],
                                "minimum_should_match": 1,
                            }
                        }
                    ],
                    "filter": filters,
                }
            },
            "collapse": {
                "field": "video_id",
                "inner_hits": {
                    "name": "matching_segments",
                    "size": matches_per_video,
                    "sort": [{"_score": "desc"}, {"start_ms": "asc"}],
                    "highlight": {
                        "pre_tags": ["<mark>"],
                        "post_tags": ["</mark>"],
                        "encoder": "html",
                        "number_of_fragments": 0,
                        "fields": {"text_zh": {}, "text_en": {}},
                    },
                },
            },
        }
        try:
            response = self.client.search(index=self.index_alias, body=body)
        except OpenSearchException as exc:
            raise SubtitleIndexError(f"failed to search subtitles: {exc}") from exc

        results: list[SubtitleSearchHit] = []
        for group in response.get("hits", {}).get("hits", []):
            inner = (
                group.get("inner_hits", {})
                .get("matching_segments", {})
                .get("hits", {})
                .get("hits", [])
            )
            for hit in inner or [group]:
                source = hit["_source"]
                text = source.get("text_zh") or source.get("text_en") or ""
                matched_names = hit.get("matched_queries", [])
                if isinstance(matched_names, str):
                    matched_names = [matched_names]
                matched_keywords = tuple(
                    named_terms[name]
                    for name in matched_names
                    if name in named_terms
                )
                highlights = hit.get("highlight", {})
                highlighted_text = next(
                    (
                        fragment
                        for field in ("text_zh", "text_en")
                        for fragment in highlights.get(field, [])
                        if isinstance(fragment, str)
                    ),
                    None,
                )
                results.append(
                    SubtitleSearchHit(
                        video_id=source["video_id"],
                        title=source.get("title") or "",
                        language=source["language"],
                        start_ms=source["start_ms"],
                        end_ms=source["end_ms"],
                        text=text,
                        score=float(hit.get("_score") or 0),
                        matched_keywords=matched_keywords,
                        highlighted_text=highlighted_text,
                    )
                )
        return results
