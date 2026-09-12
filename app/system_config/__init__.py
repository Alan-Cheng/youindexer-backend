"""Access to runtime-adjustable system configuration."""

from app.system_config.service import (
    SystemConfigService,
    get_default_subtitle_languages,
    get_system_config,
)

__all__ = [
    "SystemConfigService",
    "get_default_subtitle_languages",
    "get_system_config",
]
