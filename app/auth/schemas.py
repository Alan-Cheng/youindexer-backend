"""Authentication Pydantic schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserResponse(BaseModel):
    id: int
    email: str | None = None
    display_name: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token lifetime in seconds")


class GoogleCallbackRequest(BaseModel):
    code: str = Field(min_length=1, description="Google authorization code")
    redirect_uri: str | None = Field(
        default=None, description="Must match the redirect_uri used for login"
    )


class GoogleLoginUrlResponse(BaseModel):
    authorization_url: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=1)
