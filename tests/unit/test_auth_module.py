"""Comprehensive unit tests for auth module exports and integration."""

import pytest

from logai import auth


class TestModuleExports:
    """Test suite for verifying module exports."""

    def test_all_classes_exported(self) -> None:
        """Test that all expected classes are exported from auth module."""
        # Core classes
        assert hasattr(auth, 'GitHubCopilotAuth')
        assert hasattr(auth, 'TokenStorage')
        assert hasattr(auth, 'TokenData')
        assert hasattr(auth, 'DeviceCodeResponse')
        
        # Exception classes
        assert hasattr(auth, 'GitHubCopilotAuthError')
        assert hasattr(auth, 'AuthenticationTimeoutError')
        assert hasattr(auth, 'AuthenticationDeniedError')
        
        # Utility functions
        assert hasattr(auth, 'get_github_copilot_token')

    def test_all_exports_listed(self) -> None:
        """Test that __all__ contains all expected exports."""
        expected_exports = {
            'GitHubCopilotAuth',
            'TokenStorage',
            'TokenData',
            'DeviceCodeResponse',
            'GitHubCopilotAuthError',
            'AuthenticationTimeoutError',
            'AuthenticationDeniedError',
            'get_github_copilot_token',  # Jackie's utility function
        }
        
        assert set(auth.__all__) == expected_exports

    def test_classes_are_importable(self) -> None:
        """Test that classes can be imported directly from auth module."""
        from logai.auth import (
            AuthenticationDeniedError,
            AuthenticationTimeoutError,
            DeviceCodeResponse,
            GitHubCopilotAuth,
            GitHubCopilotAuthError,
            TokenData,
            TokenStorage,
            get_github_copilot_token,
        )
        
        # Verify they are not None
        assert GitHubCopilotAuth is not None
        assert TokenStorage is not None
        assert TokenData is not None
        assert DeviceCodeResponse is not None
        assert GitHubCopilotAuthError is not None
        assert AuthenticationTimeoutError is not None
        assert AuthenticationDeniedError is not None
        assert get_github_copilot_token is not None

    def test_no_unexpected_exports(self) -> None:
        """Test that no unexpected items are exported."""
        # Get all public attributes
        public_attrs = [name for name in dir(auth) if not name.startswith('_')]
        
        # Expected public attributes (from __all__)
        expected = set(auth.__all__)
        
        # Filter out Python module attributes
        actual = {name for name in public_attrs if name in expected}
        
        # Verify only expected items
        assert actual == expected


class TestExceptionHierarchy:
    """Test suite for exception class hierarchy."""

    def test_exception_inheritance(self) -> None:
        """Test exception class inheritance hierarchy."""
        from logai.auth import (
            AuthenticationDeniedError,
            AuthenticationTimeoutError,
            GitHubCopilotAuthError,
        )
        
        # Verify inheritance
        assert issubclass(GitHubCopilotAuthError, Exception)
        assert issubclass(AuthenticationTimeoutError, GitHubCopilotAuthError)
        assert issubclass(AuthenticationDeniedError, GitHubCopilotAuthError)

    def test_exceptions_can_be_caught_as_base(self) -> None:
        """Test that specific exceptions can be caught as base exception."""
        from logai.auth import (
            AuthenticationDeniedError,
            AuthenticationTimeoutError,
            GitHubCopilotAuthError,
        )
        
        # Test AuthenticationTimeoutError
        try:
            raise AuthenticationTimeoutError("Timeout")
        except GitHubCopilotAuthError:
            pass  # Should catch it
        else:
            pytest.fail("Should have caught AuthenticationTimeoutError as GitHubCopilotAuthError")
        
        # Test AuthenticationDeniedError
        try:
            raise AuthenticationDeniedError("Denied")
        except GitHubCopilotAuthError:
            pass  # Should catch it
        else:
            pytest.fail("Should have caught AuthenticationDeniedError as GitHubCopilotAuthError")

    def test_exception_messages(self) -> None:
        """Test that exceptions can be created with custom messages."""
        from logai.auth import (
            AuthenticationDeniedError,
            AuthenticationTimeoutError,
            GitHubCopilotAuthError,
        )
        
        error1 = GitHubCopilotAuthError("Base error")
        assert str(error1) == "Base error"
        
        error2 = AuthenticationTimeoutError("Timeout error")
        assert str(error2) == "Timeout error"
        
        error3 = AuthenticationDeniedError("Denied error")
        assert str(error3) == "Denied error"


