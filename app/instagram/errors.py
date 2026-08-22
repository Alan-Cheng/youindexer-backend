"""Error types for the Instagram crawler service."""

from __future__ import annotations


class InstagramCrawlError(RuntimeError):
    """Raised when Instagram cannot be crawled or returns no usable page."""


class InstagramLoginRequiredError(InstagramCrawlError):
    """Raised when Instagram served no public post data for an anonymous session.

    This is the extension point for authenticated crawling: callers can retry
    with a Playwright ``storage_state`` (logged-in cookies) once one is available.
    """
