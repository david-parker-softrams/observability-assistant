"""Tests for configuration settings."""

import os
from pathlib import Path

import pytest

from logai.config import LogAISettings, get_settings, reload_settings


class TestLogAISettings:
    """Test suite for LogAISettings."""

    def test_default_values(self, clean_env: None) -> None:
        """Test default configuration values."""
        # Set only required values
        os.environ["LOGAI_ANTHROPIC_API_KEY"] = "sk-ant-test-key"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

        settings = LogAISettings()  # type: ignore

        assert settings.llm_provider == "anthropic"
        assert settings.pii_sanitization_enabled is True
        assert settings.cache_max_size_mb == 500
        assert settings.cache_ttl_seconds == 86400
        assert settings.log_level == "INFO"

    def test_environment_variable_loading(
        self, clean_env: None, set_env_vars: dict[str, str]
    ) -> None:
        """Test loading configuration from environment variables."""
        settings = LogAISettings()  # type: ignore

        assert settings.llm_provider == "anthropic"
        assert settings.anthropic_api_key == "sk-ant-test-key-12345678901234567890"
        assert settings.openai_api_key == "sk-test-openai-key-12345678901234567890"
        assert settings.aws_region == "us-east-1"
        assert settings.aws_access_key_id == "AKIAIOSFODNN7EXAMPLE"
        assert settings.pii_sanitization_enabled is True
        assert settings.cache_max_size_mb == 500

    def test_aws_profile_support(self, clean_env: None) -> None:
        """Test AWS profile configuration."""
        os.environ["LOGAI_ANTHROPIC_API_KEY"] = "sk-ant-test-key"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
        os.environ["AWS_PROFILE"] = "my-profile"

        settings = LogAISettings()  # type: ignore

        assert settings.aws_profile == "my-profile"
        assert settings.aws_access_key_id is None
        assert settings.aws_secret_access_key is None

    def test_path_expansion(self, clean_env: None) -> None:
        """Test that paths with ~ are expanded."""
        os.environ["LOGAI_ANTHROPIC_API_KEY"] = "sk-ant-test-key"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
        os.environ["LOGAI_CACHE_DIR"] = "~/custom/cache"

        settings = LogAISettings()  # type: ignore

        assert "~" not in str(settings.cache_dir)
        assert settings.cache_dir.is_absolute()

    def test_validate_required_credentials_anthropic(self, clean_env: None) -> None:
        """Test validation of Anthropic credentials."""
        os.environ["LOGAI_LLM_PROVIDER"] = "anthropic"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
        os.environ["AWS_ACCESS_KEY_ID"] = "test"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "test"

        settings = LogAISettings()  # type: ignore

        with pytest.raises(ValueError, match="LOGAI_ANTHROPIC_API_KEY is required"):
            settings.validate_required_credentials()

    def test_validate_required_credentials_openai(self, clean_env: None) -> None:
        """Test validation of OpenAI credentials."""
        os.environ["LOGAI_LLM_PROVIDER"] = "openai"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
        os.environ["AWS_ACCESS_KEY_ID"] = "test"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "test"

        settings = LogAISettings()  # type: ignore

        with pytest.raises(ValueError, match="LOGAI_OPENAI_API_KEY is required"):
            settings.validate_required_credentials()

    def test_validate_required_credentials_aws_region(self, clean_env: None) -> None:
        """Test validation of AWS region."""
        os.environ["LOGAI_ANTHROPIC_API_KEY"] = "sk-ant-test-key"
        os.environ["AWS_ACCESS_KEY_ID"] = "test"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "test"

        settings = LogAISettings()  # type: ignore

        with pytest.raises(ValueError, match="AWS_DEFAULT_REGION is required"):
            settings.validate_required_credentials()

    def test_validate_required_credentials_success(
        self, clean_env: None, set_env_vars: dict[str, str]
    ) -> None:
        """Test successful validation of all credentials."""
        settings = LogAISettings()  # type: ignore

        # Should not raise
        settings.validate_required_credentials()

    def test_current_llm_api_key_anthropic(self, clean_env: None) -> None:
        """Test getting current LLM API key for Anthropic."""
        os.environ["LOGAI_LLM_PROVIDER"] = "anthropic"
        os.environ["LOGAI_ANTHROPIC_API_KEY"] = "sk-ant-test-key"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

        settings = LogAISettings()  # type: ignore

        assert settings.current_llm_api_key == "sk-ant-test-key"

    def test_current_llm_api_key_openai(self, clean_env: None) -> None:
        """Test getting current LLM API key for OpenAI."""
        os.environ["LOGAI_LLM_PROVIDER"] = "openai"
        os.environ["LOGAI_OPENAI_API_KEY"] = "sk-test-openai-key"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

        settings = LogAISettings()  # type: ignore

        assert settings.current_llm_api_key == "sk-test-openai-key"

    def test_current_llm_model_anthropic(self, clean_env: None) -> None:
        """Test getting current LLM model for Anthropic."""
        os.environ["LOGAI_LLM_PROVIDER"] = "anthropic"
        os.environ["LOGAI_ANTHROPIC_API_KEY"] = "sk-ant-test-key"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

        settings = LogAISettings()  # type: ignore

        assert settings.current_llm_model == "claude-3-5-sonnet-20241022"

    def test_current_llm_model_openai(self, clean_env: None) -> None:
        """Test getting current LLM model for OpenAI."""
        os.environ["LOGAI_LLM_PROVIDER"] = "openai"
        os.environ["LOGAI_OPENAI_API_KEY"] = "sk-test-openai-key"
        os.environ["LOGAI_OPENAI_MODEL"] = "gpt-4"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

        settings = LogAISettings()  # type: ignore

        assert settings.current_llm_model == "gpt-4"

    def test_ensure_cache_dir_exists(self, clean_env: None, tmp_path: Path) -> None:
        """Test that cache directory is created if it doesn't exist."""
        cache_dir = tmp_path / "test_cache"

        os.environ["LOGAI_ANTHROPIC_API_KEY"] = "sk-ant-test-key"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
        os.environ["LOGAI_CACHE_DIR"] = str(cache_dir)

        settings = LogAISettings()  # type: ignore

        assert not cache_dir.exists()
        settings.ensure_cache_dir_exists()
        assert cache_dir.exists()
        assert cache_dir.is_dir()

    def test_empty_api_key_validation(self, clean_env: None) -> None:
        """Test that empty API keys are rejected."""
        os.environ["LOGAI_ANTHROPIC_API_KEY"] = "   "
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

        with pytest.raises(ValueError, match="API key cannot be empty"):
            LogAISettings()  # type: ignore

    def test_cache_size_bounds(self, clean_env: None) -> None:
        """Test cache size validation bounds."""
        os.environ["LOGAI_ANTHROPIC_API_KEY"] = "sk-ant-test-key"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

        # Test invalid size (too small)
        os.environ["LOGAI_CACHE_MAX_SIZE_MB"] = "0"
        with pytest.raises(ValueError):
            LogAISettings()  # type: ignore

        # Test invalid size (too large)
        os.environ["LOGAI_CACHE_MAX_SIZE_MB"] = "20000"
        with pytest.raises(ValueError):
            LogAISettings()  # type: ignore

        # Test valid size
        os.environ["LOGAI_CACHE_MAX_SIZE_MB"] = "100"
        settings = LogAISettings()  # type: ignore
        assert settings.cache_max_size_mb == 100

    def test_ollama_configuration(self, clean_env: None) -> None:
        """Test Ollama LLM configuration."""
        os.environ["LOGAI_LLM_PROVIDER"] = "ollama"
        os.environ["LOGAI_OLLAMA_BASE_URL"] = "http://localhost:11434"
        os.environ["LOGAI_OLLAMA_MODEL"] = "llama3.1:8b"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

        settings = LogAISettings()  # type: ignore

        assert settings.llm_provider == "ollama"
        assert settings.ollama_base_url == "http://localhost:11434"
        assert settings.ollama_model == "llama3.1:8b"
        assert settings.current_llm_model == "llama3.1:8b"

    def test_ollama_no_api_key_required(self, clean_env: None) -> None:
        """Test that Ollama doesn't require API key."""
        os.environ["LOGAI_LLM_PROVIDER"] = "ollama"
        os.environ["LOGAI_OLLAMA_BASE_URL"] = "http://localhost:11434"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

        settings = LogAISettings()  # type: ignore

        # Should not raise an error even without API key
        settings.validate_required_credentials()

        # API key should be empty for Ollama
        assert settings.current_llm_api_key == ""

    def test_ollama_missing_base_url(self, clean_env: None) -> None:
        """Test that Ollama requires base URL."""
        os.environ["LOGAI_LLM_PROVIDER"] = "ollama"
        os.environ["LOGAI_OLLAMA_BASE_URL"] = ""
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

        settings = LogAISettings()  # type: ignore

        with pytest.raises(ValueError, match="LOGAI_OLLAMA_BASE_URL is required"):
            settings.validate_required_credentials()


class TestGlobalSettings:
    """Test global settings functions."""

    def test_get_settings_singleton(self, clean_env: None) -> None:
        """Test that get_settings returns the same instance."""
        os.environ["LOGAI_ANTHROPIC_API_KEY"] = "sk-ant-test-key"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2

    def test_reload_settings(self, clean_env: None) -> None:
        """Test that reload_settings creates a new instance."""
        os.environ["LOGAI_ANTHROPIC_API_KEY"] = "sk-ant-test-key"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
        os.environ["LOGAI_CACHE_MAX_SIZE_MB"] = "100"

        # Force a fresh settings instance
        settings1 = reload_settings()
        assert settings1.cache_max_size_mb == 100

        # Change environment
        os.environ["LOGAI_CACHE_MAX_SIZE_MB"] = "200"

        # Old instance should still have old value
        assert settings1.cache_max_size_mb == 100

        # Reload should get new value
        settings2 = reload_settings()
        assert settings2.cache_max_size_mb == 200

        # New calls should get the reloaded instance
        settings3 = get_settings()
        assert settings3 is settings2
