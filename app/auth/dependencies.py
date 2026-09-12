"""FastAPI dependencies for resolving the current user."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.exceptions import InvalidTokenError
from app.auth.service import verify_access_token
from app.database.models import User
from app.database.session import get_session

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)


def _extract_token(credentials: HTTPAuthorizationCredentials | None) -> str | None:
    if credentials is None:
        return None
    scheme = credentials.scheme.lower()
    if scheme != "bearer":
        return None
    return credentials.credentials


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    session: Annotated[Session, Depends(get_session)],
) -> User:
    """Require a valid access token and return the authenticated user."""
    token = _extract_token(credentials)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        user_id = verify_access_token(token)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = session.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    logger.info("required auth result=authenticated user_id=%s", user.id)
    return user


def get_optional_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    session: Annotated[Session, Depends(get_session)],
) -> User | None:
    """Return the authenticated user, or None for anonymous requests."""
    authorization = request.headers.get("authorization")
    if not authorization:
        logger.info("optional auth result=anonymous reason=no_authorization_header")
        return None

    token = _extract_token(credentials)
    if token is None:
        logger.warning("optional auth rejected authorization header with invalid scheme")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must use Bearer scheme",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        user_id = verify_access_token(token)
    except InvalidTokenError as exc:
        logger.warning(
            "optional auth rejected invalid token: %s",
            exc,
            extra={"token_preview": token[:20] + "..." if len(token) > 20 else token},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    user = session.scalar(select(User).where(User.id == user_id))
    if user is None:
        logger.warning("optional auth token valid but user not found user_id=%s", user_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    logger.info("optional auth result=authenticated user_id=%s", user.id)
    return user