class TestDataClassIntegration:
    """Test suite for dataclass integration."""

    def test_token_data_dataclass(self) -> None:
        """Test TokenData is a proper dataclass."""
        from logai.auth import TokenData
        
        # Create instance
        token_data = TokenData(
            token="gho_test123",
            created_at="2026-02-11T10:00:00Z",
        )
        
        # Test attribute access
        assert token_data.token == "gho_test123"
        assert token_data.created_at == "2026-02-11T10:00:00Z"
        assert token_data.device_code is None

    def test_device_code_response_dataclass(self) -> None:
        """Test DeviceCodeResponse is a proper dataclass."""
        from logai.auth import DeviceCodeResponse
        
        # Create instance
        response = DeviceCodeResponse(
            device_code="device_123",
            user_code="ABCD-1234",
            verification_uri="https://github.com/login/device",
            expires_in=900,
            interval=5,
        )
        
        # Test attribute access
        assert response.device_code == "device_123"
        assert response.user_code == "ABCD-1234"
        assert response.verification_uri == "https://github.com/login/device"
        assert response.expires_in == 900
        assert response.interval == 5


class TestModuleStructure:
    """Test suite for module structure and organization."""

    def test_module_docstring(self) -> None:
        """Test that auth module has a docstring."""
        from logai import auth
        
        assert auth.__doc__ is not None
        assert len(auth.__doc__.strip()) > 0

    def test_submodules_not_exposed(self) -> None:
        """Test that internal submodules are not exposed in __all__."""
        from logai import auth
        
        # Submodules should not be in __all__
        assert 'github_copilot_auth' not in auth.__all__
        assert 'token_storage' not in auth.__all__

    def test_classes_have_docstrings(self) -> None:
        """Test that all exported classes have docstrings."""
        from logai.auth import (
            AuthenticationDeniedError,
            AuthenticationTimeoutError,
            DeviceCodeResponse,
            GitHubCopilotAuth,
            GitHubCopilotAuthError,
            TokenData,
            TokenStorage,
        )
        
        classes = [
            GitHubCopilotAuth,
            TokenStorage,
            TokenData,
            DeviceCodeResponse,
            GitHubCopilotAuthError,
            AuthenticationTimeoutError,
            AuthenticationDeniedError,
        ]
        
        for cls in classes:
            assert cls.__doc__ is not None, f"{cls.__name__} missing docstring"
            assert len(cls.__doc__.strip()) > 0, f"{cls.__name__} has empty docstring"


class TestCrossClassIntegration:
    """Test suite for integration between classes."""

    def test_github_copilot_auth_uses_token_storage(self, tmp_path) -> None:
        """Test that GitHubCopilotAuth integrates with TokenStorage."""
        from logai.auth import GitHubCopilotAuth, TokenStorage
        
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        
        # GitHubCopilotAuth should accept TokenStorage
        auth = GitHubCopilotAuth(token_storage=storage)
        
        assert auth._storage is storage

    def test_token_storage_uses_token_data(self, tmp_path) -> None:
        """Test that TokenStorage integrates with TokenData."""
        from logai.auth import TokenData, TokenStorage
        
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        
        # TokenStorage should accept TokenData
        token_data = TokenData(
            token="gho_test123456789012345",
            created_at="2026-02-11T10:00:00Z",
        )
        
        storage.save_token(token_data)
        
        # Should be able to load it back
        loaded = storage.load_token()
        assert loaded is not None
        assert isinstance(loaded, TokenData)
        assert loaded.token == token_data.token

    def test_github_copilot_auth_raises_proper_exceptions(self, tmp_path) -> None:
        """Test that GitHubCopilotAuth raises proper exception types."""
        from logai.auth import (
            AuthenticationDeniedError,
            AuthenticationTimeoutError,
            GitHubCopilotAuth,
            GitHubCopilotAuthError,
            TokenStorage,
        )
        
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        auth = GitHubCopilotAuth(token_storage=storage)
        
        # Verify exception types are accessible
        assert AuthenticationTimeoutError is not None
        assert AuthenticationDeniedError is not None
        assert GitHubCopilotAuthError is not None


class TestUtilityFunctions:
    """Test suite for utility functions."""

    def test_get_github_copilot_token_function_exists(self) -> None:
        """Test that get_github_copilot_token function exists."""
        from logai.auth import get_github_copilot_token
        
        assert callable(get_github_copilot_token)

    def test_get_github_copilot_token_returns_none_when_not_authenticated(self, tmp_path) -> None:
        """Test get_github_copilot_token returns None when not authenticated."""
        from logai.auth import get_github_copilot_token
        from unittest.mock import patch
        
        # Mock to use tmp_path
        with patch('logai.auth.GitHubCopilotAuth') as mock_auth_class:
            mock_auth = mock_auth_class.return_value
            mock_auth.get_token.return_value = None
            
            token = get_github_copilot_token()
            
            assert token is None

    def test_get_github_copilot_token_returns_token_when_authenticated(self, tmp_path, monkeypatch) -> None:
        """Test get_github_copilot_token returns token when authenticated."""
        from logai.auth import get_github_copilot_token
        
        # Set environment token for simplicity
        monkeypatch.setenv("LOGAI_GITHUB_COPILOT_TOKEN", "gho_test_token_123456")
        
        token = get_github_copilot_token()
        
        assert token == "gho_test_token_123456"


