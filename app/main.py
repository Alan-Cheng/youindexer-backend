from fastapi import FastAPI

from app.api.v1.health import router as health_router
from app.api.v1.youtube import router as youtube_router

app = FastAPI(
    title="YouIndexer API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.include_router(health_router, prefix="/api/v1", tags=["health"])
app.include_router(youtube_router, prefix="/api/v1", tags=["youtube"])
