"""Exception handlers that wrap FastAPI's default error bodies in :class:`APIResponse`."""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.response import APIResponse


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    envelope = APIResponse.fail(code=exc.status_code, message=str(exc.detail))
    return JSONResponse(
        status_code=exc.status_code,
        content=envelope.model_dump(mode="json"),
        headers=exc.headers,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = [
        "{}: {}".format(".".join(str(part) for part in error["loc"]), error["msg"])
        for error in exc.errors()
    ]
    envelope = APIResponse.fail(
        code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        message="Request validation failed",
        errors=errors,
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=envelope.model_dump(mode="json"),
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
