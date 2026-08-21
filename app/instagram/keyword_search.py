"""Search Instagram's public hashtag/topic feed for a keyword.

Instagram has no logged-out endpoint for a free-text post search; the closest
public equivalent is the hashtag/topic feed, which surfaces posts Instagram
already considers representative for that tag. The public ``search_posts``
function is synchronous on purpose, matching :mod:`app.instagram.profile`.
"""

from __future__ import annotations

import re
from urllib.parse import quote

from app.instagram.client import extract_media_nodes, node_to_post, open_page
from app.instagram.errors import InstagramLoginRequiredError
from app.instagram.models import InstagramPost

INSTAGRAM_ORIGIN = "https://www.instagram.com"


def _normalize_tag(keyword: str) -> str:
    tag = re.sub(r"[^\w]", "", keyword.strip().lower())
    if not tag:
        raise ValueError("keyword must contain at least one letter, digit or underscore")
    return tag


def search_posts(
    keyword: str,
    limit: int,
    *,
    headless: bool = True,
    timeout_ms: int = 30_000,
    locale: str = "zh-TW",
    storage_state_path: str | None = None,
) -> list[InstagramPost]:
    """Return up to ``limit`` recommended public posts for a keyword/hashtag.

    ``keyword`` is normalized into an Instagram hashtag (non word characters
    are stripped). Only the first batch Instagram embeds for an anonymous
    visitor is available, so the returned count may be smaller than ``limit``.
    """
    if limit < 1:
        raise ValueError("limit must be at least 1")
    if limit > 50:
        raise ValueError("limit must not exceed 50")

    tag = _normalize_tag(keyword)
    tag_url = f"{INSTAGRAM_ORIGIN}/explore/tags/{quote(tag)}/"

    with open_page(
        headless=headless, locale=locale, storage_state_path=storage_state_path
    ) as page:
        page.goto(tag_url, wait_until="networkidle", timeout=timeout_ms)
        html = page.content()

    nodes = extract_media_nodes(html)
    if not nodes:
        raise InstagramLoginRequiredError(
            f"No public posts were found for hashtag '#{tag}'; Instagram may "
            "be requiring a login for this page"
        )

    posts = [node_to_post(node) for node in nodes]
    return posts[:limit]
