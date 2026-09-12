"""Authentication API routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import create_or_update_user, create_token_pair
from app.auth.dependencies import get_current_user
from app.auth.exceptions import InvalidTokenError, OAuthExchangeError
from app.auth.oauth import build_google_authorization_url, exchange_google_code
from app.auth.schemas import (
    GoogleCallbackRequest,
    GoogleLoginUrlResponse,
    RefreshTokenRequest,
    TokenResponse,
    UserResponse,
)
from app.auth.service import verify_refresh_token
from app.core.response import APIResponse
from app.database.models import User
from app.database.session import get_session

router = APIRouter()


@router.get("/auth/google/login", response_model=APIResponse[GoogleLoginUrlResponse])
async def google_login(
    redirect_uri: str | None = None,
    state: str | None = None,
) -> APIResponse[GoogleLoginUrlResponse]:
    """Return the Google OAuth2 consent URL.

    The frontend redirects the user to this URL. After consent, Google redirects
    back with a ``code`` query parameter.
    """
    try:
        url = build_google_authorization_url(redirect_uri=redirect_uri, state=state)
    except OAuthExchangeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return APIResponse.ok(GoogleLoginUrlResponse(authorization_url=url))


@router.post("/auth/google/callback", response_model=APIResponse[TokenResponse])
async def google_callback(
    payload: GoogleCallbackRequest,
    session: Annotated[Session, Depends(get_session)],
) -> APIResponse[TokenResponse]:
    """Exchange a Google authorization code for local JWT tokens."""
    try:
        userinfo = await exchange_google_code(
            payload.code, redirect_uri=payload.redirect_uri
        )
    except OAuthExchangeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    subject = userinfo.get("sub")
    if not isinstance(subject, str) or not subject:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Google did not return a valid user subject",
        )

    user = create_or_update_user(
        session,
        google_subject=subject,
        email=userinfo.get("email") if isinstance(userinfo.get("email"), str) else None,
        display_name=userinfo.get("name") if isinstance(userinfo.get("name"), str) else None,
    )
    return APIResponse.ok(create_token_pair(user.id))


@router.post("/auth/refresh", response_model=APIResponse[TokenResponse])
async def refresh_token(
    payload: RefreshTokenRequest,
    session: Annotated[Session, Depends(get_session)],
) -> APIResponse[TokenResponse]:
    """Issue a new access/refresh token pair from a valid refresh token."""
    try:
        user_id = verify_refresh_token(payload.refresh_token)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return APIResponse.ok(create_token_pair(user.id))


@router.get("/me", response_model=APIResponse[UserResponse])
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> APIResponse[UserResponse]:
    """Return the currently authenticated user's profile."""
    return APIResponse.ok(UserResponse.model_validate(current_user))


@router.get("/auth/verify", response_model=APIResponse[UserResponse])
async def verify_current_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> APIResponse[UserResponse]:
    """Debug helper: confirm that the provided Bearer token is valid."""
    return APIResponse.ok(UserResponse.model_validate(current_user))
