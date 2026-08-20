"""Tests for authentication API endpoints."""

import asyncio

import httpx
import pytest
from sqlalchemy import select

from app.auth.service import create_token_pair
from app.config import settings
from app.database.models import User
from app.database.session import get_session
from app.main import app


class _ASGIClient:
    """Synchronous facade avoiding Starlette TestClient's Python 3.14 deadlock."""

    def get(self, path: str, *, headers: dict | None = None) -> httpx.Response:
        async def request() -> httpx.Response:
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as client:
                return await client.get(path, headers=headers)

        return asyncio.run(request())

    def post(
        self, path: str, *, json: dict | None = None, headers: dict | None = None
    ) -> httpx.Response:
        async def request() -> httpx.Response:
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as client:
                return await client.post(path, json=json, headers=headers)

        return asyncio.run(request())


client = _ASGIClient()


@pytest.fixture(autouse=True)
def _clear_dependency_overrides():
    original_overrides = dict(app.dependency_overrides)
    yield
    app.dependency_overrides = original_overrides


def test_google_login_returns_authorization_url(monkeypatch) -> None:
    monkeypatch.setattr(settings, "google_client_id", "test-client-id")
    monkeypatch.setattr(
        settings, "google_redirect_uri", "http://localhost/callback"
    )

    response = client.get("/api/v1/auth/google/login")

    assert response.status_code == 200
    data = response.json()
    assert "accounts.google.com" in data["authorization_url"]
    assert "client_id=test-client-id" in data["authorization_url"]


def test_google_callback_exchanges_code_for_tokens(
    monkeypatch, db_session
) -> None:
    async def fake_exchange(code: str, *, redirect_uri: str | None = None):
        return {
            "sub": "google-test-subject",
            "email": "test@example.com",
            "name": "Test User",
        }

    monkeypatch.setattr(
        "app.api.v1.auth.exchange_google_code", fake_exchange
    )

    app.dependency_overrides[get_session] = lambda: db_session

    response = client.post(
        "/api/v1/auth/google/callback",
        json={"code": "test-code"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert "access_token" in data
    assert "refresh_token" in data

    user = db_session.scalar(
        select(User).where(User.google_subject == "google-test-subject")
    )
    assert user is not None
    assert user.email == "test@example.com"


def test_refresh_issues_new_tokens(monkeypatch, db_session) -> None:
    user = User(
        google_subject="refresh-subject",
        email="refresh@example.com",
        display_name="Refresh User",
    )
    db_session.add(user)
    db_session.commit()
    tokens = create_token_pair(user.id)

    app.dependency_overrides[get_session] = lambda: db_session

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens.refresh_token},
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


def test_me_returns_current_user(db_session) -> None:
    user = User(
        google_subject="me-subject",
        email="me@example.com",
        display_name="Me User",
    )
    db_session.add(user)
    db_session.commit()
    tokens = create_token_pair(user.id)

    app.dependency_overrides[get_session] = lambda: db_session

    response = client.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {tokens.access_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == user.id
    assert data["email"] == "me@example.com"
    assert data["display_name"] == "Me User"


def test_me_rejects_missing_token() -> None:
    response = client.get("/api/v1/me")
    assert response.status_code == 401
