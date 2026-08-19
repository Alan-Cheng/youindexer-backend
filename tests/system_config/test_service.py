import json
from types import SimpleNamespace
from unittest.mock import Mock

from redis.exceptions import ConnectionError

from app.database.models import SystemConfig
from app.system_config.service import (
    DEFAULT_SUBTITLE_LANGUAGES,
    SystemConfigService,
    get_default_subtitle_languages,
)


def test_get_returns_cached_value_without_querying_database() -> None:
    session = Mock()
    redis_client = Mock()
    redis_client.get.return_value = b"3"

    result = SystemConfigService(session, redis_client).get("RESULT_LIMIT")

    assert result == 3
    session.get.assert_not_called()


def test_get_reads_database_and_populates_cache_on_miss() -> None:
    session = Mock()
    session.get.return_value = SimpleNamespace(value={"limit": 3})
    redis_client = Mock()
    redis_client.get.return_value = None

    result = SystemConfigService(
        session, redis_client, cache_ttl_seconds=60
    ).get("RESULT_LIMIT")

    assert result == {"limit": 3}
    session.get.assert_called_once_with(SystemConfig, "RESULT_LIMIT")
    redis_client.setex.assert_called_once_with(
        "system_config:RESULT_LIMIT",
        60,
        json.dumps({"limit": 3}, ensure_ascii=False),
    )


def test_get_falls_back_to_database_when_redis_is_unavailable() -> None:
    session = Mock()
    session.get.return_value = SimpleNamespace(value=True)
    redis_client = Mock()
    redis_client.get.side_effect = ConnectionError("redis unavailable")

    result = SystemConfigService(session, redis_client).get("FEATURE_ENABLED")

    assert result is True
    session.get.assert_called_once_with(SystemConfig, "FEATURE_ENABLED")


def test_get_returns_default_when_config_does_not_exist() -> None:
    session = Mock()
    session.get.return_value = None
    redis_client = Mock()
    redis_client.get.return_value = None

    result = SystemConfigService(session, redis_client).get("UNKNOWN", default=10)

    assert result == 10


def test_default_subtitle_languages_are_read_from_system_config(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.system_config.service.get_system_config",
        lambda key, default: ["en", "zh-TW", "en"],
    )

    assert get_default_subtitle_languages() == ("en", "zh-TW")


def test_default_subtitle_languages_fall_back_for_invalid_value(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.system_config.service.get_system_config",
        lambda key, default: ["ja"],
    )

    assert get_default_subtitle_languages() == DEFAULT_SUBTITLE_LANGUAGES
