"""Unit tests for CLI MCP helper functions (build_mcp_env, register_mcp_tools)."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from logai.cli import build_mcp_env, register_mcp_tools
from logai.config.settings import LogAISettings

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _minimal_settings(**overrides) -> MagicMock:
    """Return a MagicMock mimicking LogAISettings with sensible defaults."""
    settings = MagicMock(spec=LogAISettings)
    settings.aws_profile = overrides.get("aws_profile", None)
    settings.aws_region = overrides.get("aws_region", None)
    return settings


# ---------------------------------------------------------------------------
# build_mcp_env tests
# ---------------------------------------------------------------------------


class TestBuildMcpEnv:
    """Tests for the build_mcp_env() helper."""

    def test_build_mcp_env_inherits_allowlisted_keys(self) -> None:
        """Keys on the allowlist (e.g. PATH) are included; unlisted keys are excluded."""
        # Plant a known allowlisted key and a sentinel non-allowlisted key.
        original_path = os.environ.get("PATH")
        os.environ["PATH"] = "/usr/bin:/bin"
        non_allowlisted_key = "_LOGAI_TEST_NON_ALLOWLISTED_KEY_"
        os.environ[non_allowlisted_key] = "should_not_appear"
        try:
            settings = _minimal_settings()
            env = build_mcp_env(settings)
            # Allowlisted key must be present
            assert env.get("PATH") == "/usr/bin:/bin"
            # Non-allowlisted key must be excluded (security requirement)
            assert non_allowlisted_key not in env
        finally:
            del os.environ[non_allowlisted_key]
            if original_path is not None:
                os.environ["PATH"] = original_path

    def test_build_mcp_env_sets_aws_profile(self) -> None:
        """When settings.aws_profile is set, AWS_PROFILE is injected."""
        settings = _minimal_settings(aws_profile="myprofile")
        env = build_mcp_env(settings)
        assert env.get("AWS_PROFILE") == "myprofile"

    def test_build_mcp_env_sets_aws_region(self) -> None:
        """When settings.aws_region is set, AWS_DEFAULT_REGION is injected."""
        settings = _minimal_settings(aws_region="eu-west-1")
        env = build_mcp_env(settings)
        assert env.get("AWS_DEFAULT_REGION") == "eu-west-1"

    def test_build_mcp_env_sets_fastmcp_log_level(self) -> None:
        """FASTMCP_LOG_LEVEL=ERROR must always be present in the returned dict."""
        settings = _minimal_settings()
        env = build_mcp_env(settings)
        assert env.get("FASTMCP_LOG_LEVEL") == "ERROR"

    def test_build_mcp_env_sets_fastmcp_log_level_regardless_of_aws_settings(self) -> None:
        """FASTMCP_LOG_LEVEL must be set even when both profile and region are None."""
        settings = _minimal_settings(aws_profile=None, aws_region=None)
        env = build_mcp_env(settings)
        assert env["FASTMCP_LOG_LEVEL"] == "ERROR"

    def test_build_mcp_env_skips_none_profile(self) -> None:
        """When settings.aws_profile is None, AWS_PROFILE must not be injected."""
        # Ensure AWS_PROFILE isn't in the process env for this test
        original = os.environ.pop("AWS_PROFILE", None)
        try:
            settings = _minimal_settings(aws_profile=None)
            env = build_mcp_env(settings)
            # Our helper should NOT have set AWS_PROFILE when profile is None
            # (it may already exist via os.environ, but we stripped it above)
            assert "AWS_PROFILE" not in env
        finally:
            if original is not None:
                os.environ["AWS_PROFILE"] = original

    def test_build_mcp_env_skips_empty_profile(self) -> None:
        """When settings.aws_profile is an empty string, AWS_PROFILE is not set."""
        original = os.environ.pop("AWS_PROFILE", None)
        try:
            settings = _minimal_settings(aws_profile="")
            env = build_mcp_env(settings)
            # Empty string is falsy — should not be written to env
            assert "AWS_PROFILE" not in env
        finally:
            if original is not None:
                os.environ["AWS_PROFILE"] = original

    def test_build_mcp_env_skips_none_region(self) -> None:
        """When settings.aws_region is None, AWS_DEFAULT_REGION must not be injected."""
        original = os.environ.pop("AWS_DEFAULT_REGION", None)
        try:
            settings = _minimal_settings(aws_region=None)
            env = build_mcp_env(settings)
            assert "AWS_DEFAULT_REGION" not in env
        finally:
            if original is not None:
                os.environ["AWS_DEFAULT_REGION"] = original

    def test_build_mcp_env_returns_dict(self) -> None:
        """build_mcp_env() must return a plain dict."""
        settings = _minimal_settings()
        env = build_mcp_env(settings)
        assert isinstance(env, dict)

    def test_build_mcp_env_does_not_leak_llm_credentials(self) -> None:
        """LLM API keys present in os.environ must NOT appear in the MCP env dict.

        The MCP subprocess only needs AWS credentials and PATH-related variables.
        Leaking LOGAI_ANTHROPIC_API_KEY or OPENAI_API_KEY into the subprocess
        environment would be a security defect (Gap #12).
        """
        anthropic_key = "LOGAI_ANTHROPIC_API_KEY"
        openai_key = "OPENAI_API_KEY"
        original_anthropic = os.environ.pop(anthropic_key, None)
        original_openai = os.environ.pop(openai_key, None)
        try:
            os.environ[anthropic_key] = "sk-ant-secret123"
            os.environ[openai_key] = "sk-openai-secret"

            settings = _minimal_settings()
            env = build_mcp_env(settings)

            assert (
                anthropic_key not in env
            ), f"{anthropic_key} must not be forwarded to the MCP subprocess"
            assert (
                openai_key not in env
            ), f"{openai_key} must not be forwarded to the MCP subprocess"
        finally:
            # Restore original state to avoid polluting subsequent tests
            del os.environ[anthropic_key]
            del os.environ[openai_key]
            if original_anthropic is not None:
                os.environ[anthropic_key] = original_anthropic
            if original_openai is not None:
                os.environ[openai_key] = original_openai


# ---------------------------------------------------------------------------
# register_mcp_tools tests
# ---------------------------------------------------------------------------


class TestRegisterMcpTools:
    """Tests for the register_mcp_tools() helper."""

    @pytest.mark.asyncio
    async def test_register_mcp_tools_returns_tool_names(self) -> None:
        """register_mcp_tools() must return a list of registered tool names."""
        mock_client = AsyncMock()
        mock_client.list_tools = AsyncMock(
            return_value=[
                {
                    "name": "describe_log_groups",
                    "description": "Lists log groups",
                    "parameters": {"type": "object", "properties": {}},
                },
                {
                    "name": "get_metric_data",
                    "description": "Gets metrics",
                    "parameters": {"type": "object", "properties": {}},
                },
            ]
        )

        mock_processor = MagicMock()

        with patch("logai.cli.ToolRegistry"):
            registered = await register_mcp_tools(mock_client, mock_processor)

        assert "describe_log_groups" in registered
        assert "get_metric_data" in registered
        assert len(registered) == 2

    @pytest.mark.asyncio
    async def test_register_mcp_tools_skips_excluded_tools(self) -> None:
        """Tools in exclude_tools set must be skipped."""
        mock_client = AsyncMock()
        mock_client.list_tools = AsyncMock(
            return_value=[
                {
                    "name": "describe_log_groups",
                    "description": "Lists log groups",
                    "parameters": {"type": "object", "properties": {}},
                },
                {
                    "name": "get_metric_data",
                    "description": "Gets metrics",
                    "parameters": {"type": "object", "properties": {}},
                },
            ]
        )

        mock_processor = MagicMock()

        with patch("logai.cli.ToolRegistry"):
            registered = await register_mcp_tools(
                mock_client, mock_processor, exclude_tools={"describe_log_groups"}
            )

        assert "describe_log_groups" not in registered
        assert "get_metric_data" in registered

    @pytest.mark.asyncio
    async def test_register_mcp_tools_calls_registry_register(self) -> None:
        """register_mcp_tools() must call ToolRegistry.register() for each tool."""
        mock_client = AsyncMock()
        mock_client.list_tools = AsyncMock(
            return_value=[
                {
                    "name": "describe_log_groups",
                    "description": "Lists log groups",
                    "parameters": {"type": "object", "properties": {}},
                },
            ]
        )
        mock_processor = MagicMock()

        with patch("logai.cli.ToolRegistry") as mock_registry:
            await register_mcp_tools(mock_client, mock_processor)
            assert mock_registry.register.called
