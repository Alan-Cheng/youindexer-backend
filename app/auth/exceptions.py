"""Authentication domain exceptions."""


class AuthenticationError(RuntimeError):
    """Base class for authentication failures."""


class OAuthExchangeError(AuthenticationError):
    """Raised when OAuth token exchange or userinfo retrieval fails."""


class InvalidTokenError(AuthenticationError):
    """Raised when a JWT is missing, expired, or malformed."""
