"""Comprehensive unit tests for GitHubCopilotAuth class."""

import asyncio
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from logai.auth import (
    AuthenticationDeniedError,
    AuthenticationTimeoutError,
    DeviceCodeResponse,
    GitHubCopilotAuth,
    GitHubCopilotAuthError,
    TokenData,
    TokenStorage,
)


class TestDeviceCodeResponse:
    """Test suite for DeviceCodeResponse dataclass."""

    def test_device_code_response_creation(self) -> None:
        """Test DeviceCodeResponse can be created with all fields."""
        response = DeviceCodeResponse(
            device_code="test_device_code_123",
            user_code="ABCD-1234",
            verification_uri="https://github.com/login/device",
            expires_in=900,
            interval=5,
        )
        
        assert response.device_code == "test_device_code_123"
        assert response.user_code == "ABCD-1234"
        assert response.verification_uri == "https://github.com/login/device"
        assert response.expires_in == 900
        assert response.interval == 5


class TestGitHubCopilotAuthInit:
    """Test suite for GitHubCopilotAuth initialization."""

    def test_init_without_storage(self) -> None:
        """Test GitHubCopilotAuth can be initialized without storage."""
        auth = GitHubCopilotAuth()
        
        assert auth is not None
        assert auth._storage is not None
        assert isinstance(auth._storage, TokenStorage)

    def test_init_with_custom_storage(self, tmp_path: Path) -> None:
        """Test GitHubCopilotAuth can be initialized with custom storage."""
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        
        auth = GitHubCopilotAuth(token_storage=storage)
        
        assert auth._storage is storage

    def test_init_http_session_is_none(self) -> None:
        """Test that HTTP session is not created until needed."""
        auth = GitHubCopilotAuth()
        
        assert auth._http_session is None


class TestGitHubCopilotAuthSession:
    """Test suite for HTTP session management."""

    @pytest.mark.asyncio
    async def test_get_session_creates_session(self) -> None:
        """Test _get_session creates HTTP session."""
        auth = GitHubCopilotAuth()
        
        session = await auth._get_session()
        
        assert session is not None
        assert isinstance(session, aiohttp.ClientSession)
        
        await auth.close()

    @pytest.mark.asyncio
    async def test_get_session_reuses_existing_session(self) -> None:
        """Test _get_session reuses existing session."""
        auth = GitHubCopilotAuth()
        
        session1 = await auth._get_session()
        session2 = await auth._get_session()
        
        assert session1 is session2
        
        await auth.close()

    @pytest.mark.asyncio
    async def test_get_session_creates_new_if_closed(self) -> None:
        """Test _get_session creates new session if previous was closed."""
        auth = GitHubCopilotAuth()
        
        session1 = await auth._get_session()
        await auth.close()
        
        session2 = await auth._get_session()
        
        assert session1 is not session2
        
        await auth.close()

    @pytest.mark.asyncio
    async def test_close_closes_session(self) -> None:
        """Test close() closes HTTP session."""
        auth = GitHubCopilotAuth()
        
        session = await auth._get_session()
        assert not session.closed
        
        await auth.close()
        assert session.closed

    @pytest.mark.asyncio
    async def test_close_when_no_session(self) -> None:
        """Test close() handles case when no session exists."""
        auth = GitHubCopilotAuth()
        
        # Should not raise error
        await auth.close()

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        """Test async context manager protocol."""
        async with GitHubCopilotAuth() as auth:
            assert auth is not None
            session = await auth._get_session()
            assert not session.closed
        
        # Session should be closed after exiting context
        assert session.closed


