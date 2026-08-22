"""Shared Playwright and JSON-extraction helpers for the Instagram crawler.

Instagram's logged-out web pages still server-render the first batch of public
post data as inline ``<script type="application/json">`` payloads, even though a
sign-up modal is shown on top of the page. This module loads a page and walks
those payloads for post-shaped nodes instead of scraping the visual DOM, since
the DOM itself uses unstable, auto-generated atomic CSS class names.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from contextlib import contextmanager

from playwright.sync_api import (
    Error as PlaywrightError,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

from app.instagram.errors import InstagramCrawlError
from app.instagram.models import InstagramPost

_JSON_SCRIPT_RE = re.compile(
    r'<script type="application/json"[^>]*>(.*?)</script>', re.S
)


@contextmanager
def open_page(
    *,
    headless: bool,
    locale: str,
    storage_state_path: str | None,
) -> Iterator[Page]:
    """Open a fresh, isolated Playwright page for a single anonymous crawl.

    ``storage_state_path`` is the reserved extension point for authenticated
    crawling: pass a Playwright storage-state file (exported from a logged-in
    session) to bypass Instagram's anonymous content limits once one exists.
    """
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=headless)
            try:
                context = browser.new_context(
                    locale=locale, storage_state=storage_state_path
                )
                page = context.new_page()
                yield page
            finally:
                browser.close()
    except PlaywrightTimeoutError as exc:
        raise InstagramCrawlError(
            "Timed out waiting for Instagram; the page layout or network "
            "response may have changed"
        ) from exc
    except PlaywrightError as exc:
        raise InstagramCrawlError(f"Playwright could not load Instagram: {exc}") from exc


def _iter_media_nodes(obj: object) -> Iterator[dict]:
    """Recursively find post-shaped nodes inside Instagram's embedded JSON.

    A node is treated as a post when it carries a ``code`` (post shortcode)
    together with either ``caption`` or ``display_uri``, which is the shape
    shared by both the profile timeline and the hashtag/topic feed payloads.
    """
    if isinstance(obj, dict):
        if "code" in obj and ("caption" in obj or "display_uri" in obj):
            yield obj
        for value in obj.values():
            yield from _iter_media_nodes(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _iter_media_nodes(item)


def extract_media_nodes(html: str) -> list[dict]:
    """Return de-duplicated post nodes embedded in an Instagram page's HTML."""
    nodes: dict[str, dict] = {}
    for block in _JSON_SCRIPT_RE.findall(html):
        try:
            payload = json.loads(block)
        except json.JSONDecodeError:
            continue
        for node in _iter_media_nodes(payload):
            code = node.get("code")
            if code and code not in nodes:
                nodes[code] = node
    return list(nodes.values())


def node_to_post(node: dict, *, fallback_username: str | None = None) -> InstagramPost:
    """Map one embedded media node to an :class:`InstagramPost`."""
    code = node["code"]
    caption = node.get("caption")
    user = node.get("user") or {}
    username = user.get("username") or fallback_username or ""
    return InstagramPost(
        post_id=code,
        url=f"https://www.instagram.com/p/{code}/",
        username=username,
        caption=caption.get("text") if isinstance(caption, dict) else None,
        accessibility_caption=node.get("accessibility_caption"),
        thumbnail_url=node.get("display_uri"),
        is_video=str(node.get("__typename", "")).endswith("VideoMedia"),
    )
