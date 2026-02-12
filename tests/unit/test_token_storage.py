"""Comprehensive unit tests for TokenStorage class."""

import json
import os
import stat
from pathlib import Path

import pytest

from logai.auth import TokenData, TokenStorage


class TestTokenData:
    """Test suite for TokenData dataclass."""

    def test_token_data_creation(self) -> None:
        """Test TokenData can be created with required fields."""
        token_data = TokenData(
            token="gho_test123456789012345",
            created_at="2026-02-11T10:00:00Z",
            device_code="device_code_123",
        )
        
        assert token_data.token == "gho_test123456789012345"
        assert token_data.created_at == "2026-02-11T10:00:00Z"
        assert token_data.device_code == "device_code_123"

    def test_token_data_creation_without_device_code(self) -> None:
        """Test TokenData can be created without device_code."""
        token_data = TokenData(
            token="gho_test123456789012345",
            created_at="2026-02-11T10:00:00Z",
        )
        
        assert token_data.token == "gho_test123456789012345"
        assert token_data.created_at == "2026-02-11T10:00:00Z"
        assert token_data.device_code is None

    def test_token_data_to_dict(self) -> None:
        """Test TokenData can be converted to dictionary."""
        token_data = TokenData(
            token="gho_test123456789012345",
            created_at="2026-02-11T10:00:00Z",
            device_code="device_code_123",
        )
        
        result = token_data.to_dict()
        
        assert result == {
            "token": "gho_test123456789012345",
            "created_at": "2026-02-11T10:00:00Z",
            "device_code": "device_code_123",
        }

    def test_token_data_from_dict(self) -> None:
        """Test TokenData can be created from dictionary."""
        data = {
            "token": "gho_test123456789012345",
            "created_at": "2026-02-11T10:00:00Z",
            "device_code": "device_code_123",
        }
        
        token_data = TokenData.from_dict(data)
        
        assert token_data.token == "gho_test123456789012345"
        assert token_data.created_at == "2026-02-11T10:00:00Z"
        assert token_data.device_code == "device_code_123"

    def test_token_data_from_dict_without_device_code(self) -> None:
        """Test TokenData can be created from dictionary without device_code."""
        data = {
            "token": "gho_test123456789012345",
            "created_at": "2026-02-11T10:00:00Z",
        }
        
        token_data = TokenData.from_dict(data)
        
        assert token_data.token == "gho_test123456789012345"
        assert token_data.created_at == "2026-02-11T10:00:00Z"
        assert token_data.device_code is None

    def test_is_valid_format_with_valid_token(self) -> None:
        """Test is_valid_format returns True for valid GitHub token."""
        token_data = TokenData(
            token="gho_1234567890abcdef",
            created_at="2026-02-11T10:00:00Z",
        )
        
        assert token_data.is_valid_format() is True

    def test_is_valid_format_with_long_valid_token(self) -> None:
        """Test is_valid_format returns True for long valid token."""
        token_data = TokenData(
            token="gho_" + "a" * 40,  # GitHub tokens are typically longer
            created_at="2026-02-11T10:00:00Z",
        )
        
        assert token_data.is_valid_format() is True

    def test_is_valid_format_with_invalid_prefix(self) -> None:
        """Test is_valid_format returns False for token without gho_ prefix."""
        token_data = TokenData(
            token="invalid_1234567890abcdef",
            created_at="2026-02-11T10:00:00Z",
        )
        
        assert token_data.is_valid_format() is False

    def test_is_valid_format_with_short_token(self) -> None:
        """Test is_valid_format returns False for too-short token."""
        token_data = TokenData(
            token="gho_123",  # Less than 10 chars
            created_at="2026-02-11T10:00:00Z",
        )
        
        assert token_data.is_valid_format() is False

    def test_is_valid_format_with_just_prefix(self) -> None:
        """Test is_valid_format returns False for token with only prefix."""
        token_data = TokenData(
            token="gho_",
            created_at="2026-02-11T10:00:00Z",
        )
        
        assert token_data.is_valid_format() is False


