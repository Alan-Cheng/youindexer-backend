import logging

from fastapi import FastAPI, Request

from app.api.v1.alias import router as alias_router
from app.api.v1.auth import router as auth_router
from app.api.v1.health import router as health_router
from app.api.v1.me import router as me_router
from app.api.v1.youtube import router as youtube_router

app = FastAPI(
    title="YouIndexer API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

logger = logging.getLogger(__name__)


@app.middleware("http")
async def log_request_auth_state(request: Request, call_next):
    """Log request auth presence without exposing the token itself."""
    authorization = request.headers.get("authorization")
    has_token = bool(authorization)
    scheme = authorization.split(" ", 1)[0] if authorization else None
    logger.info(
        "request method=%s path=%s auth_present=%s auth_scheme=%s",
        request.method,
        request.url.path,
        has_token,
        scheme,
    )
    response = await call_next(request)
    logger.info(
        "response method=%s path=%s status=%s auth_present=%s",
        request.method,
        request.url.path,
        response.status_code,
        has_token,
    )
    return response

app.include_router(alias_router, prefix="/api/v1", tags=["alias"])
app.include_router(auth_router, prefix="/api/v1", tags=["auth"])
app.include_router(health_router, prefix="/api/v1", tags=["health"])
app.include_router(me_router, prefix="/api/v1", tags=["me"])
app.include_router(youtube_router, prefix="/api/v1", tags=["youtube"])