class TestGitHubCopilotAuthIsAuthenticated:
    """Test suite for is_authenticated method."""

    def test_is_authenticated_true_with_file_token(self, tmp_path: Path) -> None:
        """Test is_authenticated returns True when token exists in file."""
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        
        # Save token
        token_data = TokenData(
            token="gho_test123456789012345",
            created_at="2026-02-11T10:00:00Z",
        )
        storage.save_token(token_data)
        
        auth = GitHubCopilotAuth(token_storage=storage)
        
        assert auth.is_authenticated() is True

    def test_is_authenticated_true_with_env_token(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test is_authenticated returns True with environment variable."""
        monkeypatch.setenv("LOGAI_GITHUB_COPILOT_TOKEN", "gho_env_token_123456")
        
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        auth = GitHubCopilotAuth(token_storage=storage)
        
        assert auth.is_authenticated() is True

    def test_is_authenticated_false_when_no_token(self, tmp_path: Path) -> None:
        """Test is_authenticated returns False when no token."""
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        auth = GitHubCopilotAuth(token_storage=storage)
        
        assert auth.is_authenticated() is False


class TestGitHubCopilotAuthGetToken:
    """Test suite for get_token method."""

    def test_get_token_from_file(self, tmp_path: Path) -> None:
        """Test get_token retrieves token from file."""
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        
        # Save token
        token_data = TokenData(
            token="gho_file_token_123456789",
            created_at="2026-02-11T10:00:00Z",
        )
        storage.save_token(token_data)
        
        auth = GitHubCopilotAuth(token_storage=storage)
        token = auth.get_token()
        
        assert token == "gho_file_token_123456789"

    def test_get_token_from_environment(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test get_token retrieves token from environment variable."""
        monkeypatch.setenv("LOGAI_GITHUB_COPILOT_TOKEN", "gho_env_token_123456789")
        
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        auth = GitHubCopilotAuth(token_storage=storage)
        
        token = auth.get_token()
        
        assert token == "gho_env_token_123456789"

    def test_get_token_env_takes_precedence(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that environment variable takes precedence over file."""
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        
        # Save token to file
        token_data = TokenData(
            token="gho_file_token_123456789",
            created_at="2026-02-11T10:00:00Z",
        )
        storage.save_token(token_data)
        
        # Set environment variable
        monkeypatch.setenv("LOGAI_GITHUB_COPILOT_TOKEN", "gho_env_token_987654321")
        
        auth = GitHubCopilotAuth(token_storage=storage)
        token = auth.get_token()
        
        # Should return env token, not file token
        assert token == "gho_env_token_987654321"

    def test_get_token_returns_none_when_no_token(self, tmp_path: Path) -> None:
        """Test get_token returns None when no token exists."""
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        auth = GitHubCopilotAuth(token_storage=storage)
        
        token = auth.get_token()
        
        assert token is None

    def test_get_token_validates_env_token_format(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test get_token validates environment token format."""
        # Set invalid token
        monkeypatch.setenv("LOGAI_GITHUB_COPILOT_TOKEN", "invalid_token")
        
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        auth = GitHubCopilotAuth(token_storage=storage)
        
        token = auth.get_token()
        
        # Should return None for invalid format
        assert token is None

    def test_get_token_rejects_short_env_token(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test get_token rejects too-short environment token."""
        # Set short token
        monkeypatch.setenv("LOGAI_GITHUB_COPILOT_TOKEN", "gho_123")
        
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        auth = GitHubCopilotAuth(token_storage=storage)
        
        token = auth.get_token()
        
        assert token is None


class TestGitHubCopilotAuthLogout:
    """Test suite for logout method."""

    def test_logout_removes_token(self, tmp_path: Path) -> None:
        """Test logout removes stored token."""
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        
        # Save token
        token_data = TokenData(
            token="gho_test123456789012345",
            created_at="2026-02-11T10:00:00Z",
        )
        storage.save_token(token_data)
        
        auth = GitHubCopilotAuth(token_storage=storage)
        result = auth.logout()
        
        assert result is True
        assert auth.get_token() is None

    def test_logout_returns_false_when_no_token(self, tmp_path: Path) -> None:
        """Test logout returns False when no token exists."""
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        auth = GitHubCopilotAuth(token_storage=storage)
        
        result = auth.logout()
        
        assert result is False

    def test_logout_does_not_affect_env_token(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test logout does not remove environment variable token."""
        monkeypatch.setenv("LOGAI_GITHUB_COPILOT_TOKEN", "gho_env_token_123456")
        
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        auth = GitHubCopilotAuth(token_storage=storage)
        
        auth.logout()
        
        # Environment token should still be accessible
        assert auth.get_token() == "gho_env_token_123456"


class TestGitHubCopilotAuthGetStatus:
    """Test suite for get_status method."""

    def test_get_status_authenticated_from_file(self, tmp_path: Path) -> None:
        """Test get_status when authenticated via file."""
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        
        # Save token
        token_data = TokenData(
            token="gho_test123456789012345",
            created_at="2026-02-11T10:00:00Z",
        )
        storage.save_token(token_data)
        
        auth = GitHubCopilotAuth(token_storage=storage)
        status = auth.get_status()
        
        assert status["authenticated"] is True
        assert status["source"] == "file"
        assert status["token_prefix"] == "gho_tes..."
        assert status["auth_file"] == str(auth_file)
        assert status["auth_file_exists"] is True

    def test_get_status_authenticated_from_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test get_status when authenticated via environment."""
        monkeypatch.setenv("LOGAI_GITHUB_COPILOT_TOKEN", "gho_env_token_123456")
        
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        auth = GitHubCopilotAuth(token_storage=storage)
        
        status = auth.get_status()
        
        assert status["authenticated"] is True
        assert status["source"] == "environment"
        assert status["token_prefix"] == "gho_env..."

    def test_get_status_not_authenticated(self, tmp_path: Path) -> None:
        """Test get_status when not authenticated."""
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        auth = GitHubCopilotAuth(token_storage=storage)
        
        status = auth.get_status()
        
        assert status["authenticated"] is False
        assert status["source"] is None
        assert status["token_prefix"] is None
        assert status["auth_file"] == str(auth_file)
        assert status["auth_file_exists"] is False

    def test_get_status_masks_token(self, tmp_path: Path) -> None:
        """Test that get_status masks token."""
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        
        # Save token
        token_data = TokenData(
            token="gho_secret_token_1234567890",
            created_at="2026-02-11T10:00:00Z",
        )
        storage.save_token(token_data)
        
        auth = GitHubCopilotAuth(token_storage=storage)
        status = auth.get_status()
        
        # Should not contain full token
        assert "secret_token_1234567890" not in str(status)
        # Should contain masked version
        assert status["token_prefix"] == "gho_sec..."


class TestGitHubCopilotAuthRequestDeviceCode:
    """Test suite for _request_device_code method."""

    @pytest.mark.asyncio
    async def test_request_device_code_success(self) -> None:
        """Test successful device code request."""
        auth = GitHubCopilotAuth()
        
        # Mock response
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "device_code": "test_device_code_123",
            "user_code": "ABCD-1234",
            "verification_uri": "https://github.com/login/device",
            "expires_in": 900,
            "interval": 5,
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)
        
        with patch.object(auth, '_get_session', return_value=mock_session):
            device_response = await auth._request_device_code()
        
        assert device_response.device_code == "test_device_code_123"
        assert device_response.user_code == "ABCD-1234"
        assert device_response.verification_uri == "https://github.com/login/device"
        assert device_response.expires_in == 900
        assert device_response.interval == 5
        
        await auth.close()

    @pytest.mark.asyncio
    async def test_request_device_code_default_interval(self) -> None:
        """Test device code request uses default interval if not provided."""
        auth = GitHubCopilotAuth()
        
        # Mock response without interval
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "device_code": "test_device_code_123",
            "user_code": "ABCD-1234",
            "verification_uri": "https://github.com/login/device",
            "expires_in": 900,
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)
        
        with patch.object(auth, '_get_session', return_value=mock_session):
            device_response = await auth._request_device_code()
        
        assert device_response.interval == 5  # Default
        
        await auth.close()

    @pytest.mark.asyncio
    async def test_request_device_code_http_error(self) -> None:
        """Test device code request handles HTTP errors."""
        auth = GitHubCopilotAuth()
        
        # Mock error response
        mock_response = MagicMock()
        mock_response.status = 400
        mock_response.text = AsyncMock(return_value="Bad Request")
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)
        
        with patch.object(auth, '_get_session', return_value=mock_session):
            with pytest.raises(GitHubCopilotAuthError, match="Failed to request device code"):
                await auth._request_device_code()
        
        await auth.close()

    @pytest.mark.asyncio
    async def test_request_device_code_network_error(self) -> None:
        """Test device code request handles network errors."""
        auth = GitHubCopilotAuth()
        
        mock_session = MagicMock()
        mock_session.post = MagicMock(side_effect=aiohttp.ClientError("Network error"))
        
        with patch.object(auth, '_get_session', return_value=mock_session):
            with pytest.raises(GitHubCopilotAuthError, match="Network error requesting device code"):
                await auth._request_device_code()
        
        await auth.close()

    @pytest.mark.asyncio
    async def test_request_device_code_missing_field(self) -> None:
        """Test device code request handles missing fields in response."""
        auth = GitHubCopilotAuth()
        
        # Mock response missing required field
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "device_code": "test_device_code_123",
            # Missing user_code
            "verification_uri": "https://github.com/login/device",
            "expires_in": 900,
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)
        
        with patch.object(auth, '_get_session', return_value=mock_session):
            with pytest.raises(GitHubCopilotAuthError, match="Invalid response from GitHub"):
                await auth._request_device_code()
        
        await auth.close()


class TestGitHubCopilotAuthPollForToken:
    """Test suite for _poll_for_token method."""

    @pytest.mark.asyncio
    async def test_poll_for_token_immediate_success(self) -> None:
        """Test polling succeeds immediately."""
        auth = GitHubCopilotAuth()
        
        # Mock successful response
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value={
            "access_token": "gho_success_token_123456",
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)
        
        with patch.object(auth, '_get_session', return_value=mock_session):
            token = await auth._poll_for_token(
                device_code="device_123",
                interval=0.1,
                expires_in=10,
            )
        
        assert token == "gho_success_token_123456"
        
        await auth.close()

    @pytest.mark.asyncio
    async def test_poll_for_token_authorization_pending(self) -> None:
        """Test polling with authorization_pending status."""
        auth = GitHubCopilotAuth()
        
        # Mock pending then success
        responses = [
            {"error": "authorization_pending"},
            {"error": "authorization_pending"},
            {"access_token": "gho_success_token_123456"},
        ]
        response_iter = iter(responses)
        
        mock_response = MagicMock()
        mock_response.json = AsyncMock(side_effect=lambda: next(response_iter))
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)
        
        with patch.object(auth, '_get_session', return_value=mock_session):
            token = await auth._poll_for_token(
                device_code="device_123",
                interval=0.1,  # Short interval for testing
                expires_in=10,
            )
        
        assert token == "gho_success_token_123456"
        
        await auth.close()

    @pytest.mark.asyncio
    async def test_poll_for_token_slow_down(self) -> None:
        """Test polling handles slow_down by increasing interval."""
        auth = GitHubCopilotAuth()
        
        # Mock slow_down then success
        responses = [
            {"error": "slow_down"},
            {"access_token": "gho_success_token_123456"},
        ]
        response_iter = iter(responses)
        
        mock_response = MagicMock()
        mock_response.json = AsyncMock(side_effect=lambda: next(response_iter))
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)
        
        with patch.object(auth, '_get_session', return_value=mock_session):
            with patch('builtins.print'):  # Suppress print output
                token = await auth._poll_for_token(
                    device_code="device_123",
                    interval=0.1,
                    expires_in=10,
                )
        
        assert token == "gho_success_token_123456"
        
        await auth.close()

    @pytest.mark.asyncio
    async def test_poll_for_token_expired(self) -> None:
        """Test polling handles expired_token error."""
        auth = GitHubCopilotAuth()
        
        # Mock expired_token response
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value={
            "error": "expired_token",
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)
        
        with patch.object(auth, '_get_session', return_value=mock_session):
            with pytest.raises(AuthenticationTimeoutError, match="Device code expired"):
                await auth._poll_for_token(
                    device_code="device_123",
                    interval=0.1,
                    expires_in=10,
                )
        
        await auth.close()

    @pytest.mark.asyncio
    async def test_poll_for_token_access_denied(self) -> None:
        """Test polling handles access_denied error."""
        auth = GitHubCopilotAuth()
        
        # Mock access_denied response
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value={
            "error": "access_denied",
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)
        
        with patch.object(auth, '_get_session', return_value=mock_session):
            with pytest.raises(AuthenticationDeniedError, match="User denied access"):
                await auth._poll_for_token(
                    device_code="device_123",
                    interval=0.1,
                    expires_in=10,
                )
        
        await auth.close()

    @pytest.mark.asyncio
    async def test_poll_for_token_timeout(self) -> None:
        """Test polling times out after expires_in seconds."""
        auth = GitHubCopilotAuth()
        
        # Mock authorization_pending indefinitely
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value={
            "error": "authorization_pending",
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)
        
        with patch.object(auth, '_get_session', return_value=mock_session):
            with pytest.raises(AuthenticationTimeoutError, match="timed out"):
                await auth._poll_for_token(
                    device_code="device_123",
                    interval=0.1,
                    expires_in=0.5,  # Very short timeout
                )
        
        await auth.close()

    @pytest.mark.asyncio
    async def test_poll_for_token_unknown_error(self) -> None:
        """Test polling handles unknown error codes."""
        auth = GitHubCopilotAuth()
        
        # Mock unknown error
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value={
            "error": "unknown_error",
            "error_description": "Something went wrong",
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)
        
        with patch.object(auth, '_get_session', return_value=mock_session):
            with pytest.raises(GitHubCopilotAuthError, match="unknown_error"):
                await auth._poll_for_token(
                    device_code="device_123",
                    interval=0.1,
                    expires_in=10,
                )
        
        await auth.close()

    @pytest.mark.asyncio
    async def test_poll_for_token_network_error_retries(self) -> None:
        """Test polling retries on network errors."""
        auth = GitHubCopilotAuth()
        
        # Mock network error then success
        call_count = 0
        
        def side_effect():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise aiohttp.ClientError("Network error")
            return {"access_token": "gho_success_token_123456"}
        
        mock_response = MagicMock()
        mock_response.json = AsyncMock(side_effect=side_effect)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)
        
        with patch.object(auth, '_get_session', return_value=mock_session):
            with patch('builtins.print'):  # Suppress print output
                token = await auth._poll_for_token(
                    device_code="device_123",
                    interval=0.1,
                    expires_in=10,
                )
        
        assert token == "gho_success_token_123456"
        assert call_count == 2  # First failed, second succeeded
        
        await auth.close()


class TestGitHubCopilotAuthAuthenticate:
    """Test suite for authenticate method."""

    @pytest.mark.asyncio
    async def test_authenticate_full_flow(self, tmp_path: Path) -> None:
        """Test complete authentication flow."""
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        auth = GitHubCopilotAuth(token_storage=storage)
        
        # Mock device code response
        device_response = DeviceCodeResponse(
            device_code="device_123",
            user_code="ABCD-1234",
            verification_uri="https://github.com/login/device",
            expires_in=900,
            interval=5,
        )
        
        # Mock datetime for timestamp
        mock_dt = MagicMock()
        mock_dt.isoformat.return_value = "2026-02-11T10:00:00Z"
        
        with patch.object(auth, '_request_device_code', return_value=device_response):
            with patch.object(auth, '_poll_for_token', return_value="gho_final_token_123456"):
                with patch('logai.auth.github_copilot_auth.datetime') as mock_datetime:
                    mock_datetime.now.return_value = mock_dt
                    with patch('builtins.print'):  # Suppress print output
                        token = await auth.authenticate()
        
        assert token == "gho_final_token_123456"
        
        # Verify token was saved
        loaded = storage.load_token()
        assert loaded is not None
        assert loaded.token == "gho_final_token_123456"
        assert loaded.device_code == "device_123"

    @pytest.mark.asyncio
    async def test_authenticate_with_custom_timeout(self, tmp_path: Path) -> None:
        """Test authenticate respects custom timeout."""
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        auth = GitHubCopilotAuth(token_storage=storage)
        
        device_response = DeviceCodeResponse(
            device_code="device_123",
            user_code="ABCD-1234",
            verification_uri="https://github.com/login/device",
            expires_in=900,
            interval=5,
        )
        
        poll_called_with = {}
        
        async def mock_poll(**kwargs):
            poll_called_with.update(kwargs)
            return "gho_token_123456"
        
        # Mock datetime for timestamp
        mock_dt = MagicMock()
        mock_dt.isoformat.return_value = "2026-02-11T10:00:00Z"
        
        with patch.object(auth, '_request_device_code', return_value=device_response):
            with patch.object(auth, '_poll_for_token', side_effect=mock_poll):
                with patch('logai.auth.github_copilot_auth.datetime') as mock_datetime:
                    mock_datetime.now.return_value = mock_dt
                    with patch('builtins.print'):
                        await auth.authenticate(timeout=300)
        
        # Verify timeout was used (min of device expires_in and custom timeout)
        assert poll_called_with['expires_in'] == 300

    @pytest.mark.asyncio
    async def test_authenticate_closes_session_on_error(self, tmp_path: Path) -> None:
        """Test authenticate closes session even on error."""
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        auth = GitHubCopilotAuth(token_storage=storage)
        
        with patch.object(auth, '_request_device_code', side_effect=GitHubCopilotAuthError("Test error")):
            with pytest.raises(GitHubCopilotAuthError):
                await auth.authenticate()
        
        # Session should be closed even though error occurred
        if auth._http_session:
            assert auth._http_session.closed


class TestGitHubCopilotAuthHelpers:
    """Test suite for helper methods."""

    def test_display_instructions(self, capsys) -> None:
        """Test _display_instructions displays correct information."""
        response = DeviceCodeResponse(
            device_code="device_123",
            user_code="ABCD-1234",
            verification_uri="https://github.com/login/device",
            expires_in=900,
            interval=5,
        )
        
        GitHubCopilotAuth._display_instructions(response)
        
        captured = capsys.readouterr()
        assert "ABCD-1234" in captured.out
        assert "https://github.com/login/device" in captured.out
        assert "15 minutes" in captured.out  # 900 seconds = 15 minutes

    def test_mask_token_with_valid_token(self) -> None:
        """Test _mask_token with valid token."""
        result = GitHubCopilotAuth._mask_token("gho_1234567890abcdef")
        assert result == "gho_123..."

    def test_mask_token_with_short_token(self) -> None:
        """Test _mask_token with short token."""
        result = GitHubCopilotAuth._mask_token("short")
        assert result == "***"

    def test_mask_token_with_none(self) -> None:
        """Test _mask_token with None."""
        result = GitHubCopilotAuth._mask_token(None)
        assert result is None


class TestGitHubCopilotAuthExceptions:
    """Test suite for exception hierarchy."""

    def test_exception_hierarchy(self) -> None:
        """Test exception class hierarchy."""
        # Verify inheritance
        assert issubclass(AuthenticationTimeoutError, GitHubCopilotAuthError)
        assert issubclass(AuthenticationDeniedError, GitHubCopilotAuthError)
        assert issubclass(GitHubCopilotAuthError, Exception)

    def test_authentication_timeout_error_message(self) -> None:
        """Test AuthenticationTimeoutError can be raised with message."""
        error = AuthenticationTimeoutError("Timeout occurred")
        assert str(error) == "Timeout occurred"

    def test_authentication_denied_error_message(self) -> None:
        """Test AuthenticationDeniedError can be raised with message."""
        error = AuthenticationDeniedError("Access denied")
        assert str(error) == "Access denied"

    def test_github_copilot_auth_error_message(self) -> None:
        """Test GitHubCopilotAuthError can be raised with message."""
        error = GitHubCopilotAuthError("Auth error")
        assert str(error) == "Auth error"


class TestGitHubCopilotAuthConstants:
    """Test suite for class constants."""

    def test_constants_defined(self) -> None:
        """Test that required constants are defined."""
        assert hasattr(GitHubCopilotAuth, 'DEVICE_CODE_URL')
        assert hasattr(GitHubCopilotAuth, 'TOKEN_URL')
        assert hasattr(GitHubCopilotAuth, 'CLIENT_ID')
        assert hasattr(GitHubCopilotAuth, 'SCOPES')
        assert hasattr(GitHubCopilotAuth, 'DEFAULT_TIMEOUT')

    def test_constants_values(self) -> None:
        """Test that constants have expected values."""
        assert GitHubCopilotAuth.DEVICE_CODE_URL == "https://github.com/login/device/code"
        assert GitHubCopilotAuth.TOKEN_URL == "https://github.com/login/oauth/access_token"
        assert GitHubCopilotAuth.CLIENT_ID == "Iv1.b507a08c87ecfe98"
        assert GitHubCopilotAuth.SCOPES == "read:user"
        assert GitHubCopilotAuth.DEFAULT_TIMEOUT == 900
