"""YouTube search integration."""

from app.youtube.search import YouTubeSearchError, YouTubeSearchResult, search_youtube
from app.youtube.suggestions import YouTubeSuggestionError, get_youtube_suggestions

__all__ = [
    "YouTubeSearchError",
    "YouTubeSearchResult",
    "YouTubeSuggestionError",
    "get_youtube_suggestions",
    "search_youtube",
]
