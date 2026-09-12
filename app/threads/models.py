"""Data model returned by the Threads crawler service."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class ThreadsPost:
    post_id: str
    url: str
    username: str
    caption: str | None
    thumbnail_url: str | None
    published_at: str | None
    like_count: int | None

    def as_dict(self) -> dict[str, str | int | None]:
        return asdict(self)
