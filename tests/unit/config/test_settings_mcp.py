"""Unit tests for MCP-related fields in LogAISettings."""

import os

import pytest
from logai.config.settings import LogAISettings
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clean_mcp_env(clean_env: None) -> None:
    """Ensure a clean env for every test in this module.

    We rely on the shared ``clean_env`` fixture from conftest.py to strip
    LOGAI_* and AWS_* vars, then supply only the bare minimum needed to
    instantiate LogAISettings without validation failures.
    """
    os.environ["LOGAI_ANTHROPIC_API_KEY"] = "sk-ant-test-key"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


# ---------------------------------------------------------------------------
# Default value tests
# ---------------------------------------------------------------------------


class TestMCPSettingsDefaults:
    """Tests for default values of MCP-related settings fields."""

    def test_mcp_server_command_default(self) -> None:
        """mcp_server_command must default to 'uvx'."""
        settings = LogAISettings(_env_file=None)  # type: ignore[call-arg]
        assert settings.mcp_server_command == "uvx"

    def test_mcp_server_args_default(self) -> None:
        """mcp_server_args must default to ['awslabs.cloudwatch-mcp-server@latest']."""
        settings = LogAISettings(_env_file=None)  # type: ignore[call-arg]
        assert settings.mcp_server_args == ["awslabs.cloudwatch-mcp-server@latest"]

    def test_mcp_server_args_is_list(self) -> None:
        """mcp_server_args must always be a list type."""
        settings = LogAISettings(_env_file=None)  # type: ignore[call-arg]
        assert isinstance(settings.mcp_server_args, list)


# ---------------------------------------------------------------------------
# Override tests
# ---------------------------------------------------------------------------


class TestMCPSettingsOverrides:
    """Tests verifying that MCP settings can be overridden."""

    def test_mcp_server_command_can_be_overridden(self) -> None:
        """mcp_server_command can be overridden at construction time."""
        settings = LogAISettings(  # type: ignore[call-arg]
            _env_file=None,
            mcp_server_command="npx",
        )
        assert settings.mcp_server_command == "npx"

    def test_mcp_server_args_can_be_overridden(self) -> None:
        """mcp_server_args can be overridden at construction time."""
        custom_args = ["@aws/cloudwatch-mcp@latest", "--verbose"]
        settings = LogAISettings(  # type: ignore[call-arg]
            _env_file=None,
            mcp_server_args=custom_args,
        )
        assert settings.mcp_server_args == custom_args

    def test_mcp_server_command_env_var_override(self) -> None:
        """LOGAI_MCP_SERVER_COMMAND env var must override the default 'uvx'."""
        os.environ["LOGAI_MCP_SERVER_COMMAND"] = "bunx"
        settings = LogAISettings(_env_file=None)  # type: ignore[call-arg]
        assert settings.mcp_server_command == "bunx"

    def test_mcp_settings_independent_of_other_fields(self) -> None:
        """Overriding MCP settings must not affect unrelated fields."""
        settings = LogAISettings(  # type: ignore[call-arg]
            _env_file=None,
            mcp_server_command="npx",
        )
        # Core fields must retain their defaults
        assert settings.llm_provider == "anthropic"
        assert settings.pii_sanitization_enabled is True


# ---------------------------------------------------------------------------
# ollama_num_ctx field tests (num_ctx context window fix)
# ---------------------------------------------------------------------------


class TestOllamaNumCtxSettings:
    """Tests for the ollama_num_ctx field introduced by the num_ctx fix."""

    def test_ollama_num_ctx_default_is_none(self) -> None:
        """ollama_num_ctx must default to None (auto-detected from model registry at runtime)."""
        settings = LogAISettings(_env_file=None)  # type: ignore[call-arg]
        assert settings.ollama_num_ctx is None

    def test_ollama_num_ctx_env_var_override(self) -> None:
        """LOGAI_OLLAMA_NUM_CTX env var must override the default."""
        os.environ["LOGAI_OLLAMA_NUM_CTX"] = "65536"
        settings = LogAISettings(_env_file=None)  # type: ignore[call-arg]
        assert settings.ollama_num_ctx == 65536

    def test_ollama_num_ctx_constructor_override(self) -> None:
        """ollama_num_ctx can be set directly via constructor."""
        settings = LogAISettings(  # type: ignore[call-arg]
            _env_file=None,
            ollama_num_ctx=8192,
        )
        assert settings.ollama_num_ctx == 8192

    def test_ollama_num_ctx_minimum_value(self) -> None:
        """ollama_num_ctx must accept its minimum valid value (1)."""
        settings = LogAISettings(  # type: ignore[call-arg]
            _env_file=None,
            ollama_num_ctx=1,
        )
        assert settings.ollama_num_ctx == 1

    def test_ollama_num_ctx_maximum_value(self) -> None:
        """ollama_num_ctx must accept its maximum valid value (131072)."""
        settings = LogAISettings(  # type: ignore[call-arg]
            _env_file=None,
            ollama_num_ctx=131072,
        )
        assert settings.ollama_num_ctx == 131072

    def test_ollama_num_ctx_zero_is_rejected(self) -> None:
        """ollama_num_ctx=0 must raise a validation error (gt=0 constraint)."""
        with pytest.raises(ValidationError):
            LogAISettings(  # type: ignore[call-arg]
                _env_file=None,
                ollama_num_ctx=0,
            )

    def test_ollama_num_ctx_above_max_is_rejected(self) -> None:
        """ollama_num_ctx > 1048576 must raise a validation error (le=1048576 constraint)."""
        with pytest.raises(ValidationError):
            LogAISettings(  # type: ignore[call-arg]
                _env_file=None,
                ollama_num_ctx=1048577,
            )

    def test_ollama_num_ctx_does_not_affect_other_providers(self) -> None:
        """Changing ollama_num_ctx must not affect llm_provider or other unrelated fields."""
        settings = LogAISettings(  # type: ignore[call-arg]
            _env_file=None,
            ollama_num_ctx=16384,
        )
        # Core provider field must still be the default
        assert settings.llm_provider == "anthropic"
        # Other Ollama defaults unchanged
        assert settings.ollama_model == "llama3.1:8b"