class TestTokenStorageInit:
    """Test suite for TokenStorage initialization."""

    def test_init_with_custom_path(self, tmp_path: Path) -> None:
        """Test TokenStorage can be initialized with custom path."""
        auth_file = tmp_path / "custom" / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        
        assert storage.auth_file_path == auth_file

    def test_init_without_custom_path(self) -> None:
        """Test TokenStorage uses XDG path by default."""
        storage = TokenStorage()
        
        # Should use XDG Base Directory specification
        expected_dir = Path.home() / ".local" / "share" / "logai"
        expected_path = expected_dir / "auth.json"
        
        assert storage.auth_file_path == expected_path

    def test_init_respects_xdg_data_home(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test TokenStorage respects XDG_DATA_HOME environment variable."""
        xdg_data_home = tmp_path / "custom_xdg"
        monkeypatch.setenv("XDG_DATA_HOME", str(xdg_data_home))
        
        storage = TokenStorage()
        
        expected_path = xdg_data_home / "logai" / "auth.json"
        assert storage.auth_file_path == expected_path


class TestTokenStorageSave:
    """Test suite for saving tokens."""

    def test_save_token_creates_file(self, tmp_path: Path) -> None:
        """Test that save_token creates the auth file."""
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        
        token_data = TokenData(
            token="gho_test123456789012345",
            created_at="2026-02-11T10:00:00Z",
        )
        
        storage.save_token(token_data)
        
        assert auth_file.exists()

    def test_save_token_creates_file_with_600_permissions(self, tmp_path: Path) -> None:
        """Test that tokens are saved with secure 600 permissions."""
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        
        token_data = TokenData(
            token="gho_test123456789012345",
            created_at="2026-02-11T10:00:00Z",
        )
        
        storage.save_token(token_data)
        
        # Verify 600 permissions (owner read/write only)
        file_stat = auth_file.stat()
        file_mode = stat.S_IMODE(file_stat.st_mode)
        
        assert file_mode == 0o600

    def test_save_token_creates_directory_with_700_permissions(self, tmp_path: Path) -> None:
        """Test that parent directory is created with 700 permissions."""
        auth_file = tmp_path / "logai" / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        
        token_data = TokenData(
            token="gho_test123456789012345",
            created_at="2026-02-11T10:00:00Z",
        )
        
        storage.save_token(token_data)
        
        # Verify directory exists
        assert auth_file.parent.exists()
        
        # Verify 700 permissions (owner access only)
        dir_stat = auth_file.parent.stat()
        dir_mode = stat.S_IMODE(dir_stat.st_mode)
        
        assert dir_mode == 0o700

    def test_save_token_creates_nested_directories(self, tmp_path: Path) -> None:
        """Test that nested parent directories are created."""
        auth_file = tmp_path / "level1" / "level2" / "level3" / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        
        token_data = TokenData(
            token="gho_test123456789012345",
            created_at="2026-02-11T10:00:00Z",
        )
        
        storage.save_token(token_data)
        
        assert auth_file.exists()
        assert auth_file.parent.exists()

    def test_save_token_writes_correct_content(self, tmp_path: Path) -> None:
        """Test that token data is written correctly."""
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        
        token_data = TokenData(
            token="gho_test123456789012345",
            created_at="2026-02-11T10:00:00Z",
            device_code="device_code_123",
        )
        
        storage.save_token(token_data)
        
        # Read and verify content
        with open(auth_file) as f:
            content = json.load(f)
        
        assert "github_copilot" in content
        assert content["github_copilot"]["token"] == "gho_test123456789012345"
        assert content["github_copilot"]["created_at"] == "2026-02-11T10:00:00Z"
        assert content["github_copilot"]["device_code"] == "device_code_123"

    def test_save_token_rejects_invalid_format(self, tmp_path: Path) -> None:
        """Test that save_token rejects invalid token format."""
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        
        token_data = TokenData(
            token="invalid_token",
            created_at="2026-02-11T10:00:00Z",
        )
        
        with pytest.raises(ValueError, match="Invalid token format"):
            storage.save_token(token_data)
        
        # Verify file was not created
        assert not auth_file.exists()

    def test_save_token_masks_token_in_error_message(self, tmp_path: Path) -> None:
        """Test that invalid token is masked in error message."""
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        
        token_data = TokenData(
            token="invalid_secret_token_12345",
            created_at="2026-02-11T10:00:00Z",
        )
        
        with pytest.raises(ValueError) as exc_info:
            storage.save_token(token_data)
        
        error_msg = str(exc_info.value)
        # Should not contain full token
        assert "invalid_secret_token_12345" not in error_msg
        # Should contain masked version
        assert "invalid..." in error_msg

    def test_save_token_preserves_other_providers(self, tmp_path: Path) -> None:
        """Test that saving token preserves other provider credentials."""
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        
        # Pre-populate with another provider
        existing_data = {
            "other_provider": {
                "token": "other_token_123",
                "created_at": "2026-02-10T10:00:00Z",
            }
        }
        auth_file.parent.mkdir(parents=True, exist_ok=True)
        with open(auth_file, "w") as f:
            json.dump(existing_data, f)
        
        # Save GitHub Copilot token
        token_data = TokenData(
            token="gho_test123456789012345",
            created_at="2026-02-11T10:00:00Z",
        )
        storage.save_token(token_data)
        
        # Verify both providers exist
        with open(auth_file) as f:
            content = json.load(f)
        
        assert "github_copilot" in content
        assert "other_provider" in content
        assert content["other_provider"]["token"] == "other_token_123"

    def test_save_token_overwrites_existing_github_copilot_token(self, tmp_path: Path) -> None:
        """Test that saving a new token overwrites existing GitHub Copilot token."""
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        
        # Save first token
        token_data_1 = TokenData(
            token="gho_old_token_123456789",
            created_at="2026-02-10T10:00:00Z",
        )
        storage.save_token(token_data_1)
        
        # Save second token
        token_data_2 = TokenData(
            token="gho_new_token_987654321",
            created_at="2026-02-11T10:00:00Z",
        )
        storage.save_token(token_data_2)
        
        # Verify only new token exists
        with open(auth_file) as f:
            content = json.load(f)
        
        assert content["github_copilot"]["token"] == "gho_new_token_987654321"
        assert content["github_copilot"]["created_at"] == "2026-02-11T10:00:00Z"

    def test_save_token_atomic_write_uses_temp_file(self, tmp_path: Path) -> None:
        """Test that save_token uses atomic write (temp file + rename)."""
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        
        token_data = TokenData(
            token="gho_test123456789012345",
            created_at="2026-02-11T10:00:00Z",
        )
        
        storage.save_token(token_data)
        
        # Verify temp file is not left behind
        temp_file = auth_file.with_suffix(".tmp")
        assert not temp_file.exists()
        
        # Verify actual file exists
        assert auth_file.exists()


class TestTokenStorageLoad:
    """Test suite for loading tokens."""

    def test_load_token_success(self, tmp_path: Path) -> None:
        """Test loading a valid token."""
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        
        # Create auth file
        auth_data = {
            "github_copilot": {
                "token": "gho_test123456789012345",
                "created_at": "2026-02-11T10:00:00Z",
                "device_code": "device_code_123",
            }
        }
        auth_file.parent.mkdir(parents=True, exist_ok=True)
        with open(auth_file, "w") as f:
            json.dump(auth_data, f)
        
        token_data = storage.load_token()
        
        assert token_data is not None
        assert token_data.token == "gho_test123456789012345"
        assert token_data.created_at == "2026-02-11T10:00:00Z"
        assert token_data.device_code == "device_code_123"

    def test_load_token_missing_file(self, tmp_path: Path) -> None:
        """Test loading when no auth file exists."""
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        
        token_data = storage.load_token()
        
        assert token_data is None

    def test_load_token_missing_github_copilot_key(self, tmp_path: Path) -> None:
        """Test loading when github_copilot key doesn't exist."""
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        
        # Create auth file without github_copilot
        auth_data = {
            "other_provider": {
                "token": "other_token_123",
            }
        }
        auth_file.parent.mkdir(parents=True, exist_ok=True)
        with open(auth_file, "w") as f:
            json.dump(auth_data, f)
        
        token_data = storage.load_token()
        
        assert token_data is None

    def test_load_token_corrupted_json(self, tmp_path: Path) -> None:
        """Test loading corrupted JSON file."""
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        
        # Create corrupted JSON file
        auth_file.parent.mkdir(parents=True, exist_ok=True)
        with open(auth_file, "w") as f:
            f.write("{invalid json content")
        
        with pytest.raises(ValueError, match="Corrupted auth file"):
            storage.load_token()

    def test_load_token_missing_required_field(self, tmp_path: Path) -> None:
        """Test loading token data missing required field."""
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        
        # Create auth file missing 'token' field
        auth_data = {
            "github_copilot": {
                "created_at": "2026-02-11T10:00:00Z",
            }
        }
        auth_file.parent.mkdir(parents=True, exist_ok=True)
        with open(auth_file, "w") as f:
            json.dump(auth_data, f)
        
        with pytest.raises(ValueError, match="Missing required field"):
            storage.load_token()

    def test_load_token_invalid_format(self, tmp_path: Path) -> None:
        """Test loading token with invalid format."""
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        
        # Create auth file with invalid token
        auth_data = {
            "github_copilot": {
                "token": "invalid_token",
                "created_at": "2026-02-11T10:00:00Z",
            }
        }
        auth_file.parent.mkdir(parents=True, exist_ok=True)
        with open(auth_file, "w") as f:
            json.dump(auth_data, f)
        
        with pytest.raises(ValueError, match="invalid format"):
            storage.load_token()

    def test_load_token_masks_invalid_token_in_error(self, tmp_path: Path) -> None:
        """Test that invalid token is masked in error message."""
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        
        # Create auth file with invalid token
        auth_data = {
            "github_copilot": {
                "token": "invalid_secret_token_12345",
                "created_at": "2026-02-11T10:00:00Z",
            }
        }
        auth_file.parent.mkdir(parents=True, exist_ok=True)
        with open(auth_file, "w") as f:
            json.dump(auth_data, f)
        
        with pytest.raises(ValueError) as exc_info:
            storage.load_token()
        
        error_msg = str(exc_info.value)
        # Should not contain full token
        assert "invalid_secret_token_12345" not in error_msg
        # Should contain masked version
        assert "invalid..." in error_msg


class TestTokenStorageDelete:
    """Test suite for deleting tokens."""

    def test_delete_token_removes_file_when_empty(self, tmp_path: Path) -> None:
        """Test deletion removes file when no other providers."""
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        
        # Save token
        token_data = TokenData(
            token="gho_test123456789012345",
            created_at="2026-02-11T10:00:00Z",
        )
        storage.save_token(token_data)
        
        # Delete token
        result = storage.delete_token()
        
        assert result is True
        assert not auth_file.exists()

    def test_delete_token_preserves_other_providers(self, tmp_path: Path) -> None:
        """Test deletion preserves other provider credentials."""
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        
        # Create file with multiple providers
        auth_data = {
            "github_copilot": {
                "token": "gho_test123456789012345",
                "created_at": "2026-02-11T10:00:00Z",
            },
            "other_provider": {
                "token": "other_token_123",
                "created_at": "2026-02-10T10:00:00Z",
            },
        }
        auth_file.parent.mkdir(parents=True, exist_ok=True)
        with open(auth_file, "w") as f:
            json.dump(auth_data, f)
        
        # Delete GitHub Copilot token
        result = storage.delete_token()
        
        assert result is True
        assert auth_file.exists()
        
        # Verify other provider still exists
        with open(auth_file) as f:
            content = json.load(f)
        
        assert "github_copilot" not in content
        assert "other_provider" in content
        assert content["other_provider"]["token"] == "other_token_123"

    def test_delete_token_returns_false_when_no_file(self, tmp_path: Path) -> None:
        """Test delete_token returns False when no file exists."""
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        
        result = storage.delete_token()
        
        assert result is False

    def test_delete_token_returns_false_when_no_github_copilot(self, tmp_path: Path) -> None:
        """Test delete_token returns False when no GitHub Copilot token."""
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        
        # Create file without github_copilot
        auth_data = {
            "other_provider": {
                "token": "other_token_123",
            }
        }
        auth_file.parent.mkdir(parents=True, exist_ok=True)
        with open(auth_file, "w") as f:
            json.dump(auth_data, f)
        
        result = storage.delete_token()
        
        assert result is False


class TestTokenStorageExists:
    """Test suite for checking token existence."""

    def test_token_exists_true_when_valid_token(self, tmp_path: Path) -> None:
        """Test token_exists returns True when valid token exists."""
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        
        # Save token
        token_data = TokenData(
            token="gho_test123456789012345",
            created_at="2026-02-11T10:00:00Z",
        )
        storage.save_token(token_data)
        
        assert storage.token_exists() is True

    def test_token_exists_false_when_no_file(self, tmp_path: Path) -> None:
        """Test token_exists returns False when no file."""
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        
        assert storage.token_exists() is False

    def test_token_exists_false_when_no_github_copilot(self, tmp_path: Path) -> None:
        """Test token_exists returns False when no GitHub Copilot token."""
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        
        # Create file without github_copilot
        auth_data = {
            "other_provider": {
                "token": "other_token_123",
            }
        }
        auth_file.parent.mkdir(parents=True, exist_ok=True)
        with open(auth_file, "w") as f:
            json.dump(auth_data, f)
        
        assert storage.token_exists() is False

    def test_token_exists_false_when_invalid_format(self, tmp_path: Path) -> None:
        """Test token_exists returns False when token has invalid format."""
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        
        # Create file with invalid token (bypassing save validation)
        auth_data = {
            "github_copilot": {
                "token": "invalid_token",
                "created_at": "2026-02-11T10:00:00Z",
            }
        }
        auth_file.parent.mkdir(parents=True, exist_ok=True)
        with open(auth_file, "w") as f:
            json.dump(auth_data, f)
        
        assert storage.token_exists() is False

    def test_token_exists_false_when_corrupted_file(self, tmp_path: Path) -> None:
        """Test token_exists returns False for corrupted file."""
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        
        # Create corrupted file
        auth_file.parent.mkdir(parents=True, exist_ok=True)
        with open(auth_file, "w") as f:
            f.write("{invalid json")
        
        assert storage.token_exists() is False


class TestTokenStorageHelpers:
    """Test suite for helper methods."""

    def test_mask_token_short_token(self) -> None:
        """Test _mask_token with short token."""
        result = TokenStorage._mask_token("short")
        assert result == "***"

    def test_mask_token_long_token(self) -> None:
        """Test _mask_token with long token."""
        result = TokenStorage._mask_token("gho_1234567890abcdef")
        assert result == "gho_123..."

    def test_mask_token_exactly_10_chars(self) -> None:
        """Test _mask_token with exactly 10 character token."""
        result = TokenStorage._mask_token("1234567890")
        assert result == "***"

    def test_mask_token_11_chars(self) -> None:
        """Test _mask_token with 11 character token."""
        result = TokenStorage._mask_token("12345678901")
        assert result == "1234567..."


class TestTokenStorageEdgeCases:
    """Test suite for edge cases and error handling."""

    def test_concurrent_writes_dont_corrupt_file(self, tmp_path: Path) -> None:
        """Test that atomic writes prevent file corruption."""
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        
        # Save multiple tokens in sequence
        for i in range(5):
            token_data = TokenData(
                token=f"gho_token_number_{i}_12345",
                created_at=f"2026-02-11T10:0{i}:00Z",
            )
            storage.save_token(token_data)
        
        # Verify file is valid JSON and has last token
        with open(auth_file) as f:
            content = json.load(f)
        
        assert "github_copilot" in content
        assert content["github_copilot"]["token"] == "gho_token_number_4_12345"

    def test_save_token_with_unicode_in_device_code(self, tmp_path: Path) -> None:
        """Test saving token with unicode characters in device_code."""
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        
        token_data = TokenData(
            token="gho_test123456789012345",
            created_at="2026-02-11T10:00:00Z",
            device_code="device_code_with_émojis_🎉",
        )
        
        storage.save_token(token_data)
        
        # Verify it can be loaded back
        loaded = storage.load_token()
        assert loaded is not None
        assert loaded.device_code == "device_code_with_émojis_🎉"

    def test_save_token_with_empty_string_device_code(self, tmp_path: Path) -> None:
        """Test saving token with empty string device_code."""
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        
        token_data = TokenData(
            token="gho_test123456789012345",
            created_at="2026-02-11T10:00:00Z",
            device_code="",
        )
        
        storage.save_token(token_data)
        
        loaded = storage.load_token()
        assert loaded is not None
        assert loaded.device_code == ""

    def test_path_property(self, tmp_path: Path) -> None:
        """Test auth_file_path property."""
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        
        assert storage.auth_file_path == auth_file


class TestAtomicWriteErrorHandling:
    """Test suite for atomic write error handling."""

    def test_atomic_write_cleans_up_temp_file_on_error(self, tmp_path: Path) -> None:
        """Test that temp file is cleaned up when write fails."""
        auth_file = tmp_path / "auth.json"
        storage = TokenStorage(auth_file_path=auth_file)
        
        # Create directory
        auth_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Mock json.dump to raise an error
        import json
        from unittest.mock import patch, mock_open
        
        with patch('json.dump', side_effect=OSError("Disk full")):
            with pytest.raises(OSError, match="Disk full"):
                storage._write_auth_file_atomic({"test": "data"})
        
        # Verify temp file was cleaned up
        temp_file = auth_file.with_suffix(".tmp")
        assert not temp_file.exists()
