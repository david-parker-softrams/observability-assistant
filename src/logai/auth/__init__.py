"""Authentication module for LogAI."""

from .github_copilot_auth import (
    AuthenticationDeniedError,
    AuthenticationTimeoutError,
    DeviceCodeResponse,
    GitHubCopilotAuth,
    GitHubCopilotAuthError,
)
from .token_storage import TokenData, TokenStorage

__all__ = [
    # GitHub Copilot Auth
    "GitHubCopilotAuth",
    "DeviceCodeResponse",
    "GitHubCopilotAuthError",
    "AuthenticationTimeoutError",
    "AuthenticationDeniedError",
    # Token Storage
    "TokenStorage",
    "TokenData",
    # Utility Functions
    "get_github_copilot_token",
]


def get_github_copilot_token() -> str | None:
    """
    Get GitHub Copilot token for use in providers.

    This is a convenience function for integrating GitHub Copilot authentication
    into other parts of the codebase without directly managing auth instances.

    Returns:
        GitHub Copilot access token if authenticated, None otherwise

    Example:
        ```python
        from logai.auth import get_github_copilot_token

        token = get_github_copilot_token()
        if token:
            # Use token for API calls
            headers = {"Authorization": f"Bearer {token}"}
        else:
            # Not authenticated
            print("Run 'logai auth login' to authenticate")
        ```
    """
    auth = GitHubCopilotAuth()
    return auth.get_token()
