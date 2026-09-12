"""Google OAuth2 authorization-code flow helpers."""

from __future__ import annotations

from urllib.parse import urlencode

import httpx

from app.auth.exceptions import OAuthExchangeError
from app.config import settings

_GOOGLE_AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
_DEFAULT_SCOPES = ["openid", "email", "profile"]


def build_google_authorization_url(*, redirect_uri: str | None = None, state: str | None = None) -> str:
    """Return the URL to redirect the user for Google consent."""
    redirect_uri = redirect_uri or settings.google_redirect_uri
    if not redirect_uri:
        raise OAuthExchangeError("GOOGLE_REDIRECT_URI is not configured")

    params: dict[str, str] = {
        "client_id": settings.google_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(_DEFAULT_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
    }
    if state:
        params["state"] = state
    return f"{_GOOGLE_AUTHORIZATION_URL}?{urlencode(params)}"


async def exchange_google_code(
    code: str,
    *,
    redirect_uri: str | None = None,
) -> dict[str, object]:
    """Exchange an authorization code for Google userinfo.

    Returns a dict with keys such as ``sub``, ``email``, and ``name``.
    """
    redirect_uri = redirect_uri or settings.google_redirect_uri
    if not redirect_uri:
        raise OAuthExchangeError("GOOGLE_REDIRECT_URI is not configured")
    if not settings.google_client_id or not settings.google_client_secret:
        raise OAuthExchangeError("Google OAuth credentials are not configured")

    token_payload = {
        "code": code,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }

    async with httpx.AsyncClient() as client:
        token_response = await client.post(_GOOGLE_TOKEN_URL, data=token_payload)
        token_response.raise_for_status()
        token_data = token_response.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise OAuthExchangeError("Google did not return an access token")

        userinfo_response = await client.get(
            _GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        userinfo_response.raise_for_status()
        return userinfo_response.json()
