"""Shared API response envelope, analogous to a Spring Boot ``ApiResponse<T>``.

Every endpoint should return its payload wrapped in :class:`APIResponse` so API
consumers can rely on one consistent shape for both success and error results,
regardless of which router produced the response.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    success: bool
    code: int
    message: str
    data: T | None = None
    errors: list[str] | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def ok(cls, data: T, *, code: int = 200, message: str = "OK") -> "APIResponse[T]":
        return cls(success=True, code=code, message=message, data=data)

    @classmethod
    def fail(
        cls,
        *,
        code: int,
        message: str,
        errors: list[str] | None = None,
    ) -> "APIResponse[None]":
        return APIResponse[None](
            success=False, code=code, message=message, data=None, errors=errors
        )
