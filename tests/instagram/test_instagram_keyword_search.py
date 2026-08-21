import pytest

from app.instagram.keyword_search import _normalize_tag, search_posts


@pytest.mark.parametrize(
    ("keyword", "expected"),
    [
        ("Cats", "cats"),
        (" cute cats! ", "cutecats"),
        ("#foryou", "foryou"),
        ("貓咪", "貓咪"),
    ],
)
def test_normalize_tag(keyword: str, expected: str) -> None:
    assert _normalize_tag(keyword) == expected


def test_normalize_tag_rejects_only_punctuation() -> None:
    with pytest.raises(ValueError, match="keyword must contain"):
        _normalize_tag("!!!")


@pytest.mark.parametrize("limit", [0, -1])
def test_rejects_non_positive_limit(limit: int) -> None:
    with pytest.raises(ValueError, match="limit must be at least 1"):
        search_posts("cats", limit)


def test_rejects_excessive_limit() -> None:
    with pytest.raises(ValueError, match="limit must not exceed 50"):
        search_posts("cats", 51)
