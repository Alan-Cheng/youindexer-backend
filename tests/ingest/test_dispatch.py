import pytest

from app.ingest.dispatch import UnknownUrlSourceError, detect_url_source


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.youtube.com/watch?v=abc123XYZ90", "youtube"),
        ("https://youtu.be/abc123XYZ90", "youtube"),
        ("https://m.youtube.com/watch?v=abc123XYZ90", "youtube"),
        ("https://www.instagram.com/p/Cxyz123/", "instagram"),
        ("https://instagram.com/p/Cxyz123/", "instagram"),
        ("https://www.threads.net/@user/post/Cxyz123", "threads"),
        ("https://www.threads.com/@user/post/Cxyz123", "threads"),
    ],
)
def test_detect_url_source(url: str, expected: str) -> None:
    assert detect_url_source(url) == expected


@pytest.mark.parametrize(
    "url",
    ["https://example.com/watch?v=abc123", "not a url", ""],
)
def test_detect_url_source_rejects_unknown_host(url: str) -> None:
    with pytest.raises(UnknownUrlSourceError):
        detect_url_source(url)
