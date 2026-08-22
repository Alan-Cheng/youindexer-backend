import pytest

from app.threads.keyword_search import search_posts


@pytest.mark.parametrize("keyword", ["", "   "])
def test_rejects_empty_keyword(keyword: str) -> None:
    with pytest.raises(ValueError, match="keyword must not be empty"):
        search_posts(keyword, 1)


@pytest.mark.parametrize("limit", [0, -1])
def test_rejects_non_positive_limit(limit: int) -> None:
    with pytest.raises(ValueError, match="limit must be at least 1"):
        search_posts("formula1", limit)


def test_rejects_excessive_limit() -> None:
    with pytest.raises(ValueError, match="limit must not exceed 50"):
        search_posts("formula1", 51)
