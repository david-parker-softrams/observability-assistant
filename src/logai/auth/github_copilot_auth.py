"""GitHub Copilot OAuth authentication using device code flow."""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiohttp

from .token_storage import TokenData, TokenStorage


@dataclass
class DeviceCodeResponse:
    """
    Response from GitHub device code request (RFC 8628).

    Attributes:
        device_code: Device verification code
        user_code: User verification code (shown to user)
        verification_uri: URL where user enters code
        expires_in: Device code expiration in seconds
        interval: Polling interval in seconds
    """

    device_code: str
    user_code: str
    verification_uri: str
    expires_in: int
    interval: int


class GitHubCopilotAuthError(Exception):
    """Base exception for GitHub Copilot authentication errors."""

    pass


class AuthenticationTimeoutError(GitHubCopilotAuthError):
    """Raised when authentication times out."""

    pass


class AuthenticationDeniedError(GitHubCopilotAuthError):
    """Raised when user denies authentication."""

    pass


class GitHubCopilotAuth:
    """
    GitHub Copilot OAuth authentication manager.

    Implements OAuth 2.0 Device Authorization Grant (RFC 8628) for terminal-based
    authentication without requiring a callback URL.

    The device code flow works as follows:
        1. Request device code from GitHub
        2. Display user code and verification URL
        3. User visits URL and enters code
        4. Poll GitHub for access token
        5. Save token securely

    Credentials are stored in:
        - Primary: ~/.local/share/logai/auth.json (with 600 permissions)
        - Override: LOGAI_GITHUB_COPILOT_TOKEN environment variable

    Example:
        ```python
        auth = GitHubCopilotAuth()

        # Check if authenticated
        if not auth.is_authenticated():
            # Authenticate
            await auth.authenticate()

        # Get token for API calls
        token = auth.get_token()
        ```

    Security features:
        - Secure token storage with 600 permissions
        - Token masking in all output
        - Atomic file writes
        - Environment variable override support
    """

    # GitHub OAuth endpoints
    DEVICE_CODE_URL = "https://github.com/login/device/code"
    TOKEN_URL = "https://github.com/login/oauth/access_token"

    # GitHub Copilot OAuth client ID (public, used by VS Code/OpenCode)
    CLIENT_ID = "Iv1.b507a08c87ecfe98"

    # OAuth scopes required for Copilot access
    # GitHub Copilot API requires both scopes:
    # - read:user: Access to user profile information
    # - user:email: Access to user email addresses (required for API authorization)
    SCOPES = "user:email read:user"

    # Default timeout for authentication (15 minutes)
    DEFAULT_TIMEOUT = 900

    def __init__(self, token_storage: TokenStorage | None = None):
        """
        Initialize authentication manager.

        Args:
            token_storage: Token storage instance (for testing). Defaults to new instance.
        """
        self._storage = token_storage or TokenStorage()
        self._http_session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._http_session is None or self._http_session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self._http_session = aiohttp.ClientSession(
                timeout=timeout, headers={"Accept": "application/json"}
            )
        return self._http_session

    async def close(self) -> None:
        """Close HTTP session."""
        if self._http_session and not self._http_session.closed:
            await self._http_session.close()

    async def __aenter__(self) -> GitHubCopilotAuth:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    @property
    def auth_file_path(self) -> Path:
        """Get the authentication file path.

        Returns:
            Path to the auth.json file
        """
        return self._storage.auth_file_path

    def is_authenticated(self) -> bool:
        """
        Check if user is authenticated with valid credentials.

        Returns:
            True if authenticated with valid token
        """
        return self.get_token() is not None

    def get_token(self) -> str | None:
        """
        Get the current access token.

        Priority:
            1. Environment variable LOGAI_GITHUB_COPILOT_TOKEN
            2. File-based token storage

        Returns:
            Access token or None if not authenticated
        """
        # Check environment variable first
        env_token = os.environ.get("LOGAI_GITHUB_COPILOT_TOKEN")
        if env_token:
            # Validate format (GitHub tokens start with 'gh' prefix)
            if env_token.startswith("gh") and len(env_token) > 10:
                return env_token

        # Try loading from file
        token_data = self._storage.load_token()
        if token_data:
            return token_data.token

        return None

    async def authenticate(self, timeout: int = DEFAULT_TIMEOUT) -> str:
        """
        Initiate OAuth device code flow for GitHub Copilot.

        This is the main authentication method that orchestrates the full OAuth flow:
            1. Request device code
            2. Display instructions to user
            3. Poll for token
            4. Save token

        Args:
            timeout: Maximum time to wait for authentication (seconds). Default 15 minutes.

        Returns:
            The access token on successful authentication

        Raises:
            AuthenticationTimeoutError: If authentication times out
            AuthenticationDeniedError: If user denies access
            GitHubCopilotAuthError: For other authentication errors
        """
        try:
            # Step 1: Request device code
            device_response = await self._request_device_code()

            # Step 2: Display user instructions
            self._display_instructions(device_response)

            # Step 3: Poll for token
            token = await self._poll_for_token(
                device_code=device_response.device_code,
                interval=device_response.interval,
                expires_in=min(device_response.expires_in, timeout),
            )

            # Step 4: Save token
            token_data = TokenData(
                token=token,
                created_at=datetime.now(UTC).isoformat(),
                device_code=device_response.device_code,
            )
            self._storage.save_token(token_data)

            print("\n✓ Authentication successful!")
            print(f"Token saved to: {self._storage.auth_file_path}")

            return token

        finally:
            await self.close()

    def logout(self) -> bool:
        """
        Remove stored credentials.

        Note: This only removes file-based credentials. If using environment variable
        (LOGAI_GITHUB_COPILOT_TOKEN), that must be unset separately.

        Returns:
            True if credentials were removed, False if none existed
        """
        return self._storage.delete_token()

    def get_status(self) -> dict[str, Any]:
        """
        Get authentication status information.

        Returns:
            Dictionary with status information including:
                - authenticated: bool
                - source: 'environment' | 'file' | None
                - token_prefix: Masked token (first 7 chars)
                - auth_file: Path to auth file
                - auth_file_exists: bool
        """
        token = self.get_token()
        env_token = os.environ.get("LOGAI_GITHUB_COPILOT_TOKEN")

        return {
            "authenticated": self.is_authenticated(),
            "source": "environment" if env_token else "file" if token else None,
            "token_prefix": self._mask_token(token) if token else None,
            "auth_file": str(self._storage.auth_file_path),
            "auth_file_exists": self._storage.auth_file_path.exists(),
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Private Methods - OAuth Device Code Flow
    # ─────────────────────────────────────────────────────────────────────────

    async def _request_device_code(self) -> DeviceCodeResponse:
        """
        Request a device code from GitHub.

        Returns:
            DeviceCodeResponse with verification details

        Raises:
            GitHubCopilotAuthError: If request fails
        """
        session = await self._get_session()

        try:
            async with session.post(
                self.DEVICE_CODE_URL,
                json={
                    "client_id": self.CLIENT_ID,
                    "scope": self.SCOPES,
                },
                headers={"Content-Type": "application/json"},
            ) as response:
                if response.status != 200:
                    text = await response.text()
                    raise GitHubCopilotAuthError(
                        f"Failed to request device code: {response.status} - {text}"
                    )

                data = await response.json()

                return DeviceCodeResponse(
                    device_code=data["device_code"],
                    user_code=data["user_code"],
                    verification_uri=data["verification_uri"],
                    expires_in=data["expires_in"],
                    interval=data.get("interval", 5),
                )

        except aiohttp.ClientError as e:
            raise GitHubCopilotAuthError(f"Network error requesting device code: {e}") from e
        except KeyError as e:
            raise GitHubCopilotAuthError(f"Invalid response from GitHub: missing {e}") from e

    async def _poll_for_token(
        self,
        device_code: str,
        interval: int,
        expires_in: int,
    ) -> str:
        """
        Poll GitHub for access token.

        Implements the polling logic as specified in RFC 8628:
            - Poll at the specified interval
            - Handle 'slow_down' by increasing interval
            - Handle 'authorization_pending' by continuing
            - Stop on 'expired_token', 'access_denied', or success

        Args:
            device_code: Device code from initial request
            interval: Polling interval in seconds
            expires_in: Device code expiration time in seconds

        Returns:
            Access token on success

        Raises:
            AuthenticationTimeoutError: If device code expires
            AuthenticationDeniedError: If user denies access
            GitHubCopilotAuthError: For other errors
        """
        session = await self._get_session()
        start_time = time.time()
        current_interval = interval

        while (time.time() - start_time) < expires_in:
            # Wait before polling
            await asyncio.sleep(current_interval)

            try:
                async with session.post(
                    self.TOKEN_URL,
                    json={
                        "client_id": self.CLIENT_ID,
                        "device_code": device_code,
                        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    },
                    headers={"Content-Type": "application/json"},
                ) as response:
                    data = await response.json()

                    # Success - got access token
                    if "access_token" in data:
                        access_token: str = data["access_token"]
                        return access_token

                    # Handle errors
                    error = data.get("error")
                    if error == "authorization_pending":
                        # User hasn't authorized yet, keep polling
                        continue
                    elif error == "slow_down":
                        # GitHub asked us to slow down
                        current_interval += 5
                        print(f"\nSlowing down polling interval to {current_interval}s...")
                        continue
                    elif error == "expired_token":
                        raise AuthenticationTimeoutError("Device code expired")
                    elif error == "access_denied":
                        raise AuthenticationDeniedError("User denied access")
                    else:
                        error_desc = data.get("error_description", "Unknown error")
                        raise GitHubCopilotAuthError(
                            f"Authentication error: {error} - {error_desc}"
                        )

            except aiohttp.ClientError as e:
                # Network error - wait and retry
                print(f"\nNetwork error, retrying: {e}")
                await asyncio.sleep(current_interval)
                continue

        # Timeout
        raise AuthenticationTimeoutError(f"Authentication timed out after {expires_in} seconds")

    @staticmethod
    def _display_instructions(response: DeviceCodeResponse) -> None:
        """
        Display authentication instructions to user.

        Args:
            response: Device code response with user code and URL
        """
        print("\n" + "=" * 70)
        print("GitHub Copilot Authentication")
        print("=" * 70)
        print("\n1. Open this URL in your browser:")
        print(f"   {response.verification_uri}")
        print("\n2. Enter this code:")
        print(f"   {response.user_code}")
        print(f"\nWaiting for authentication (expires in {response.expires_in // 60} minutes)...")
        print("Press Ctrl+C to cancel\n")

    @staticmethod
    def _mask_token(token: str | None) -> str | None:
        """
        Mask token for display (show prefix only).

        Args:
            token: Token to mask

        Returns:
            Masked token or None
        """
        if not token:
            return None
        if len(token) <= 10:
            return "***"
        return f"{token[:7]}..."
