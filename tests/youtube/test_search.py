import pytest

from app.youtube.cli import build_parser
from app.youtube.search import _video_id, search_youtube


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.youtube.com/watch?v=abc123", "abc123"),
        ("/watch?v=xyz987&list=foo", "xyz987"),
        ("https://www.youtube.com/results?search_query=test", None),
    ],
)
def test_video_id(url: str, expected: str | None) -> None:
    assert _video_id(url) == expected


@pytest.mark.parametrize("query", ["", "   "])
def test_search_rejects_empty_query(query: str) -> None:
    with pytest.raises(ValueError, match="query must not be empty"):
        search_youtube(query, 1)


@pytest.mark.parametrize("limit", [0, -1])
def test_search_rejects_non_positive_limit(limit: int) -> None:
    with pytest.raises(ValueError, match="limit must be at least 1"):
        search_youtube("test", limit)


def test_search_rejects_excessive_limit() -> None:
    with pytest.raises(ValueError, match="limit must not exceed 500"):
        search_youtube("test", 501)


def test_cli_is_visible_by_default() -> None:
    args = build_parser().parse_args(["test"])
    assert args.headless is False


def test_cli_accepts_headless_switch() -> None:
    args = build_parser().parse_args(["test", "--headless"])
    assert args.headless is True
