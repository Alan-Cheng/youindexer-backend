"""Detect which platform a URL belongs to, so ingestion can route to the right handler."""

from __future__ import annotations

from urllib.parse import urlparse

YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}
INSTAGRAM_HOSTS = {"instagram.com", "www.instagram.com"}
THREADS_HOSTS = {"threads.net", "www.threads.net", "threads.com", "www.threads.com"}

SOURCE_YOUTUBE = "youtube"
SOURCE_INSTAGRAM = "instagram"
SOURCE_THREADS = "threads"

_HOSTS_BY_SOURCE = {
    SOURCE_YOUTUBE: YOUTUBE_HOSTS,
    SOURCE_INSTAGRAM: INSTAGRAM_HOSTS,
    SOURCE_THREADS: THREADS_HOSTS,
}


class UnknownUrlSourceError(ValueError):
    """Raised when a URL's host does not match any known content source."""


def detect_url_source(url: str) -> str:
    """Return the platform name for a URL's host, or raise if none match."""
    host = (urlparse(url.strip()).hostname or "").lower()
    for source, hosts in _HOSTS_BY_SOURCE.items():
        if host in hosts:
            return source
    raise UnknownUrlSourceError(f"unrecognized content source for url host: {host!r}")
