"""Error types for the Threads crawler service."""

from __future__ import annotations


class ThreadsCrawlError(RuntimeError):
    """Raised when Threads cannot be crawled or returns no usable page."""


class ThreadsLoginRequiredError(ThreadsCrawlError):
    """Raised when Threads served no public post data for an anonymous session.

    This is the extension point for authenticated crawling: callers can retry
    with a Playwright ``storage_state`` (logged-in cookies) once one is available.
    """
