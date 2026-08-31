"""YouTube search integration."""

from app.youtube.search import YouTubeSearchError, YouTubeSearchResult, search_youtube
from app.youtube.suggestions import YouTubeSuggestionError, get_youtube_suggestions
from app.youtube.video_lookup import (
    YouTubeVideoLookupError,
    fetch_youtube_video_metadata,
    parse_youtube_video_id,
)

__all__ = [
    "YouTubeSearchError",
    "YouTubeSearchResult",
    "YouTubeSuggestionError",
    "YouTubeVideoLookupError",
    "fetch_youtube_video_metadata",
    "get_youtube_suggestions",
    "parse_youtube_video_id",
    "search_youtube",
]
