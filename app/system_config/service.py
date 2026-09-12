"""Redis-backed access to system configuration stored in PostgreSQL."""

import json
from typing import Any

from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy.orm import Session

from app.config import settings
from app.database.models import SystemConfig
from app.database.session import SessionLocal

CACHE_KEY_PREFIX = "system_config:"
CACHE_TTL_SECONDS = 3600
DEFAULT_SUBTITLE_LANGUAGES_KEY = "DEFAULT_SUBTITLE_LANGUAGES"
DEFAULT_SUBTITLE_LANGUAGES = ("zh-TW",)


class SystemConfigService:
    def __init__(
        self,
        session: Session,
        redis_client: Redis,
        *,
        cache_ttl_seconds: int = CACHE_TTL_SECONDS,
    ) -> None:
        self._session = session
        self._redis = redis_client
        self._cache_ttl_seconds = cache_ttl_seconds

    def get(self, key: str, default: Any = None) -> Any:
        """Return a config value from Redis, falling back to PostgreSQL."""
        cache_key = f"{CACHE_KEY_PREFIX}{key}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        config = self._session.get(SystemConfig, key)
        if config is None:
            return default

        self._cache(cache_key, config.value)
        return config.value

    def _get_cached(self, cache_key: str) -> Any | None:
        try:
            cached = self._redis.get(cache_key)
        except RedisError:
            return None

        if cached is None:
            return None
        try:
            return json.loads(cached)
        except (json.JSONDecodeError, TypeError, UnicodeDecodeError):
            return None

    def _cache(self, cache_key: str, value: Any) -> None:
        try:
            self._redis.setex(
                cache_key,
                self._cache_ttl_seconds,
                json.dumps(value, ensure_ascii=False),
            )
        except RedisError:
            pass


def get_system_config(key: str, default: Any = None) -> Any:
    """Read a system config using application-managed DB and Redis connections."""
    redis_client = Redis.from_url(settings.redis_url)
    try:
        with SessionLocal() as session:
            return SystemConfigService(session, redis_client).get(key, default)
    finally:
        redis_client.close()


def get_default_subtitle_languages() -> tuple[str, ...]:
    """Return validated subtitle languages used for retrieval and search."""
    from app.transcription.youtube import SUPPORTED_LANGUAGES

    value = get_system_config(
        DEFAULT_SUBTITLE_LANGUAGES_KEY, list(DEFAULT_SUBTITLE_LANGUAGES)
    )
    if not isinstance(value, list):
        return DEFAULT_SUBTITLE_LANGUAGES

    languages = tuple(
        dict.fromkeys(
            language
            for language in value
            if isinstance(language, str) and language in SUPPORTED_LANGUAGES
        )
    )
    return languages or DEFAULT_SUBTITLE_LANGUAGES
