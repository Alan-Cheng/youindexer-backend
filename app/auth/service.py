"""Authentication business logic: user persistence and JWT issuance."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.exceptions import InvalidTokenError
from app.auth.schemas import TokenResponse
from app.config import settings
from app.database.models import User

_ACCESS_TOKEN_TYPE = "access"
_REFRESH_TOKEN_TYPE = "refresh"


def _utcnow() -> datetime:
    return datetime.now(UTC)


def create_or_update_user(
    session: Session,
    *,
    google_subject: str,
    email: str | None,
    display_name: str | None,
) -> User:
    """Create or update a user from Google OAuth claims."""
    user = session.scalar(
        select(User).where(User.google_subject == google_subject)
    )
    if user is None:
        user = User(
            google_subject=google_subject,
            email=email,
            display_name=display_name,
        )
        session.add(user)
        session.flush()
    else:
        if email is not None:
            user.email = email
        if display_name is not None:
            user.display_name = display_name
    session.commit()
    return user


def _encode_token(
    user_id: int,
    token_type: str,
    expires_delta: timedelta,
) -> str:
    now = _utcnow()
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_token_pair(user_id: int) -> TokenResponse:
    """Issue a new access and refresh token pair for a user."""
    access_token = _encode_token(
        user_id,
        _ACCESS_TOKEN_TYPE,
        timedelta(minutes=settings.jwt_access_token_expire_minutes),
    )
    refresh_token = _encode_token(
        user_id,
        _REFRESH_TOKEN_TYPE,
        timedelta(days=settings.jwt_refresh_token_expire_days),
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


def _verify_token(token: str, expected_type: str) -> int:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError as exc:
        raise InvalidTokenError("token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise InvalidTokenError("invalid token") from exc

    token_type = payload.get("type")
    if token_type != expected_type:
        raise InvalidTokenError(f"expected {expected_type} token")

    sub = payload.get("sub")
    if not isinstance(sub, str):
        raise InvalidTokenError("missing subject")
    try:
        return int(sub)
    except ValueError as exc:
        raise InvalidTokenError("invalid subject") from exc


def verify_access_token(token: str) -> int:
    """Return the user_id encoded in an access token."""
    return _verify_token(token, _ACCESS_TOKEN_TYPE)


def verify_refresh_token(token: str) -> int:
    """Return the user_id encoded in a refresh token."""
    return _verify_token(token, _REFRESH_TOKEN_TYPE)
