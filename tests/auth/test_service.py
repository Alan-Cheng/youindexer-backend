"""Tests for authentication service helpers."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.exceptions import InvalidTokenError
from app.auth.service import (
    create_or_update_user,
    create_token_pair,
    verify_access_token,
    verify_refresh_token,
)
from app.config import settings
from app.database.models import User


class TestCreateOrUpdateUser:
    def test_creates_user_when_subject_does_not_exist(
        self, db_session: Session
    ) -> None:
        user = create_or_update_user(
            db_session,
            google_subject="new-subject",
            email="new@example.com",
            display_name="New User",
        )

        assert user.id is not None
        assert user.google_subject == "new-subject"
        assert user.email == "new@example.com"
        assert user.display_name == "New User"
        assert db_session.scalar(
            select(User).where(User.google_subject == "new-subject")
        ) == user

    def test_updates_existing_user(self, db_session: Session) -> None:
        existing = User(
            google_subject="existing-subject",
            email="old@example.com",
            display_name="Old Name",
        )
        db_session.add(existing)
        db_session.commit()

        user = create_or_update_user(
            db_session,
            google_subject="existing-subject",
            email="new@example.com",
            display_name="New Name",
        )

        assert user.id == existing.id
        assert user.email == "new@example.com"
        assert user.display_name == "New Name"


class TestTokenPair:
    def test_verify_access_token_returns_user_id(self) -> None:
        tokens = create_token_pair(user_id=42)
        assert verify_access_token(tokens.access_token) == 42

    def test_verify_refresh_token_returns_user_id(self) -> None:
        tokens = create_token_pair(user_id=42)
        assert verify_refresh_token(tokens.refresh_token) == 42

    def test_access_token_rejects_refresh_token(self) -> None:
        tokens = create_token_pair(user_id=42)
        with pytest.raises(InvalidTokenError):
            verify_access_token(tokens.refresh_token)

    def test_refresh_token_rejects_access_token(self) -> None:
        tokens = create_token_pair(user_id=42)
        with pytest.raises(InvalidTokenError):
            verify_refresh_token(tokens.access_token)

    def test_expired_access_token_is_rejected(self) -> None:
        now = datetime.now(UTC)
        expired_token = jwt.encode(
            {
                "sub": "42",
                "type": "access",
                "iat": now - timedelta(hours=2),
                "exp": now - timedelta(hours=1),
            },
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )
        with pytest.raises(InvalidTokenError):
            verify_access_token(expired_token)

    def test_invalid_signature_is_rejected(self) -> None:
        tokens = create_token_pair(user_id=42)
        tampered = tokens.access_token[:-5] + "XXXXX"
        with pytest.raises(InvalidTokenError):
            verify_access_token(tampered)
