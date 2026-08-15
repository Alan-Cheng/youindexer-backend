import asyncio
from typing import Literal

import psycopg
import redis.asyncio as redis
from fastapi import APIRouter, Response, status
from pydantic import BaseModel

from app.config import settings

router = APIRouter()


class ServiceHealth(BaseModel):
    status: Literal["up", "down"]
    detail: str | None = None


class HealthResponse(BaseModel):
    status: Literal["healthy", "unhealthy"]
    postgres: ServiceHealth
    redis: ServiceHealth


async def check_postgres() -> ServiceHealth:
    def ping() -> None:
        with psycopg.connect(settings.database_url, connect_timeout=3) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()

    try:
        await asyncio.to_thread(ping)
        return ServiceHealth(status="up")
    except Exception as exc:
        return ServiceHealth(status="down", detail=type(exc).__name__)


async def check_redis() -> ServiceHealth:
    client = redis.from_url(settings.redis_url, socket_connect_timeout=3)
    try:
        await client.ping()
        return ServiceHealth(status="up")
    except Exception as exc:
        return ServiceHealth(status="down", detail=type(exc).__name__)
    finally:
        await client.aclose()


@router.get("/health", response_model=HealthResponse)
async def health(response: Response) -> HealthResponse:
    postgres_health, redis_health = await asyncio.gather(
        check_postgres(),
        check_redis(),
    )
    is_healthy = postgres_health.status == "up" and redis_health.status == "up"
    if not is_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status="healthy" if is_healthy else "unhealthy",
        postgres=postgres_health,
        redis=redis_health,
    )
