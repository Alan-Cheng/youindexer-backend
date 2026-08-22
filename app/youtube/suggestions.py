"""YouTube search-box suggestions collected from the public web UI."""

from __future__ import annotations

from playwright.sync_api import (
    Error as PlaywrightError,
    Locator,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

YOUTUBE_ORIGIN = "https://www.youtube.com"
SEARCH_INPUT_SELECTOR = 'input[name="search_query"]'
SUGGESTION_SELECTORS = (
    "[role='option'] .ytSuggestionComponentSuggestion",
    "[role='option'] .yt-core-attributed-string",
    "#suggestions ytd-searchbox-spt yt-formatted-string",
    "yt-searchbox [role='option']",
)


class YouTubeSuggestionError(RuntimeError):
    """Raised when YouTube suggestions cannot be collected."""


def _clean_suggestion(value: str) -> str:
    """Normalize the visible text of a suggestion option."""
    return " ".join(value.split()).strip()


def _collect_suggestions(page, limit: int) -> list[str]:
    suggestions: list[str] = []
    seen: set[str] = set()

    for selector in SUGGESTION_SELECTORS:
        options: Locator = page.locator(selector)
        for index in range(options.count()):
            value = _clean_suggestion(options.nth(index).inner_text())
            key = value.casefold()
            if value and key not in seen:
                seen.add(key)
                suggestions.append(value)
            if len(suggestions) >= limit:
                return suggestions
        if suggestions:
            break

    return suggestions


def get_youtube_suggestions(
    query: str,
    limit: int = 10,
    *,
    headless: bool = False,
    timeout_ms: int = 30_000,
    locale: str = "zh-TW",
) -> list[str]:
    """Type ``query`` into YouTube's web search box and return its dropdown items."""
    query = query.strip()
    if not query:
        raise ValueError("query must not be empty")
    if limit < 1:
        raise ValueError("limit must be at least 1")
    if limit > 20:
        raise ValueError("limit must not exceed 20")

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=headless)
            try:
                context = browser.new_context(locale=locale)
                page = context.new_page()
                page.goto(YOUTUBE_ORIGIN, wait_until="domcontentloaded", timeout=timeout_ms)

                search_input = page.locator(SEARCH_INPUT_SELECTOR).first
                search_input.wait_for(state="visible", timeout=timeout_ms)
                search_input.fill(query)

                combined_selector = ", ".join(SUGGESTION_SELECTORS)
                page.locator(combined_selector).first.wait_for(
                    state="visible", timeout=timeout_ms
                )
                return _collect_suggestions(page, limit)
            finally:
                browser.close()
    except PlaywrightTimeoutError as exc:
        raise YouTubeSuggestionError(
            "Timed out waiting for YouTube search suggestions; the page layout or "
            "network response may have changed"
        ) from exc
    except PlaywrightError as exc:
        raise YouTubeSuggestionError(
            f"Playwright could not fetch YouTube suggestions: {exc}"
        ) from exc
