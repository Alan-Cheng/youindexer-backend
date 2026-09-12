"""Data model returned by the Instagram crawler service."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class InstagramPost:
    post_id: str
    url: str
    username: str
    caption: str | None
    accessibility_caption: str | None
    thumbnail_url: str | None
    is_video: bool

    def as_dict(self) -> dict[str, str | bool | None]:
        return asdict(self)
