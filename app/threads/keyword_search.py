"""Search Threads' public search results for a keyword.

Unlike the profile page, Threads' search results are rendered client-side
without an embedded JSON payload, so this reads the live DOM instead (see
:func:`app.threads.client.extract_search_results`). The public ``search_posts``
function is synchronous on purpose, matching :mod:`app.threads.profile`.
"""

from __future__ import annotations

from urllib.parse import quote

from app.threads.client import extract_search_results, open_page
from app.threads.errors import ThreadsLoginRequiredError
from app.threads.models import ThreadsPost

THREADS_ORIGIN = "https://www.threads.com"


def search_posts(
    keyword: str,
    limit: int,
    *,
    headless: bool = True,
    timeout_ms: int = 30_000,
    locale: str = "zh-TW",
    storage_state_path: str | None = None,
) -> list[ThreadsPost]:
    """Return up to ``limit`` recommended public posts for a keyword.

    Only the results Threads renders for an anonymous visitor's initial page
    load are available, so the returned count may be smaller than ``limit``.
    """
    keyword = keyword.strip()
    if not keyword:
        raise ValueError("keyword must not be empty")
    if limit < 1:
        raise ValueError("limit must be at least 1")
    if limit > 50:
        raise ValueError("limit must not exceed 50")

    search_url = f"{THREADS_ORIGIN}/search?q={quote(keyword)}&serp_type=default"

    with open_page(
        headless=headless, locale=locale, storage_state_path=storage_state_path
    ) as page:
        page.goto(search_url, wait_until="networkidle", timeout=timeout_ms)
        posts = extract_search_results(page)

    if not posts:
        raise ThreadsLoginRequiredError(
            f"No public threads were found for keyword '{keyword}'; Threads "
            "may be requiring a login for this search"
        )

    return posts[:limit]
