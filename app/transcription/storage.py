"""MinIO-backed storage for normalized subtitle documents."""

from __future__ import annotations

import json
from io import BytesIO
from typing import Any

from minio import Minio
from minio.error import MinioException, S3Error
from urllib3.exceptions import HTTPError

from app.config import Settings, settings


class SubtitleStorageError(RuntimeError):
    """Raised when a subtitle object cannot be read or persisted."""


class MinioSubtitleStorage:
    def __init__(self, client: Minio, bucket: str) -> None:
        self.client = client
        self.bucket = bucket

    @classmethod
    def from_settings(cls, config: Settings = settings) -> MinioSubtitleStorage:
        return cls(
            Minio(
                config.minio_endpoint,
                access_key=config.minio_access_key,
                secret_key=config.minio_secret_key,
                secure=config.minio_secure,
            ),
            config.minio_bucket,
        )

    def _ensure_bucket(self) -> None:
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
        except (MinioException, HTTPError) as exc:
            if isinstance(exc, S3Error) and exc.code in {
                "BucketAlreadyExists",
                "BucketAlreadyOwnedByYou",
            }:
                return
            raise SubtitleStorageError(
                f"failed to prepare MinIO bucket {self.bucket}: {exc}"
            ) from exc

    def put_json(self, object_name: str, document: dict[str, Any]) -> None:
        body = json.dumps(
            document,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        self._ensure_bucket()
        try:
            self.client.put_object(
                self.bucket,
                object_name,
                BytesIO(body),
                length=len(body),
                content_type="application/json; charset=utf-8",
            )
        except (MinioException, HTTPError) as exc:
            raise SubtitleStorageError(
                f"failed to store subtitle object {object_name}: {exc}"
            ) from exc

    def get_json(self, object_name: str) -> dict[str, Any]:
        response = None
        try:
            response = self.client.get_object(self.bucket, object_name)
            document = json.loads(response.read().decode("utf-8"))
        except (
            MinioException,
            HTTPError,
            OSError,
            UnicodeError,
            json.JSONDecodeError,
        ) as exc:
            raise SubtitleStorageError(
                f"failed to read subtitle object {object_name}: {exc}"
            ) from exc
        finally:
            if response is not None:
                response.close()
                response.release_conn()
        if not isinstance(document, dict):
            raise SubtitleStorageError(
                f"subtitle object {object_name} must contain a JSON object"
            )
        return document
