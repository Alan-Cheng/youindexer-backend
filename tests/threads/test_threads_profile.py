import pytest

from app.threads.profile import fetch_profile_posts


@pytest.mark.parametrize("username", ["", "   ", "has space", "way-too-long-" * 5])
def test_rejects_invalid_username(username: str) -> None:
    with pytest.raises(ValueError, match="username must be"):
        fetch_profile_posts(username, 1)


@pytest.mark.parametrize("limit", [0, -1])
def test_rejects_non_positive_limit(limit: int) -> None:
    with pytest.raises(ValueError, match="limit must be at least 1"):
        fetch_profile_posts("zuck", limit)


def test_rejects_excessive_limit() -> None:
    with pytest.raises(ValueError, match="limit must not exceed 50"):
        fetch_profile_posts("zuck", 51)
