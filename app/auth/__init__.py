"""Authentication domain: Google OAuth2 and JWT helpers."""

from app.auth.dependencies import get_current_user, get_optional_user
from app.auth.schemas import TokenResponse, UserResponse
from app.auth.service import create_or_update_user, create_token_pair

__all__ = [
    "TokenResponse",
    "UserResponse",
    "create_or_update_user",
    "create_token_pair",
    "get_current_user",
    "get_optional_user",
]
