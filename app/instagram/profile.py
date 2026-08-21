"""Fetch public posts from an Instagram account's profile grid.

The public ``fetch_profile_posts`` function is synchronous on purpose: Celery
workers can call it directly. Async web handlers should execute it in a worker
thread with ``await asyncio.to_thread(fetch_profile_posts, ...)`` so the event
loop is not blocked.
"""

from __future__ import annotations

import re

from app.instagram.client import extract_media_nodes, node_to_post, open_page
from app.instagram.errors import InstagramLoginRequiredError
from app.instagram.models import InstagramPost

INSTAGRAM_ORIGIN = "https://www.instagram.com"
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9._]{1,30}$")


def fetch_profile_posts(
    username: str,
    limit: int,
    *,
    headless: bool = True,
    timeout_ms: int = 30_000,
    locale: str = "zh-TW",
    storage_state_path: str | None = None,
) -> list[InstagramPost]:
    """Return up to ``limit`` public posts from ``username``'s profile grid.

    Only the first batch of posts Instagram embeds for an anonymous visitor is
    available; scrolling further requires an authenticated session. The
    returned count may therefore be smaller than ``limit``.
    """
    username = username.strip().lstrip("@")
    if not USERNAME_PATTERN.match(username):
        raise ValueError("username must be 1-30 characters of letters, digits, '.' or '_'")
    if limit < 1:
        raise ValueError("limit must be at least 1")
    if limit > 50:
        raise ValueError("limit must not exceed 50")

    profile_url = f"{INSTAGRAM_ORIGIN}/{username}/"

    with open_page(
        headless=headless, locale=locale, storage_state_path=storage_state_path
    ) as page:
        page.goto(profile_url, wait_until="networkidle", timeout=timeout_ms)
        html = page.content()

    nodes = extract_media_nodes(html)
    if not nodes:
        raise InstagramLoginRequiredError(
            f"No public posts were found for '{username}'; Instagram may be "
            "requiring a login for this profile"
        )

    posts = [node_to_post(node, fallback_username=username) for node in nodes]
    return posts[:limit]
