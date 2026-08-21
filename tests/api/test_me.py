"""Tests for authenticated /me API routes."""

import asyncio

import httpx
import pytest

from app.auth.service import create_token_pair
from app.database.models import KeywordSearchJob, KeywordSearchJobVideo, User, YouTubeVideo
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

    def delete(self, path: str, *, headers: dict | None = None) -> httpx.Response:
        async def request() -> httpx.Response:
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as client:
                return await client.delete(path, headers=headers)

        return asyncio.run(request())


client = _ASGIClient()


@pytest.fixture(autouse=True)
def _clear_dependency_overrides():
    original_overrides = dict(app.dependency_overrides)
    yield
    app.dependency_overrides = original_overrides


def test_list_search_history_returns_only_user_jobs(db_session) -> None:
    user = User(
        google_subject="history-subject",
        email="history@example.com",
        display_name="History User",
    )
    other_user = User(
        google_subject="other-subject",
        email="other@example.com",
        display_name="Other User",
    )
    db_session.add_all([user, other_user])
    db_session.flush()

    video = YouTubeVideo(
        youtube_video_id="history-video",
        canonical_url="https://www.youtube.com/watch?v=history-video",
        title="History Video",
    )
    db_session.add(video)
    db_session.flush()

    user_job = KeywordSearchJob(
        user_id=user.id,
        query="user query",
        locale="zh-TW",
        requested_count=1,
        matches_per_video=5,
        status="processing",
    )
    other_job = KeywordSearchJob(
        user_id=other_user.id,
        query="other query",
        locale="zh-TW",
        requested_count=1,
        matches_per_video=5,
        status="processing",
    )
    db_session.add_all([user_job, other_job])
    db_session.flush()

    db_session.add(
        KeywordSearchJobVideo(
            job_id=user_job.id,
            video_id=video.id,
            position=0,
            status="loading",
            keyword_matches=[],
        )
    )
    db_session.commit()

    tokens = create_token_pair(user.id)
    app.dependency_overrides[get_session] = lambda: db_session

    response = client.get(
        "/api/v1/me/search-history",
        headers={"Authorization": f"Bearer {tokens.access_token}"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["task_id"] == user_job.id
    assert data["items"][0]["query"] == "user query"
    assert data["items"][0]["video_count"] == 1


def test_list_search_history_requires_authentication() -> None:
    response = client.get("/api/v1/me/search-history")
    assert response.status_code == 401


def test_delete_search_history_item_is_scoped_to_current_user(db_session) -> None:
    user = User(
        google_subject="delete-history-subject",
        email="delete-history@example.com",
        display_name="Delete History User",
    )
    other_user = User(
        google_subject="delete-other-subject",
        email="delete-other@example.com",
        display_name="Other User",
    )
    db_session.add_all([user, other_user])
    db_session.flush()

    user_job = KeywordSearchJob(
        user_id=user.id,
        query="delete me",
        locale="zh-TW",
        requested_count=1,
        matches_per_video=5,
        status="completed",
    )
    other_job = KeywordSearchJob(
        user_id=other_user.id,
        query="do not delete",
        locale="zh-TW",
        requested_count=1,
        matches_per_video=5,
        status="completed",
    )
    db_session.add_all([user_job, other_job])
    db_session.commit()

    tokens = create_token_pair(user.id)
    app.dependency_overrides[get_session] = lambda: db_session
    headers = {"Authorization": f"Bearer {tokens.access_token}"}

    response = client.delete(f"/api/v1/me/search-history/{user_job.id}", headers=headers)
    other_response = client.delete(
        f"/api/v1/me/search-history/{other_job.id}", headers=headers
    )

    assert response.status_code == 204
    assert other_response.status_code == 404
    assert db_session.get(KeywordSearchJob, user_job.id) is None
    assert db_session.get(KeywordSearchJob, other_job.id) is not None
