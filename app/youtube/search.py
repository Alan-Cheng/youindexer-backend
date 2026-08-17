"""Anonymous YouTube keyword search implemented with Playwright.

The public ``search_youtube`` function is synchronous on purpose: Celery workers can
call it directly. Async web handlers should execute it in a worker thread with
``await asyncio.to_thread(search_youtube, ...)`` so the event loop is not blocked.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from urllib.parse import parse_qs, quote_plus, urljoin, urlparse

from playwright.sync_api import (
    Error as PlaywrightError,
    Locator,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)


YOUTUBE_ORIGIN = "https://www.youtube.com"
RESULT_SELECTOR = "ytd-video-renderer"


class YouTubeSearchError(RuntimeError):
    """Raised when YouTube cannot be searched or returns no usable page."""


@dataclass(frozen=True, slots=True)
class YouTubeSearchResult:
    video_id: str
    title: str
    url: str
    channel_name: str | None
    channel_url: str | None
    thumbnail_url: str | None
    duration: str | None
    published_text: str | None
    view_count_text: str | None
    description: str | None

    def as_dict(self) -> dict[str, str | None]:
        return asdict(self)


def _text(locator: Locator) -> str | None:
    if locator.count() == 0:
        return None
    value = locator.first.inner_text().strip()
    return value or None


def _attribute(locator: Locator, name: str) -> str | None:
    if locator.count() == 0:
        return None
    return locator.first.get_attribute(name)


def _video_id(href: str) -> str | None:
    query = parse_qs(urlparse(href).query)
    values = query.get("v")
    return values[0] if values else None


def _first_text_line(locator: Locator) -> str | None:
    value = _text(locator)
    if not value:
        return None
    return value.splitlines()[0].strip() or None


def _parse_renderer(renderer: Locator) -> YouTubeSearchResult | None:
    title_link = renderer.locator("a#video-title")
    href = _attribute(title_link, "href")
    title = _attribute(title_link, "title") or _text(title_link)
    if not href or not title:
        return None

    video_id = _video_id(urljoin(YOUTUBE_ORIGIN, href))
    if not video_id:
        return None

    thumbnail = renderer.locator("a#thumbnail img")
    thumbnail_url = _attribute(thumbnail, "src") or _attribute(
        thumbnail, "data-thumb"
    )

    channel_link = renderer.locator("#channel-name a").first
    channel_href = _attribute(channel_link, "href")
    metadata = renderer.locator("#metadata-line span")

    return YouTubeSearchResult(
        video_id=video_id,
        title=title,
        url=f"{YOUTUBE_ORIGIN}/watch?v={video_id}",
        channel_name=_text(channel_link),
        channel_url=urljoin(YOUTUBE_ORIGIN, channel_href) if channel_href else None,
        thumbnail_url=thumbnail_url
        or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
        duration=_first_text_line(
            renderer.locator("ytd-thumbnail-overlay-time-status-renderer")
        ),
        published_text=_text(metadata.nth(1)) if metadata.count() > 1 else None,
        view_count_text=_text(metadata.nth(0)) if metadata.count() else None,
        description=_text(renderer.locator(".metadata-snippet-text")),
    )


def search_youtube(
    query: str,
    limit: int,
    *,
    headless: bool = False,
    timeout_ms: int = 30_000,
    locale: str = "zh-TW",
) -> list[YouTubeSearchResult]:
    """Return up to ``limit`` anonymous YouTube video search results.

    A fresh isolated browser context is used for every call, so concurrent Celery
    jobs do not share cookies or browser state. The function scrolls when more than
    the initially rendered result count is requested.
    """
    query = query.strip()
    if not query:
        raise ValueError("query must not be empty")
    if limit < 1:
        raise ValueError("limit must be at least 1")
    if limit > 500:
        raise ValueError("limit must not exceed 500")

    search_url = f"{YOUTUBE_ORIGIN}/results?search_query={quote_plus(query)}"

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=headless)
            try:
                context = browser.new_context(locale=locale)
                page = context.new_page()
                page.goto(search_url, wait_until="domcontentloaded", timeout=timeout_ms)
                page.locator(RESULT_SELECTOR).first.wait_for(
                    state="attached", timeout=timeout_ms
                )

                results: dict[str, YouTubeSearchResult] = {}
                unchanged_rounds = 0
                previous_count = 0

                while len(results) < limit and unchanged_rounds < 3:
                    renderers = page.locator(RESULT_SELECTOR)
                    for index in range(renderers.count()):
                        result = _parse_renderer(renderers.nth(index))
                        if result:
                            results.setdefault(result.video_id, result)
                        if len(results) >= limit:
                            break

                    if len(results) >= limit:
                        break

                    current_count = renderers.count()
                    unchanged_rounds = (
                        unchanged_rounds + 1 if current_count == previous_count else 0
                    )
                    previous_count = current_count
                    page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
                    page.wait_for_timeout(1_000)

                return list(results.values())[:limit]
            finally:
                browser.close()
    except PlaywrightTimeoutError as exc:
        raise YouTubeSearchError(
            "Timed out waiting for YouTube search results; the page layout or "
            "network response may have changed"
        ) from exc
    except PlaywrightError as exc:
        raise YouTubeSearchError(f"Playwright could not search YouTube: {exc}") from exc
