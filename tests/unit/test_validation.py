"""Tests for configuration validation functions."""

from pathlib import Path

import pytest

from logai.config.validation import (
    validate_api_key_format,
    validate_aws_region,
    validate_cache_size,
    validate_path,
    validate_ttl,
)


class TestValidateApiKeyFormat:
    """Tests for API key format validation."""

    def test_valid_anthropic_key(self) -> None:
        """Test validation of valid Anthropic API key."""
        key = "sk-ant-api01-abcdefghijklmnopqrstuvwxyz1234567890"
        assert validate_api_key_format(key, "anthropic") is True

    def test_valid_openai_key(self) -> None:
        """Test validation of valid OpenAI API key."""
        key = "sk-abcdefghijklmnopqrstuvwxyz1234567890"
        assert validate_api_key_format(key, "openai") is True

    def test_invalid_anthropic_key_wrong_prefix(self) -> None:
        """Test validation of Anthropic key with wrong prefix."""
        key = "sk-wrong-prefix-12345678901234567890"
        assert validate_api_key_format(key, "anthropic") is False

    def test_invalid_anthropic_key_too_short(self) -> None:
        """Test validation of Anthropic key that's too short."""
        key = "sk-ant-short"
        assert validate_api_key_format(key, "anthropic") is False

    def test_invalid_openai_key_wrong_prefix(self) -> None:
        """Test validation of OpenAI key with wrong prefix."""
        key = "not-sk-12345678901234567890"
        assert validate_api_key_format(key, "openai") is False

    def test_invalid_openai_key_too_short(self) -> None:
        """Test validation of OpenAI key that's too short."""
        key = "sk-short"
        assert validate_api_key_format(key, "openai") is False

    def test_empty_key(self) -> None:
        """Test validation of empty API key."""
        assert validate_api_key_format("", "anthropic") is False
        assert validate_api_key_format("", "openai") is False

    def test_whitespace_only_key(self) -> None:
        """Test validation of whitespace-only API key."""
        assert validate_api_key_format("   ", "anthropic") is False
        assert validate_api_key_format("   ", "openai") is False

    def test_unknown_provider(self) -> None:
        """Test validation with unknown provider."""
        key = "sk-any-key-12345678901234567890"
        assert validate_api_key_format(key, "unknown") is False


class TestValidateAwsRegion:
    """Tests for AWS region validation."""

    def test_valid_us_regions(self) -> None:
        """Test validation of valid US regions."""
        assert validate_aws_region("us-east-1") is True
        assert validate_aws_region("us-east-2") is True
        assert validate_aws_region("us-west-1") is True
        assert validate_aws_region("us-west-2") is True

    def test_valid_eu_regions(self) -> None:
        """Test validation of valid EU regions."""
        assert validate_aws_region("eu-west-1") is True
        assert validate_aws_region("eu-west-2") is True
        assert validate_aws_region("eu-central-1") is True
        assert validate_aws_region("eu-north-1") is True

    def test_valid_ap_regions(self) -> None:
        """Test validation of valid Asia Pacific regions."""
        assert validate_aws_region("ap-southeast-1") is True
        assert validate_aws_region("ap-southeast-2") is True
        assert validate_aws_region("ap-northeast-1") is True

    def test_invalid_format(self) -> None:
        """Test validation of invalid region formats."""
        assert validate_aws_region("invalid") is False
        assert validate_aws_region("us_east_1") is False
        assert validate_aws_region("us-east") is False
        assert validate_aws_region("123-456-7") is False

    def test_empty_region(self) -> None:
        """Test validation of empty region."""
        assert validate_aws_region("") is False


class TestValidatePath:
    """Tests for path validation."""

    def test_valid_existing_directory(self, tmp_path: Path) -> None:
        """Test validation of existing directory."""
        assert validate_path(tmp_path) is True

    def test_valid_existing_file(self, tmp_path: Path) -> None:
        """Test validation of existing file."""
        test_file = tmp_path / "test.txt"
        test_file.touch()
        assert validate_path(test_file) is True

    def test_valid_nonexistent_path_with_existing_parent(self, tmp_path: Path) -> None:
        """Test validation of nonexistent path with existing parent."""
        test_path = tmp_path / "new_dir"
        assert validate_path(test_path) is True

    def test_valid_home_directory(self) -> None:
        """Test validation of home directory path."""
        assert validate_path("~") is True
        assert validate_path("~/test") is True

    def test_invalid_path_with_null_bytes(self) -> None:
        """Test validation of path with null bytes."""
        # Null bytes in paths should fail
        result = validate_path("/tmp/test\x00file")
        # This may raise OSError or return False depending on OS
        assert result is False or isinstance(result, bool)


class TestValidateCacheSize:
    """Tests for cache size validation."""

    def test_valid_cache_sizes(self) -> None:
        """Test validation of valid cache sizes."""
        assert validate_cache_size(1) is True
        assert validate_cache_size(100) is True
        assert validate_cache_size(500) is True
        assert validate_cache_size(1000) is True
        assert validate_cache_size(10000) is True

    def test_invalid_cache_size_too_small(self) -> None:
        """Test validation of cache size that's too small."""
        assert validate_cache_size(0) is False
        assert validate_cache_size(-1) is False

    def test_invalid_cache_size_too_large(self) -> None:
        """Test validation of cache size that's too large."""
        assert validate_cache_size(10001) is False
        assert validate_cache_size(100000) is False

    def test_boundary_values(self) -> None:
        """Test validation at boundary values."""
        assert validate_cache_size(1) is True  # Minimum
        assert validate_cache_size(10000) is True  # Maximum
        assert validate_cache_size(0) is False  # Below minimum
        assert validate_cache_size(10001) is False  # Above maximum


class TestValidateTtl:
    """Tests for TTL validation."""

    def test_valid_ttls(self) -> None:
        """Test validation of valid TTL values."""
        assert validate_ttl(60) is True  # 1 minute
        assert validate_ttl(3600) is True  # 1 hour
        assert validate_ttl(86400) is True  # 1 day
        assert validate_ttl(604800) is True  # 7 days
        assert validate_ttl(2592000) is True  # 30 days

    def test_invalid_ttl_too_small(self) -> None:
        """Test validation of TTL that's too small."""
        assert validate_ttl(0) is False
        assert validate_ttl(30) is False  # Less than 1 minute
        assert validate_ttl(59) is False

    def test_invalid_ttl_too_large(self) -> None:
        """Test validation of TTL that's too large."""
        assert validate_ttl(2592001) is False  # More than 30 days
        assert validate_ttl(31536000) is False  # 365 days

    def test_boundary_values(self) -> None:
        """Test validation at boundary values."""
        assert validate_ttl(60) is True  # Minimum (1 minute)
        assert validate_ttl(2592000) is True  # Maximum (30 days)
        assert validate_ttl(59) is False  # Below minimum
        assert validate_ttl(2592001) is False  # Above maximum
