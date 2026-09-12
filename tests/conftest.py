"""Shared pytest fixtures."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import settings
from app.database.models import User
from app.database.session import _sqlalchemy_url


@pytest.fixture(scope="session")
def engine():
    """SQLAlchemy engine connected to the configured database."""
    return create_engine(_sqlalchemy_url(settings.database_url), pool_pre_ping=True)


@pytest.fixture
def db_session(engine) -> Generator[Session]:
    """Yield a database session that rolls back all changes after the test."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    session.begin_nested()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def make_user(db_session: Session) -> Generator[Callable[..., User], None, None]:
    """Factory fixture that creates a unique test user and rolls it back."""
    created: list[User] = []

    def factory(**kwargs) -> User:
        suffix = uuid.uuid4().hex[:12]
        user = User(
            email=kwargs.get("email", f"test-{suffix}@example.com"),
            display_name=kwargs.get("display_name", "Test User"),
            google_subject=kwargs.get("google_subject", f"google-subject-{suffix}"),
        )
        db_session.add(user)
        db_session.commit()
        created.append(user)
        return user

    yield factory
