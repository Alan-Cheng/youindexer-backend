"""Shared Playwright and extraction helpers for the Threads crawler.

Threads' logged-out profile page still server-renders the first batch of a
user's public threads as inline ``<script type="application/json">`` payloads,
even though a sign-up modal is shown on top of the page. The search results
page does not embed this JSON and is instead rendered client-side, so search
results are read from the live DOM through a small heuristic instead.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

from playwright.sync_api import (
    Error as PlaywrightError,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

from app.threads.errors import ThreadsCrawlError
from app.threads.models import ThreadsPost

_JSON_SCRIPT_RE = re.compile(
    r'<script type="application/json"[^>]*>(.*?)</script>', re.S
)

# Reads each rendered search result card by walking up from its permalink
# anchor and picking the first sibling text span that is not the author name,
# the timestamp, an engagement count, or a UI control label.
_SEARCH_RESULT_JS = r"""
() => {
  const results = [];
  const seen = new Set();
  const postAnchors = Array.from(document.querySelectorAll('a[href*="/post/"]'));
  for (const a of postAnchors) {
    const href = a.getAttribute('href') || '';
    const m = href.match(/^\/@([^/]+)\/post\/([^/?]+)/);
    if (!m) continue;
    const username = m[1];
    const code = m[2];
    if (seen.has(code)) continue;
    seen.add(code);

    const timeEl = a.querySelector('time[datetime]');
    const timestamp = timeEl ? timeEl.getAttribute('datetime') : null;
    const timeText = timeEl ? timeEl.textContent.trim() : null;

    let card = a;
    let captionText = null;
    for (let i = 0; i < 8 && card; i++) {
      card = card.parentElement;
      if (!card) break;
      const spans = Array.from(card.querySelectorAll('span[dir="auto"]'));
      for (const span of spans) {
        const clone = span.cloneNode(true);
        clone.querySelectorAll('a, [role="button"]').forEach((el) => el.remove());
        const text = clone.textContent.trim();
        if (!text) continue;
        if (text === username) continue;
        if (timeText && text === timeText) continue;
        if (/^[\d.,]+[KMB]?$/.test(text)) continue;
        if (/^\d{1,2}\/\d{1,2}\/\d{2,4}$/.test(text)) continue;
        if (/^\d+\s*(s|m|h|d|w|mo|y)$/.test(text)) continue;
        if (['Translate', 'More', 'Follow', 'Following'].includes(text)) continue;
        captionText = text;
        break;
      }
      if (captionText) break;
    }

    const img = card ? card.querySelector('img[src*="cdninstagram"], img[src*="fbcdn"]') : null;
    results.push({
      username,
      code,
      timestamp,
      caption: captionText,
      thumbnail_url: img ? img.getAttribute('src') : null,
    });
  }
  return results;
}
"""


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
    session) to bypass Threads' anonymous content limits once one exists.
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
        raise ThreadsCrawlError(
            "Timed out waiting for Threads; the page layout or network "
            "response may have changed"
        ) from exc
    except PlaywrightError as exc:
        raise ThreadsCrawlError(f"Playwright could not load Threads: {exc}") from exc


def _iter_thread_item_posts(obj: object) -> Iterator[dict]:
    """Recursively find ``post`` payloads inside Threads' embedded JSON."""
    if isinstance(obj, dict):
        if obj.get("__typename") == "XDTThreadItem" and isinstance(
            obj.get("post"), dict
        ):
            yield obj["post"]
        for value in obj.values():
            yield from _iter_thread_item_posts(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _iter_thread_item_posts(item)


def extract_thread_posts(html: str) -> list[dict]:
    """Return de-duplicated post payloads embedded in a Threads page's HTML."""
    posts: dict[str, dict] = {}
    for block in _JSON_SCRIPT_RE.findall(html):
        try:
            payload = json.loads(block)
        except json.JSONDecodeError:
            continue
        for post in _iter_thread_item_posts(payload):
            code = post.get("code")
            if code and code not in posts:
                posts[code] = post
    return list(posts.values())


def post_to_thread(post: dict, *, fallback_username: str | None = None) -> ThreadsPost:
    """Map one embedded ``post`` payload to a :class:`ThreadsPost`."""
    code = post["code"]
    caption = post.get("caption")
    user = post.get("user") or {}
    username = user.get("username") or fallback_username or ""
    taken_at = post.get("taken_at")
    published_at = (
        datetime.fromtimestamp(taken_at, tz=UTC).isoformat()
        if isinstance(taken_at, int | float)
        else None
    )
    image_versions = post.get("image_versions2") or {}
    candidates = image_versions.get("candidates") or []
    thumbnail_url = candidates[0]["url"] if candidates else None

    return ThreadsPost(
        post_id=code,
        url=f"https://www.threads.com/@{username}/post/{code}",
        username=username,
        caption=caption.get("text") if isinstance(caption, dict) else None,
        thumbnail_url=thumbnail_url,
        published_at=published_at,
        like_count=post.get("like_count"),
    )


def extract_search_results(page: Page) -> list[ThreadsPost]:
    """Read search-result thread cards from the live DOM (no embedded JSON)."""
    raw_results: list[dict] = page.evaluate(_SEARCH_RESULT_JS)
    return [
        ThreadsPost(
            post_id=item["code"],
            url=f"https://www.threads.com/@{item['username']}/post/{item['code']}",
            username=item["username"],
            caption=item.get("caption"),
            thumbnail_url=item.get("thumbnail_url"),
            published_at=item.get("timestamp"),
            like_count=None,
        )
        for item in raw_results
    ]
