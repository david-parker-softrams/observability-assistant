"""Tests for model configuration loading and management."""

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, mock_open, patch

import pytest
from logai.config.model_config import (
    ModelConfig,
    ModelConfigData,
    ModelConfigLoader,
    ValidationResult,
    get_context_window,
    get_encoding,
    get_model_config_loader,
)


class TestModelConfig:
    """Test ModelConfig dataclass."""

    def test_model_config_defaults(self):
        """Test ModelConfig with default values."""
        config = ModelConfig(context_window=8192)
        assert config.context_window == 8192
        assert config.encoding is None
        assert config.chars_per_token == 3.5
        assert config.source == "default"

    def test_model_config_full(self):
        """Test ModelConfig with all values."""
        config = ModelConfig(
            context_window=128000, encoding="cl100k_base", chars_per_token=4.0, source="user"
        )
        assert config.context_window == 128000
        assert config.encoding == "cl100k_base"
        assert config.chars_per_token == 4.0
        assert config.source == "user"

    def test_model_config_immutable(self):
        """Test that ModelConfig is frozen."""
        config = ModelConfig(context_window=8192)
        with pytest.raises(AttributeError):
            config.context_window = 16384  # type: ignore


class TestModelConfigData:
    """Test ModelConfigData dataclass."""

    def test_model_config_data_defaults(self):
        """Test ModelConfigData with defaults."""
        data = ModelConfigData()
        assert data.models == {}
        assert data.defaults.context_window == 8192
        assert data.defaults.encoding == "cl100k_base"
        assert data.schema_version == "1.0"
        assert data.sources == []

    def test_model_config_data_full(self):
        """Test ModelConfigData with values."""
        models = {"gpt-4": ModelConfig(context_window=8192, encoding="cl100k_base")}
        defaults = ModelConfig(context_window=16384, encoding="cl100k_base")
        data = ModelConfigData(
            models=models, defaults=defaults, schema_version="1.0", sources=["test.yaml"]
        )
        assert len(data.models) == 1
        assert data.defaults.context_window == 16384
        assert data.sources == ["test.yaml"]


class TestModelConfigLoader:
    """Test ModelConfigLoader class."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset singleton before each test."""
        ModelConfigLoader.reset_instance()
        yield
        ModelConfigLoader.reset_instance()

    def test_singleton_pattern(self):
        """Test that get_instance returns same instance."""
        loader1 = ModelConfigLoader.get_instance()
        loader2 = ModelConfigLoader.get_instance()
        assert loader1 is loader2

    def test_reset_instance(self):
        """Test that reset_instance clears singleton."""
        loader1 = ModelConfigLoader.get_instance()
        ModelConfigLoader.reset_instance()
        loader2 = ModelConfigLoader.get_instance()
        assert loader1 is not loader2

    def test_load_hardcoded_defaults(self):
        """Test loading with no config files (hardcoded fallback)."""
        loader = ModelConfigLoader()
        # Mock file access to simulate missing files
        with patch.object(Path, "exists", return_value=False):
            config = loader.load()

        assert config is not None
        assert "gpt-4" in config.models
        assert "claude-3-5-sonnet" in config.models
        assert config.defaults.context_window == 8192
        assert "hardcoded" in config.sources

    def test_load_yaml_file_valid(self):
        """Test loading a valid YAML file."""
        yaml_content = """
schema_version: "1.0"
models:
  test-model:
    context_window: 16384
    encoding: cl100k_base
defaults:
  context_window: 8192
  encoding: cl100k_base
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            temp_path = Path(f.name)

        try:
            loader = ModelConfigLoader()
            data = loader._load_yaml_file(temp_path)
            assert data is not None
            assert "models" in data
            assert "test-model" in data["models"]
        finally:
            temp_path.unlink()

    def test_load_yaml_file_invalid_syntax(self):
        """Test loading YAML with invalid syntax."""
        yaml_content = """
