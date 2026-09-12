import pytest

from app.youtube.suggestions import _clean_suggestion, get_youtube_suggestions
from app.youtube.suggestions_cli import build_parser


def test_clean_suggestion_normalizes_whitespace() -> None:
    assert _clean_suggestion("  python\n  tutorial  ") == "python tutorial"


@pytest.mark.parametrize("query", ["", "   "])
def test_suggestions_reject_empty_query(query: str) -> None:
    with pytest.raises(ValueError, match="query must not be empty"):
        get_youtube_suggestions(query)


@pytest.mark.parametrize("limit", [0, -1])
def test_suggestions_reject_non_positive_limit(limit: int) -> None:
    with pytest.raises(ValueError, match="limit must be at least 1"):
        get_youtube_suggestions("python", limit)


def test_suggestions_reject_excessive_limit() -> None:
    with pytest.raises(ValueError, match="limit must not exceed 20"):
        get_youtube_suggestions("python", 21)


def test_suggestions_cli_is_visible_by_default() -> None:
    assert build_parser().parse_args(["python"]).headless is False
