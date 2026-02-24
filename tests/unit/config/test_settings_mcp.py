"""Unit tests for MCP-related fields in LogAISettings."""

import os

import pytest
from logai.config.settings import LogAISettings

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

    def test_use_mcp_tools_defaults_to_true(self) -> None:
        """use_mcp_tools must default to True (MCP is the default as of Phase 3)."""
        settings = LogAISettings(_env_file=None)  # type: ignore[call-arg]
        assert settings.use_mcp_tools is True

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

    def test_mcp_settings_can_be_overridden_via_constructor(self) -> None:
        """Constructing LogAISettings with use_mcp_tools=False must persist."""
        settings = LogAISettings(  # type: ignore[call-arg]
            _env_file=None,
            use_mcp_tools=False,
        )
        assert settings.use_mcp_tools is False

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

    def test_use_mcp_tools_env_var_override(self) -> None:
        """LOGAI_USE_MCP_TOOLS=true in env must set use_mcp_tools to True."""
        os.environ["LOGAI_USE_MCP_TOOLS"] = "true"
        settings = LogAISettings(_env_file=None)  # type: ignore[call-arg]
        assert settings.use_mcp_tools is True

    def test_mcp_server_command_env_var_override(self) -> None:
        """LOGAI_MCP_SERVER_COMMAND env var must override the default 'uvx'."""
        os.environ["LOGAI_MCP_SERVER_COMMAND"] = "bunx"
        settings = LogAISettings(_env_file=None)  # type: ignore[call-arg]
        assert settings.mcp_server_command == "bunx"

    def test_use_mcp_tools_false_via_env_var(self) -> None:
        """LOGAI_USE_MCP_TOOLS=false must override the default True and set use_mcp_tools to False."""
        os.environ["LOGAI_USE_MCP_TOOLS"] = "false"
        settings = LogAISettings(_env_file=None)  # type: ignore[call-arg]
        assert settings.use_mcp_tools is False

    def test_mcp_settings_independent_of_other_fields(self) -> None:
        """Overriding MCP settings must not affect unrelated fields."""
        settings = LogAISettings(  # type: ignore[call-arg]
            _env_file=None,
            use_mcp_tools=True,
            mcp_server_command="npx",
        )
        # Core fields must retain their defaults
        assert settings.llm_provider == "anthropic"
        assert settings.pii_sanitization_enabled is True