models:
  test-model:
    context_window: [invalid: syntax
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            temp_path = Path(f.name)

        try:
            loader = ModelConfigLoader()
            data = loader._load_yaml_file(temp_path)
            assert data is None
        finally:
            temp_path.unlink()

    def test_load_yaml_file_missing(self):
        """Test loading a missing file."""
        loader = ModelConfigLoader()
        data = loader._load_yaml_file(Path("/nonexistent/file.yaml"))
        assert data is None

    def test_validate_config_valid(self):
        """Test validation with valid config."""
        loader = ModelConfigLoader()
        data = {
            "schema_version": "1.0",
            "models": {"gpt-4": {"context_window": 8192, "encoding": "cl100k_base"}},
            "defaults": {"context_window": 8192, "encoding": "cl100k_base"},
        }
        result = loader._validate_config(data)
        assert result.valid
        assert len(result.errors) == 0

    def test_validate_config_invalid_context_window(self):
        """Test validation with invalid context_window."""
        loader = ModelConfigLoader()
        data = {
            "models": {"test": {"context_window": -1}},
            "defaults": {"context_window": 8192, "encoding": "cl100k_base"},
        }
        result = loader._validate_config(data)
        assert not result.valid
        assert any("context_window must be positive" in e for e in result.errors)

    def test_validate_config_invalid_encoding(self):
        """Test validation with invalid encoding type."""
        loader = ModelConfigLoader()
        data = {
            "models": {
                "test": {"encoding": 123}  # Should be string
            },
            "defaults": {"context_window": 8192, "encoding": "cl100k_base"},
        }
        result = loader._validate_config(data)
        assert not result.valid
        assert any("encoding must be string" in e for e in result.errors)

    def test_validate_config_user_partial(self):
        """Test validation with partial user config (should be valid)."""
        loader = ModelConfigLoader()
        data = {"models": {"my-model": {"context_window": 16384}}}
        result = loader._validate_config(data, is_user_config=True)
        assert result.valid

    def test_merge_configs(self):
        """Test merging user config over defaults."""
        loader = ModelConfigLoader()
        base = {
            "models": {"gpt-4": {"context_window": 8192, "encoding": "cl100k_base"}},
            "defaults": {"context_window": 8192, "encoding": "cl100k_base"},
        }
        override = {
            "models": {
                "gpt-4": {"context_window": 16384},  # Override window
                "new-model": {"context_window": 32768},  # Add new model
            }
        }

        result = loader._merge_configs(base, override)

        assert result["models"]["gpt-4"]["context_window"] == 16384
        assert result["models"]["gpt-4"]["encoding"] == "cl100k_base"  # Preserved
        assert "new-model" in result["models"]

    def test_get_model_config_exact_match(self):
        """Test getting config with exact match."""
        loader = ModelConfigLoader()
        # Use hardcoded defaults
        with patch.object(Path, "exists", return_value=False):
            loader.load()

        config = loader.get_model_config("gpt-4")
        assert config.context_window == 8192
        assert config.encoding == "cl100k_base"

    def test_get_model_config_substring_match(self):
        """Test getting config with substring matching."""
        loader = ModelConfigLoader()
        with patch.object(Path, "exists", return_value=False):
            loader.load()

        # "qwen3" should match "qwen3:32b"
        config = loader.get_model_config("qwen3:32b")
        assert config.context_window == 32768

    def test_get_model_config_default_fallback(self):
        """Test getting config for unknown model (uses defaults)."""
        loader = ModelConfigLoader()
        with patch.object(Path, "exists", return_value=False):
            loader.load()

        config = loader.get_model_config("unknown-model")
        assert config.context_window == 8192  # Default
        assert config.encoding == "cl100k_base"

    def test_get_context_window(self):
        """Test convenience method for context window."""
        loader = ModelConfigLoader()
        with patch.object(Path, "exists", return_value=False):
            loader.load()

        window = loader.get_context_window("gpt-4-turbo")
        assert window == 128000

    def test_get_encoding(self):
        """Test convenience method for encoding."""
        loader = ModelConfigLoader()
        with patch.object(Path, "exists", return_value=False):
            loader.load()

        encoding = loader.get_encoding("gpt-4")
        assert encoding == "cl100k_base"

    def test_get_chars_per_token(self):
        """Test convenience method for chars_per_token."""
        loader = ModelConfigLoader()
        with patch.object(Path, "exists", return_value=False):
            loader.load()

        cpt = loader.get_chars_per_token("gpt-4")
        assert cpt == 3.5

    def test_get_all_models(self):
        """Test getting all models."""
        loader = ModelConfigLoader()
        with patch.object(Path, "exists", return_value=False):
            loader.load()

        models = loader.get_all_models()
        assert isinstance(models, dict)
        assert "gpt-4" in models
        assert "claude-3-5-sonnet" in models

    def test_is_loaded(self):
        """Test is_loaded status."""
        loader = ModelConfigLoader()
        assert not loader.is_loaded()

        with patch.object(Path, "exists", return_value=False):
            loader.load()

        assert loader.is_loaded()

    def test_get_sources(self):
        """Test getting config sources."""
        loader = ModelConfigLoader()
        with patch.object(Path, "exists", return_value=False):
            loader.load()

        sources = loader.get_sources()
        assert "hardcoded" in sources

    def test_reload(self):
        """Test reloading config."""
        loader = ModelConfigLoader()
        with patch.object(Path, "exists", return_value=False):
            loader.load()

        assert loader.is_loaded()

        with patch.object(Path, "exists", return_value=False):
            loader.reload()

        assert loader.is_loaded()

    def test_load_with_user_override(self):
        """Test loading with user config override."""
        # Create temporary user config
        user_yaml = """
schema_version: "1.0"
models:
  custom-model:
    context_window: 65536
    encoding: cl100k_base
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(user_yaml)
            user_path = Path(f.name)

        try:
            loader = ModelConfigLoader()
            # Mock USER_CONFIG_PATH to point to our temp file
            with patch.object(ModelConfigLoader, "USER_CONFIG_PATH", user_path):
                with patch.object(Path, "exists", return_value=True):
                    config = loader.load()

            assert "custom-model" in config.models
            assert config.models["custom-model"].context_window == 65536
        finally:
            user_path.unlink()


class TestModuleFunctions:
    """Test module-level convenience functions."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset singleton before each test."""
        ModelConfigLoader.reset_instance()
        yield
        ModelConfigLoader.reset_instance()

    def test_get_model_config_loader(self):
        """Test get_model_config_loader function."""
        loader = get_model_config_loader()
        assert isinstance(loader, ModelConfigLoader)

    def test_get_context_window_function(self):
        """Test get_context_window convenience function."""
        with patch.object(Path, "exists", return_value=False):
            window = get_context_window("gpt-4")
        assert window == 8192

    def test_get_encoding_function(self):
        """Test get_encoding convenience function."""
        with patch.object(Path, "exists", return_value=False):
            encoding = get_encoding("gpt-4")
        assert encoding == "cl100k_base"


class TestBackwardCompatibility:
    """Test backward compatibility with existing code."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset singleton before each test."""
        ModelConfigLoader.reset_instance()
        yield
        ModelConfigLoader.reset_instance()

    def test_all_hardcoded_models_present(self):
        """Test that all hardcoded models are in config."""
        loader = ModelConfigLoader()
        with patch.object(Path, "exists", return_value=False):
            loader.load()

        expected_models = [
            "gpt-4",
            "gpt-4-turbo",
            "gpt-4o",
            "claude-3-5-sonnet",
            "claude-3-opus",
            "claude-opus-4",
            "claude-sonnet-4",
            "github-copilot",
            "llama3.1:8b",
            "llama3.1:70b",
            "qwen3",
        ]

        for model in expected_models:
            config_obj = loader.get_model_config(model)
            assert config_obj.context_window > 0


class TestErrorHandling:
    """Test error handling and graceful degradation."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset singleton before each test."""
        ModelConfigLoader.reset_instance()
        yield
        ModelConfigLoader.reset_instance()

    def test_corrupted_default_config(self):
        """Test handling corrupted default config file."""
        loader = ModelConfigLoader()

        # Mock _load_yaml_file to return None (simulating corrupted file)
        with patch.object(loader, "_load_yaml_file", return_value=None):
            config = loader.load()

        # Should fall back to hardcoded defaults
        assert "hardcoded" in config.sources
        assert "gpt-4" in config.models

    def test_invalid_user_config_ignored(self):
        """Test that invalid user config is ignored."""
        invalid_yaml = "invalid: [syntax: error"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(invalid_yaml)
            user_path = Path(f.name)

        try:
            loader = ModelConfigLoader()
            with patch.object(ModelConfigLoader, "USER_CONFIG_PATH", user_path):
                config = loader.load()

            # Should still have default models
            assert "gpt-4" in config.models
        finally:
            user_path.unlink()

    def test_permission_denied_handled(self):
        """Test handling permission denied errors."""
        loader = ModelConfigLoader()

        with patch("builtins.open", side_effect=PermissionError("Access denied")):
            data = loader._load_yaml_file(Path("/test.yaml"))

        assert data is None


class TestIntegration:
    """Integration tests with TokenCounter."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset singleton before each test."""
        ModelConfigLoader.reset_instance()
        yield
        ModelConfigLoader.reset_instance()

    def test_token_counter_uses_config(self):
        """Test that TokenCounter can use ModelConfigLoader."""
        from logai.core.context.token_counter import TokenCounter

        # Reset TokenCounter's config loader
        TokenCounter._set_config_loader(None)

        with patch.object(Path, "exists", return_value=False):
            window = TokenCounter.get_context_window("gpt-4-turbo")

        assert window == 128000

    def test_token_counter_fallback_on_config_failure(self):
        """Test that TokenCounter falls back if config fails."""
        from logai.core.context.token_counter import TokenCounter

        # Save original loader
        original_loader = TokenCounter._config_loader

        try:
            # Set a broken config loader
            broken_loader = Mock()
            broken_loader.get_context_window.side_effect = Exception("Config error")
            broken_loader.get_chars_per_token.return_value = 3.5  # Prevent Mock division error
            TokenCounter._set_config_loader(broken_loader)

            # Should fall back to hardcoded values
            window = TokenCounter.get_context_window("gpt-4")
            assert window == 8192
        finally:
            # Restore original loader
            TokenCounter._set_config_loader(original_loader)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
