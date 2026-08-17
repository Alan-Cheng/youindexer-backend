import os

from dotenv import load_dotenv
from pydantic import BaseModel

# Docker Compose reads .env for service interpolation, but local Python commands do
# not. Load it here so FastAPI, Celery, and Alembic share the same local settings.
# Existing process environment variables still take precedence.
load_dotenv()


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Settings(BaseModel):
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://youindexer:youindexer@localhost:5433/youindexer",
    )
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    celery_result_backend: str = os.getenv(
        "CELERY_RESULT_BACKEND", "redis://localhost:6379/1"
    )
    minio_endpoint: str = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    minio_access_key: str = os.getenv("MINIO_ROOT_USER", "minioadmin")
    minio_secret_key: str = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
    minio_secure: bool = _env_bool("MINIO_SECURE")
    minio_bucket: str = os.getenv("MINIO_BUCKET", "youindexer")
    youtube_cookies_file: str | None = os.getenv("YOUTUBE_COOKIES_FILE")
    opensearch_url: str = os.getenv("OPENSEARCH_URL", "http://localhost:9200")
    opensearch_subtitle_index: str = os.getenv(
        "OPENSEARCH_SUBTITLE_INDEX", "subtitle-segments-v1"
    )
    opensearch_subtitle_alias: str = os.getenv(
        "OPENSEARCH_SUBTITLE_ALIAS", "subtitle-segments"
    )


settings = Settings()
