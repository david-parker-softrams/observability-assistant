"""Secure token storage for authentication credentials."""

from __future__ import annotations

import json
import os
import stat
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class TokenData:
    """
    Authentication token data.

    Attributes:
        token: The access token (GitHub tokens start with 'gh' prefix: gho_, ghu_, ghp_)
        created_at: ISO 8601 timestamp of when the token was created
        device_code: Optional device code from OAuth flow (for debugging)
    """

    token: str
    created_at: str
    device_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TokenData:
        """Create TokenData from dictionary."""
        return cls(
            token=data["token"],
            created_at=data["created_at"],
            device_code=data.get("device_code"),
        )

    def is_valid_format(self) -> bool:
        """
        Validate token format.

        GitHub tokens should start with 'gh' prefix:
        - 'gho_' for OAuth tokens
        - 'ghu_' for user tokens
        - 'ghp_' for personal access tokens

        Returns:
            True if token format is valid
        """
        return self.token.startswith("gh") and len(self.token) > 10


class TokenStorage:
    """
    Secure storage for authentication tokens.

    Stores tokens in a JSON file with secure permissions (600 - owner read/write only).
    Uses atomic writes (temp file + rename) to prevent partial credential writes.

    Storage location follows XDG Base Directory specification:
        ~/.local/share/logai/auth.json

    File format:
        {
            "github_copilot": {
                "token": "gho_...",
                "created_at": "2026-02-11T10:30:00Z",
                "device_code": "..."
            }
        }

    Example:
        ```python
        storage = TokenStorage()

        # Save token
        token_data = TokenData(
            token="gho_abc123...",
            created_at=datetime.now(timezone.utc).isoformat()
        )
        storage.save_token(token_data)

        # Load token
        if storage.token_exists():
            token_data = storage.load_token()
            print(f"Token: {token_data.token[:10]}...")

        # Delete token
        storage.delete_token()
        ```

    Security features:
        - File permissions: 600 (owner read/write only)
        - Directory permissions: 700 (owner access only)
        - Atomic writes: Temp file + rename
        - Token validation: Checks for 'gh' prefix (gho_, ghu_, ghp_)
        - Token masking: Masks tokens in error messages
    """

    def __init__(self, auth_file_path: Path | None = None):
        """
        Initialize token storage.

        Args:
            auth_file_path: Override path for auth file (mainly for testing).
                           Defaults to ~/.local/share/logai/auth.json
        """
        if auth_file_path:
            self._auth_file = auth_file_path
        else:
            # XDG Base Directory compliant
            xdg_data_home = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))
            self._auth_file = Path(xdg_data_home) / "logai" / "auth.json"

    @property
    def auth_file_path(self) -> Path:
        """Get the auth file path."""
        return self._auth_file

    def save_token(self, token_data: TokenData) -> None:
        """
        Save token securely with atomic write.

        Args:
            token_data: Token data to save

        Raises:
            ValueError: If token format is invalid
            OSError: If file operations fail
        """
        # Validate token format
        if not token_data.is_valid_format():
            raise ValueError(
                f"Invalid token format. Expected GitHub token starting with 'gh' prefix, "
                f"got: {self._mask_token(token_data.token)}"
            )

        # Ensure directory exists with secure permissions
        self._auth_file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

        # Load existing auth data for other providers (if any)
        auth_data = self._load_auth_file()

        # Update with new GitHub Copilot token
        auth_data["github_copilot"] = token_data.to_dict()

        # Write atomically
        self._write_auth_file_atomic(auth_data)

    def load_token(self) -> TokenData | None:
        """
        Load token from storage.

        Returns:
            TokenData if token exists, None otherwise

        Raises:
            ValueError: If token data is corrupted or invalid
            OSError: If file operations fail
        """
        if not self._auth_file.exists():
            return None

        try:
            auth_data = self._load_auth_file()

            if "github_copilot" not in auth_data:
                return None

            token_data = TokenData.from_dict(auth_data["github_copilot"])

            # Validate token format
            if not token_data.is_valid_format():
                raise ValueError(
                    f"Stored token has invalid format: {self._mask_token(token_data.token)}"
                )

            return token_data

        except json.JSONDecodeError as e:
            raise ValueError(f"Corrupted auth file: {e}") from e
        except KeyError as e:
            raise ValueError(f"Missing required field in token data: {e}") from e

    def delete_token(self) -> bool:
        """
        Delete stored token.

        If other providers have tokens, only removes GitHub Copilot token.
        If this is the only token, removes the entire file.

        Returns:
            True if token was deleted, False if no token existed

        Raises:
            OSError: If file operations fail
        """
        if not self._auth_file.exists():
            return False

        auth_data = self._load_auth_file()

        if "github_copilot" not in auth_data:
            return False

        # Remove GitHub Copilot credentials
        del auth_data["github_copilot"]

        if auth_data:
            # Other providers exist, keep file
            self._write_auth_file_atomic(auth_data)
        else:
            # No other providers, remove file
            self._auth_file.unlink()

        return True

    def token_exists(self) -> bool:
        """
        Check if a token exists in storage.

        Returns:
            True if token exists and is valid format
        """
        try:
            token_data = self.load_token()
            return token_data is not None and token_data.is_valid_format()
        except Exception:
            return False

    def _load_auth_file(self) -> dict[str, Any]:
        """
        Load auth file or return empty dict.

        Returns:
            Auth data dictionary

        Raises:
            json.JSONDecodeError: If file is corrupted
            OSError: If file read fails
        """
        if not self._auth_file.exists():
            return {}

        with open(self._auth_file) as f:
            data: dict[str, Any] = json.load(f)
            return data

    def _write_auth_file_atomic(self, auth_data: dict[str, Any]) -> None:
        """
        Write auth file atomically with secure permissions.

        Uses temp file + rename pattern to ensure atomic writes.
        Sets file permissions to 600 (owner read/write only).

        Args:
            auth_data: Complete auth data to write

        Raises:
            OSError: If file operations fail
        """
        # Write to temp file first
        temp_file = self._auth_file.with_suffix(".tmp")

        try:
            # Write data
            with open(temp_file, "w") as f:
                json.dump(auth_data, f, indent=2)

            # Set secure permissions (600 = owner read/write only)
            os.chmod(temp_file, stat.S_IRUSR | stat.S_IWUSR)

            # Atomic rename
            temp_file.replace(self._auth_file)

        except Exception:
            # Clean up temp file on error
            if temp_file.exists():
                temp_file.unlink()
            raise

    @staticmethod
    def _mask_token(token: str) -> str:
        """
        Mask token for display in logs/errors.

        Shows only the first 7 characters (e.g., 'gho_abc...').

        Args:
            token: Token to mask

        Returns:
            Masked token string
        """
        if len(token) <= 10:
            return "***"
        return f"{token[:7]}..."