class TestTypeHints:
    """Test suite for type hint coverage."""

    def test_token_data_type_hints(self) -> None:
        """Test TokenData has proper type hints."""
        from logai.auth import TokenData
        
        # Get type hints
        hints = TokenData.__annotations__
        
        assert 'token' in hints
        assert 'created_at' in hints
        assert 'device_code' in hints

    def test_device_code_response_type_hints(self) -> None:
        """Test DeviceCodeResponse has proper type hints."""
        from logai.auth import DeviceCodeResponse
        
        # Get type hints
        hints = DeviceCodeResponse.__annotations__
        
        assert 'device_code' in hints
        assert 'user_code' in hints
        assert 'verification_uri' in hints
        assert 'expires_in' in hints
        assert 'interval' in hints


class TestModuleInitialization:
    """Test suite for module initialization."""

    def test_module_imports_successfully(self) -> None:
        """Test that auth module can be imported without errors."""
        try:
            import logai.auth
        except Exception as e:
            pytest.fail(f"Failed to import logai.auth: {e}")

    def test_all_imports_from_module_work(self) -> None:
        """Test that all items in __all__ can be imported."""
        from logai import auth
        
        for name in auth.__all__:
            try:
                getattr(auth, name)
            except AttributeError:
                pytest.fail(f"Failed to get {name} from auth module")

    def test_star_import_works(self) -> None:
        """Test that 'from logai.auth import *' works correctly."""
        # This test verifies __all__ is properly defined
        namespace = {}
        exec("from logai.auth import *", namespace)
        
        # Verify all expected items are in namespace
        expected_items = {
            'GitHubCopilotAuth',
            'TokenStorage',
            'TokenData',
            'DeviceCodeResponse',
            'GitHubCopilotAuthError',
            'AuthenticationTimeoutError',
            'AuthenticationDeniedError',
            'get_github_copilot_token',
        }
        
        for item in expected_items:
            assert item in namespace, f"{item} not imported with 'from logai.auth import *'"


class TestSecurityFeatures:
    """Test suite for security-related module features."""

    def test_token_masking_available(self) -> None:
        """Test that token masking functionality is available."""
        from logai.auth import TokenData, TokenStorage
        
        # TokenStorage should have _mask_token method
        assert hasattr(TokenStorage, '_mask_token')
        assert callable(TokenStorage._mask_token)
        
        # Test masking works
        masked = TokenStorage._mask_token("gho_secret_token_123456")
        assert "secret_token" not in masked
        assert "gho_sec..." == masked

    def test_token_validation_available(self) -> None:
        """Test that token validation is available."""
        from logai.auth import TokenData
        
        # TokenData should have is_valid_format method
        token_data = TokenData(
            token="gho_test123456789",
            created_at="2026-02-11T10:00:00Z",
        )
        
        assert hasattr(token_data, 'is_valid_format')
        assert callable(token_data.is_valid_format)
        assert token_data.is_valid_format() is True


class TestBackwardCompatibility:
    """Test suite for ensuring backward compatibility."""

    def test_import_paths_work(self) -> None:
        """Test that all documented import paths work."""
        # Test different import styles
        
        # Style 1: Import from module
        from logai.auth import GitHubCopilotAuth
        assert GitHubCopilotAuth is not None
        
        # Style 2: Import module
        import logai.auth
        assert logai.auth.GitHubCopilotAuth is not None
        
        # Style 3: Import specific module
        from logai import auth
        assert auth.GitHubCopilotAuth is not None

    def test_class_names_stable(self) -> None:
        """Test that class names haven't changed."""
        from logai import auth
        
        # Core class names should be stable
        assert 'GitHubCopilotAuth' in auth.__all__
        assert 'TokenStorage' in auth.__all__
        assert 'TokenData' in auth.__all__
        
        # Exception names should be stable
        assert 'GitHubCopilotAuthError' in auth.__all__
        assert 'AuthenticationTimeoutError' in auth.__all__
        assert 'AuthenticationDeniedError' in auth.__all__
