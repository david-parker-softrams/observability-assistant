"""Comprehensive unit tests for Phase 2 configuration settings.

This test suite verifies all 28 Phase 2 settings that were externalized from
hardcoded values to .env configuration. Tests cover:
- Settings override verification (defaults vs user-provided values)
- Validation constraints (bounds, types, cross-field validation)
- List parsing and type conversion
- Integration with components using these settings
"""

import os
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from logai.config.settings import LogAISettings, reload_settings
from pydantic import ValidationError

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def minimal_env(clean_env: None) -> dict[str, str]:
    """Set up minimal required environment variables."""
    env = {
        "LOGAI_ANTHROPIC_API_KEY": "sk-ant-test-key",
        "AWS_DEFAULT_REGION": "us-east-1",
    }
    for key, value in env.items():
        os.environ[key] = value
    return env


@pytest.fixture
def phase2_custom_settings(minimal_env: dict[str, str]) -> dict[str, str]:
    """Custom Phase 2 settings for override testing."""
    custom = {
        # CloudWatch (4 settings)
        "LOGAI_CLOUDWATCH_CONNECT_TIMEOUT": "10",
        "LOGAI_CLOUDWATCH_READ_TIMEOUT": "60",
        "LOGAI_CLOUDWATCH_MAX_RETRY_ATTEMPTS": "5",
        "LOGAI_CLOUDWATCH_RETRY_MODE": "standard",
        # GitHub Copilot Provider (7 settings)
        "LOGAI_GITHUB_COPILOT_MAX_RETRIES": "5",
        "LOGAI_GITHUB_COPILOT_RETRY_BASE_DELAY": "2.0",
        "LOGAI_GITHUB_COPILOT_RETRY_MAX_DELAY": "16.0",
        "LOGAI_GITHUB_COPILOT_INTEGRATION_ID": "custom-integration",
        "LOGAI_GITHUB_COPILOT_EDITOR_VERSION": "custom/2.0.0",
        "LOGAI_GITHUB_COPILOT_REQUEST_TIMEOUT": "180.0",
        "LOGAI_GITHUB_COPILOT_CONNECT_TIMEOUT": "15.0",
        # GitHub Model Cache (2 settings)
        "LOGAI_GITHUB_MODEL_CACHE_HOURS": "48",
        "LOGAI_GITHUB_MODEL_CACHE_FILE": "custom_models.json",
        # GitHub OAuth (5 settings)
        "LOGAI_GITHUB_OAUTH_CLIENT_ID": "custom-client-id",
        "LOGAI_GITHUB_OAUTH_SCOPES": "user:email read:org",
        "LOGAI_GITHUB_AUTH_TIMEOUT": "1200",
        "LOGAI_GITHUB_AUTH_POLL_INTERVAL": "10",
        "LOGAI_GITHUB_AUTH_SLOW_DOWN_INCREMENT": "10",
        # Tools (4 settings)
        "LOGAI_TOOL_LIST_LOG_GROUPS_DEFAULT_LIMIT": "25",
        "LOGAI_TOOL_LIST_LOG_GROUPS_MAX_LIMIT": "75",
        "LOGAI_TOOL_FETCH_LOGS_DEFAULT_LIMIT": "200",
        "LOGAI_TOOL_FETCH_LOGS_MAX_LIMIT": "2000",
        # Orchestrator (1 setting)
        "LOGAI_ORCHESTRATOR_RETRY_DELAYS": "1.0,2.0,4.0,8.0",
        # UI (4 settings)
        "LOGAI_UI_CONTEXT_UPDATE_THROTTLE": "2.0",
        "LOGAI_UI_TOOL_TIMEOUT_INITIAL": "15",
        "LOGAI_UI_TOOL_TIMEOUT_SUBSEQUENT": "12",
        "LOGAI_UI_TOOL_TIMEOUT_FINAL": "8",
        # Model Discovery (1 setting)
        "LOGAI_MODEL_DISCOVERY_TIMEOUT": "20.0",
    }
    for key, value in custom.items():
        os.environ[key] = value
    return custom


# =============================================================================
# 1. SETTINGS OVERRIDE VERIFICATION
# =============================================================================


class TestDefaultValues:
    """Test that all Phase 2 settings have correct default values."""

    def test_cloudwatch_defaults(self, minimal_env: dict[str, str]) -> None:
        """Verify CloudWatch settings match original hardcoded values."""
        settings = LogAISettings()

        # Original hardcoded values from cloudwatch.py
        assert settings.cloudwatch_connect_timeout == 5
        assert settings.cloudwatch_read_timeout == 30
        assert settings.cloudwatch_max_retry_attempts == 3
        assert settings.cloudwatch_retry_mode == "adaptive"

    def test_github_copilot_provider_defaults(self, minimal_env: dict[str, str]) -> None:
        """Verify GitHub Copilot Provider settings match original hardcoded values."""
        settings = LogAISettings()

        # Original hardcoded values from github_copilot_provider.py
        assert settings.github_copilot_max_retries == 3
        assert settings.github_copilot_retry_base_delay == 1.0
        assert settings.github_copilot_retry_max_delay == 8.0
        assert settings.github_copilot_integration_id == "vscode-chat"
        assert settings.github_copilot_editor_version == "vscode/1.98.2"
        assert settings.github_copilot_request_timeout == 120.0
        assert settings.github_copilot_connect_timeout == 10.0

    def test_github_model_cache_defaults(self, minimal_env: dict[str, str]) -> None:
        """Verify GitHub Model Cache settings match original hardcoded values."""
        settings = LogAISettings()

        # Original hardcoded values from github_copilot_models.py
        assert settings.github_model_cache_hours == 24
        assert settings.github_model_cache_file == "github_copilot_models.json"

    def test_github_oauth_defaults(self, minimal_env: dict[str, str]) -> None:
        """Verify GitHub OAuth settings match original hardcoded values."""
        settings = LogAISettings()

        # Original hardcoded values from github_copilot_auth.py
        assert settings.github_oauth_client_id == "Iv1.b507a08c87ecfe98"
        assert settings.github_oauth_scopes == "user:email read:user"
        assert settings.github_auth_timeout == 900
        assert settings.github_auth_poll_interval == 5
        assert settings.github_auth_slow_down_increment == 5

    def test_tools_defaults(self, minimal_env: dict[str, str]) -> None:
        """Verify Tools settings match original hardcoded values."""
        settings = LogAISettings()

        # Original hardcoded values from cloudwatch_tools.py
        assert settings.tool_list_log_groups_default_limit == 50
        assert settings.tool_list_log_groups_max_limit == 100
        assert settings.tool_fetch_logs_default_limit == 100
        assert settings.tool_fetch_logs_max_limit == 1000

    def test_orchestrator_defaults(self, minimal_env: dict[str, str]) -> None:
        """Verify Orchestrator settings match original hardcoded values."""
        settings = LogAISettings()

        # Original hardcoded values from orchestrator.py
        assert settings.orchestrator_retry_delays == "0.5,1.0,2.0"
        assert settings.orchestrator_retry_delays_list == [0.5, 1.0, 2.0]

    def test_ui_defaults(self, minimal_env: dict[str, str]) -> None:
        """Verify UI settings match original hardcoded values."""
        settings = LogAISettings()

        # Original hardcoded values from chat.py
        assert settings.ui_context_update_throttle == 1.0
        assert settings.ui_tool_timeout_initial == 10
        assert settings.ui_tool_timeout_subsequent == 8
        assert settings.ui_tool_timeout_final == 5

    def test_model_discovery_defaults(self, minimal_env: dict[str, str]) -> None:
        """Verify Model Discovery settings match original hardcoded values."""
        settings = LogAISettings()

        # Original hardcoded values from github_copilot_models.py
        assert settings.model_discovery_timeout == 10.0


class TestSettingsOverrides:
    """Test that user-provided .env values properly override defaults."""

    def test_cloudwatch_overrides(self, phase2_custom_settings: dict[str, str]) -> None:
        """Verify CloudWatch settings can be overridden."""
        settings = LogAISettings()

        assert settings.cloudwatch_connect_timeout == 10
        assert settings.cloudwatch_read_timeout == 60
        assert settings.cloudwatch_max_retry_attempts == 5
        assert settings.cloudwatch_retry_mode == "standard"

    def test_github_copilot_provider_overrides(
        self, phase2_custom_settings: dict[str, str]
    ) -> None:
        """Verify GitHub Copilot Provider settings can be overridden."""
        settings = LogAISettings()

        assert settings.github_copilot_max_retries == 5
        assert settings.github_copilot_retry_base_delay == 2.0
        assert settings.github_copilot_retry_max_delay == 16.0
        assert settings.github_copilot_integration_id == "custom-integration"
        assert settings.github_copilot_editor_version == "custom/2.0.0"
        assert settings.github_copilot_request_timeout == 180.0
        assert settings.github_copilot_connect_timeout == 15.0

    def test_github_model_cache_overrides(self, phase2_custom_settings: dict[str, str]) -> None:
        """Verify GitHub Model Cache settings can be overridden."""
        settings = LogAISettings()

        assert settings.github_model_cache_hours == 48
        assert settings.github_model_cache_file == "custom_models.json"

    def test_github_oauth_overrides(self, phase2_custom_settings: dict[str, str]) -> None:
        """Verify GitHub OAuth settings can be overridden."""
        settings = LogAISettings()

        assert settings.github_oauth_client_id == "custom-client-id"
        assert settings.github_oauth_scopes == "user:email read:org"
        assert settings.github_auth_timeout == 1200
        assert settings.github_auth_poll_interval == 10
        assert settings.github_auth_slow_down_increment == 10

    def test_tools_overrides(self, phase2_custom_settings: dict[str, str]) -> None:
        """Verify Tools settings can be overridden."""
        settings = LogAISettings()

        assert settings.tool_list_log_groups_default_limit == 25
        assert settings.tool_list_log_groups_max_limit == 75
        assert settings.tool_fetch_logs_default_limit == 200
        assert settings.tool_fetch_logs_max_limit == 2000

    def test_orchestrator_overrides(self, phase2_custom_settings: dict[str, str]) -> None:
        """Verify Orchestrator settings can be overridden."""
        settings = LogAISettings()

        assert settings.orchestrator_retry_delays == "1.0,2.0,4.0,8.0"
        assert settings.orchestrator_retry_delays_list == [1.0, 2.0, 4.0, 8.0]

    def test_ui_overrides(self, phase2_custom_settings: dict[str, str]) -> None:
        """Verify UI settings can be overridden."""
        settings = LogAISettings()

        assert settings.ui_context_update_throttle == 2.0
        assert settings.ui_tool_timeout_initial == 15
        assert settings.ui_tool_timeout_subsequent == 12
        assert settings.ui_tool_timeout_final == 8

    def test_model_discovery_overrides(self, phase2_custom_settings: dict[str, str]) -> None:
        """Verify Model Discovery settings can be overridden."""
        settings = LogAISettings()

        assert settings.model_discovery_timeout == 20.0


# =============================================================================
# 2. VALIDATION TESTING
# =============================================================================


class TestNumericConstraints:
    """Test numeric validation constraints (gt, ge, le)."""

    def test_cloudwatch_connect_timeout_bounds(self, minimal_env: dict[str, str]) -> None:
        """Test CloudWatch connect timeout must be > 0 and <= 60."""
        # Too small
        os.environ["LOGAI_CLOUDWATCH_CONNECT_TIMEOUT"] = "0"
        with pytest.raises(ValidationError) as exc_info:
            LogAISettings()
        assert "greater than 0" in str(exc_info.value).lower()

        # Too large
        os.environ["LOGAI_CLOUDWATCH_CONNECT_TIMEOUT"] = "61"
        with pytest.raises(ValidationError) as exc_info:
            LogAISettings()
        assert "less than or equal to 60" in str(exc_info.value).lower()

        # Valid boundary values
        os.environ["LOGAI_CLOUDWATCH_CONNECT_TIMEOUT"] = "1"
        settings = LogAISettings()
        assert settings.cloudwatch_connect_timeout == 1

        os.environ["LOGAI_CLOUDWATCH_CONNECT_TIMEOUT"] = "60"
        settings = reload_settings()
        assert settings.cloudwatch_connect_timeout == 60

    def test_cloudwatch_read_timeout_bounds(self, minimal_env: dict[str, str]) -> None:
        """Test CloudWatch read timeout must be > 0 and <= 300."""
        # Too small
        os.environ["LOGAI_CLOUDWATCH_READ_TIMEOUT"] = "0"
        with pytest.raises(ValidationError):
            LogAISettings()

        # Too large
        os.environ["LOGAI_CLOUDWATCH_READ_TIMEOUT"] = "301"
        with pytest.raises(ValidationError):
            LogAISettings()

        # Valid
        os.environ["LOGAI_CLOUDWATCH_READ_TIMEOUT"] = "300"
        settings = LogAISettings()
        assert settings.cloudwatch_read_timeout == 300

    def test_cloudwatch_max_retry_attempts_bounds(self, minimal_env: dict[str, str]) -> None:
        """Test CloudWatch max retry attempts must be > 0 and <= 10."""
        # Too small
        os.environ["LOGAI_CLOUDWATCH_MAX_RETRY_ATTEMPTS"] = "0"
        with pytest.raises(ValidationError):
            LogAISettings()

        # Too large
        os.environ["LOGAI_CLOUDWATCH_MAX_RETRY_ATTEMPTS"] = "11"
        with pytest.raises(ValidationError):
            LogAISettings()

        # Valid
        os.environ["LOGAI_CLOUDWATCH_MAX_RETRY_ATTEMPTS"] = "10"
        settings = LogAISettings()
        assert settings.cloudwatch_max_retry_attempts == 10

    def test_github_copilot_max_retries_bounds(self, minimal_env: dict[str, str]) -> None:
        """Test GitHub Copilot max retries must be >= 0 and <= 10."""
        # Negative not allowed
        os.environ["LOGAI_GITHUB_COPILOT_MAX_RETRIES"] = "-1"
        with pytest.raises(ValidationError):
            LogAISettings()

        # Zero is valid (no retries)
        os.environ["LOGAI_GITHUB_COPILOT_MAX_RETRIES"] = "0"
        settings = LogAISettings()
        assert settings.github_copilot_max_retries == 0

        # Too large
        os.environ["LOGAI_GITHUB_COPILOT_MAX_RETRIES"] = "11"
        with pytest.raises(ValidationError):
            LogAISettings()

    def test_github_copilot_retry_base_delay_bounds(self, minimal_env: dict[str, str]) -> None:
        """Test GitHub Copilot base delay must be > 0 and <= 10."""
        # Too small
        os.environ["LOGAI_GITHUB_COPILOT_RETRY_BASE_DELAY"] = "0"
        with pytest.raises(ValidationError):
            LogAISettings()

        # Too large
        os.environ["LOGAI_GITHUB_COPILOT_RETRY_BASE_DELAY"] = "11"
        with pytest.raises(ValidationError):
            LogAISettings()

        # Valid
        os.environ["LOGAI_GITHUB_COPILOT_RETRY_BASE_DELAY"] = "5.5"
        settings = LogAISettings()
        assert settings.github_copilot_retry_base_delay == 5.5

    def test_github_copilot_retry_max_delay_bounds(self, minimal_env: dict[str, str]) -> None:
        """Test GitHub Copilot max delay must be > 0 and <= 60."""
        # Too small
        os.environ["LOGAI_GITHUB_COPILOT_RETRY_MAX_DELAY"] = "0"
        with pytest.raises(ValidationError):
            LogAISettings()

        # Too large
        os.environ["LOGAI_GITHUB_COPILOT_RETRY_MAX_DELAY"] = "61"
        with pytest.raises(ValidationError):
            LogAISettings()

    def test_github_copilot_request_timeout_bounds(self, minimal_env: dict[str, str]) -> None:
        """Test GitHub Copilot request timeout must be > 0 and <= 600."""
        os.environ["LOGAI_GITHUB_COPILOT_REQUEST_TIMEOUT"] = "0"
        with pytest.raises(ValidationError):
            LogAISettings()

        os.environ["LOGAI_GITHUB_COPILOT_REQUEST_TIMEOUT"] = "601"
        with pytest.raises(ValidationError):
            LogAISettings()

    def test_github_model_cache_hours_bounds(self, minimal_env: dict[str, str]) -> None:
        """Test GitHub model cache hours must be > 0 and <= 168 (1 week)."""
        # Too small
        os.environ["LOGAI_GITHUB_MODEL_CACHE_HOURS"] = "0"
        with pytest.raises(ValidationError):
            LogAISettings()

        # Too large (> 1 week)
        os.environ["LOGAI_GITHUB_MODEL_CACHE_HOURS"] = "169"
        with pytest.raises(ValidationError):
            LogAISettings()

        # Valid (1 week)
        os.environ["LOGAI_GITHUB_MODEL_CACHE_HOURS"] = "168"
        settings = LogAISettings()
        assert settings.github_model_cache_hours == 168

    def test_github_auth_timeout_bounds(self, minimal_env: dict[str, str]) -> None:
        """Test GitHub auth timeout must be > 0 and <= 3600 (1 hour)."""
        os.environ["LOGAI_GITHUB_AUTH_TIMEOUT"] = "0"
        with pytest.raises(ValidationError):
            LogAISettings()

        os.environ["LOGAI_GITHUB_AUTH_TIMEOUT"] = "3601"
        with pytest.raises(ValidationError):
            LogAISettings()

    def test_github_auth_poll_interval_bounds(self, minimal_env: dict[str, str]) -> None:
        """Test GitHub auth poll interval must be > 0 and <= 60."""
        os.environ["LOGAI_GITHUB_AUTH_POLL_INTERVAL"] = "0"
        with pytest.raises(ValidationError):
            LogAISettings()

        os.environ["LOGAI_GITHUB_AUTH_POLL_INTERVAL"] = "61"
        with pytest.raises(ValidationError):
            LogAISettings()

    def test_tool_limits_bounds(self, minimal_env: dict[str, str]) -> None:
        """Test tool limits have appropriate bounds."""
        # list_log_groups default must be > 0 and <= 100
        os.environ["LOGAI_TOOL_LIST_LOG_GROUPS_DEFAULT_LIMIT"] = "0"
        with pytest.raises(ValidationError):
            LogAISettings()

        os.environ["LOGAI_TOOL_LIST_LOG_GROUPS_DEFAULT_LIMIT"] = "101"
        with pytest.raises(ValidationError):
            LogAISettings()

        # fetch_logs max must be > 0 and <= 10000
        del os.environ["LOGAI_TOOL_LIST_LOG_GROUPS_DEFAULT_LIMIT"]
        os.environ["LOGAI_TOOL_FETCH_LOGS_MAX_LIMIT"] = "10001"
        with pytest.raises(ValidationError):
            LogAISettings()

    def test_ui_timeout_bounds(self, minimal_env: dict[str, str]) -> None:
        """Test UI timeout settings must be > 0 and <= 60."""
        os.environ["LOGAI_UI_TOOL_TIMEOUT_INITIAL"] = "0"
        with pytest.raises(ValidationError):
            LogAISettings()

        os.environ["LOGAI_UI_TOOL_TIMEOUT_INITIAL"] = "61"
        with pytest.raises(ValidationError):
            LogAISettings()

    def test_ui_context_throttle_bounds(self, minimal_env: dict[str, str]) -> None:
        """Test UI context throttle must be > 0 and <= 10."""
        os.environ["LOGAI_UI_CONTEXT_UPDATE_THROTTLE"] = "0"
        with pytest.raises(ValidationError):
            LogAISettings()

        os.environ["LOGAI_UI_CONTEXT_UPDATE_THROTTLE"] = "11"
        with pytest.raises(ValidationError):
            LogAISettings()

    def test_model_discovery_timeout_bounds(self, minimal_env: dict[str, str]) -> None:
        """Test model discovery timeout must be > 0 and <= 60."""
        os.environ["LOGAI_MODEL_DISCOVERY_TIMEOUT"] = "0"
        with pytest.raises(ValidationError):
            LogAISettings()

        os.environ["LOGAI_MODEL_DISCOVERY_TIMEOUT"] = "61"
        with pytest.raises(ValidationError):
            LogAISettings()


class TestLiteralTypeValidation:
    """Test Literal type validation for enum-like values."""

    def test_cloudwatch_retry_mode_valid_values(self, minimal_env: dict[str, str]) -> None:
        """Test cloudwatch_retry_mode only accepts valid modes."""
        # Valid values
        for mode in ["standard", "legacy", "adaptive"]:
            os.environ["LOGAI_CLOUDWATCH_RETRY_MODE"] = mode
            settings = reload_settings()
            assert settings.cloudwatch_retry_mode == mode

        # Invalid value
        os.environ["LOGAI_CLOUDWATCH_RETRY_MODE"] = "invalid_mode"
        with pytest.raises(ValidationError) as exc_info:
            LogAISettings()
        assert "cloudwatch_retry_mode" in str(exc_info.value).lower()


class TestCrossFieldValidation:
    """Test cross-field validation constraints."""

    def test_retry_max_delay_must_be_gte_base_delay(self, minimal_env: dict[str, str]) -> None:
        """Test github_copilot_retry_max_delay >= github_copilot_retry_base_delay."""
        # Valid: max_delay > base_delay
        os.environ["LOGAI_GITHUB_COPILOT_RETRY_BASE_DELAY"] = "2.0"
        os.environ["LOGAI_GITHUB_COPILOT_RETRY_MAX_DELAY"] = "10.0"
        settings = LogAISettings()
        assert settings.github_copilot_retry_base_delay == 2.0
        assert settings.github_copilot_retry_max_delay == 10.0

        # Valid: max_delay == base_delay
        os.environ["LOGAI_GITHUB_COPILOT_RETRY_BASE_DELAY"] = "5.0"
        os.environ["LOGAI_GITHUB_COPILOT_RETRY_MAX_DELAY"] = "5.0"
        settings = reload_settings()
        assert settings.github_copilot_retry_base_delay == 5.0
        assert settings.github_copilot_retry_max_delay == 5.0

        # Invalid: max_delay < base_delay
        os.environ["LOGAI_GITHUB_COPILOT_RETRY_BASE_DELAY"] = "10.0"
        os.environ["LOGAI_GITHUB_COPILOT_RETRY_MAX_DELAY"] = "5.0"
        with pytest.raises(ValidationError) as exc_info:
            LogAISettings()
        # Check that the error mentions both fields
        assert "github_copilot_retry_max_delay" in str(exc_info.value)
        assert "github_copilot_retry_base_delay" in str(exc_info.value)


class TestListParsing:
    """Test parsing of comma-separated list values."""

    def test_orchestrator_retry_delays_parsing(self, minimal_env: dict[str, str]) -> None:
        """Test orchestrator_retry_delays parses comma-separated string correctly."""
        # Default value
        settings = LogAISettings()
        assert settings.orchestrator_retry_delays == "0.5,1.0,2.0"
        assert settings.orchestrator_retry_delays_list == [0.5, 1.0, 2.0]

        # Custom values
        os.environ["LOGAI_ORCHESTRATOR_RETRY_DELAYS"] = "1.0,2.5,5.0,10.0"
        settings = reload_settings()
        assert settings.orchestrator_retry_delays_list == [1.0, 2.5, 5.0, 10.0]

        # Single value
        os.environ["LOGAI_ORCHESTRATOR_RETRY_DELAYS"] = "3.0"
        settings = reload_settings()
        assert settings.orchestrator_retry_delays_list == [3.0]

    def test_orchestrator_retry_delays_with_whitespace(self, minimal_env: dict[str, str]) -> None:
        """Test orchestrator_retry_delays handles whitespace correctly."""
        # With spaces
        os.environ["LOGAI_ORCHESTRATOR_RETRY_DELAYS"] = "1.0, 2.0, 3.0"
        settings = LogAISettings()
        assert settings.orchestrator_retry_delays_list == [1.0, 2.0, 3.0]

        # Mixed whitespace
        os.environ["LOGAI_ORCHESTRATOR_RETRY_DELAYS"] = "  1.5 ,  3.0  , 6.0  "
        settings = reload_settings()
        assert settings.orchestrator_retry_delays_list == [1.5, 3.0, 6.0]

    def test_orchestrator_retry_delays_invalid_format(self, minimal_env: dict[str, str]) -> None:
        """Test orchestrator_retry_delays raises error on invalid format."""
        # Non-numeric value
        os.environ["LOGAI_ORCHESTRATOR_RETRY_DELAYS"] = "1.0,not_a_number,3.0"
        settings = LogAISettings()
        with pytest.raises(ValueError):
            _ = settings.orchestrator_retry_delays_list

        # Empty string
        os.environ["LOGAI_ORCHESTRATOR_RETRY_DELAYS"] = ""
        settings = reload_settings()
        with pytest.raises(ValueError):
            _ = settings.orchestrator_retry_delays_list


# =============================================================================
# 3. EDGE CASES
# =============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_retries_allowed(self, minimal_env: dict[str, str]) -> None:
        """Test that 0 retries is valid for GitHub Copilot (disables retries)."""
        os.environ["LOGAI_GITHUB_COPILOT_MAX_RETRIES"] = "0"
        settings = LogAISettings()
        assert settings.github_copilot_max_retries == 0

    def test_very_large_timeout_values(self, minimal_env: dict[str, str]) -> None:
        """Test maximum allowed timeout values."""
        os.environ["LOGAI_CLOUDWATCH_READ_TIMEOUT"] = "300"
        os.environ["LOGAI_GITHUB_COPILOT_REQUEST_TIMEOUT"] = "600"
        os.environ["LOGAI_GITHUB_AUTH_TIMEOUT"] = "3600"

        settings = LogAISettings()
        assert settings.cloudwatch_read_timeout == 300
        assert settings.github_copilot_request_timeout == 600.0
        assert settings.github_auth_timeout == 3600

    def test_minimal_timeout_values(self, minimal_env: dict[str, str]) -> None:
        """Test minimum allowed timeout values."""
        os.environ["LOGAI_CLOUDWATCH_CONNECT_TIMEOUT"] = "1"
        os.environ["LOGAI_GITHUB_COPILOT_CONNECT_TIMEOUT"] = "0.1"
        os.environ["LOGAI_UI_TOOL_TIMEOUT_FINAL"] = "1"

        settings = LogAISettings()
        assert settings.cloudwatch_connect_timeout == 1
        assert settings.github_copilot_connect_timeout == 0.1
        assert settings.ui_tool_timeout_final == 1

    def test_float_vs_int_settings(self, minimal_env: dict[str, str]) -> None:
        """Test that float and int settings are properly typed."""
        settings = LogAISettings()

        # These should be int
        assert isinstance(settings.cloudwatch_connect_timeout, int)
        assert isinstance(settings.cloudwatch_max_retry_attempts, int)
        assert isinstance(settings.github_copilot_max_retries, int)
        assert isinstance(settings.github_model_cache_hours, int)

        # These should be float
        assert isinstance(settings.github_copilot_retry_base_delay, float)
        assert isinstance(settings.github_copilot_retry_max_delay, float)
        assert isinstance(settings.github_copilot_request_timeout, float)
        assert isinstance(settings.ui_context_update_throttle, float)

    def test_string_settings_not_stripped(self, minimal_env: dict[str, str]) -> None:
        """Test that string settings preserve meaningful content."""
        os.environ["LOGAI_GITHUB_COPILOT_INTEGRATION_ID"] = "  custom-id  "
        os.environ["LOGAI_GITHUB_MODEL_CACHE_FILE"] = "models.json"

        settings = LogAISettings()
        # Pydantic does NOT strip whitespace by default - it preserves it
        assert settings.github_copilot_integration_id == "  custom-id  "
        assert settings.github_model_cache_file == "models.json"

    def test_empty_list_parsing(self, minimal_env: dict[str, str]) -> None:
        """Test behavior with malformed retry delays."""
        # Just commas
        os.environ["LOGAI_ORCHESTRATOR_RETRY_DELAYS"] = ",,,"
        settings = LogAISettings()
        with pytest.raises(ValueError):
            _ = settings.orchestrator_retry_delays_list


# =============================================================================
# 4. INTEGRATION WITH COMPONENTS (Simplified - Settings Accessibility)
# =============================================================================


class TestComponentSettingsAccessibility:
    """Test that Phase 2 settings are properly accessible for components to use.

    Note: Full integration tests with actual component initialization are in
    separate integration test files. These tests verify settings are correctly
    exposed and accessible.
    """

    def test_cloudwatch_settings_accessible(self, minimal_env: dict[str, str]) -> None:
        """Verify CloudWatch settings are accessible with custom values."""
        os.environ["LOGAI_CLOUDWATCH_CONNECT_TIMEOUT"] = "15"
        os.environ["LOGAI_CLOUDWATCH_READ_TIMEOUT"] = "90"
        os.environ["LOGAI_CLOUDWATCH_MAX_RETRY_ATTEMPTS"] = "5"
        os.environ["LOGAI_CLOUDWATCH_RETRY_MODE"] = "standard"

        settings = reload_settings()

        # Verify CloudWatchDataSource can access these settings
        assert settings.cloudwatch_connect_timeout == 15
        assert settings.cloudwatch_read_timeout == 90
        assert settings.cloudwatch_max_retry_attempts == 5
        assert settings.cloudwatch_retry_mode == "standard"

    def test_github_copilot_provider_settings_accessible(self, minimal_env: dict[str, str]) -> None:
        """Verify GitHub Copilot Provider settings are accessible with custom values."""
        os.environ["LOGAI_GITHUB_COPILOT_MAX_RETRIES"] = "5"
        os.environ["LOGAI_GITHUB_COPILOT_RETRY_BASE_DELAY"] = "2.0"
        os.environ["LOGAI_GITHUB_COPILOT_RETRY_MAX_DELAY"] = "20.0"
        os.environ["LOGAI_GITHUB_COPILOT_REQUEST_TIMEOUT"] = "180.0"
        os.environ["LOGAI_GITHUB_COPILOT_CONNECT_TIMEOUT"] = "20.0"
        os.environ["LOGAI_GITHUB_COPILOT_INTEGRATION_ID"] = "custom-integration"
        os.environ["LOGAI_GITHUB_COPILOT_EDITOR_VERSION"] = "custom/2.0"

        settings = reload_settings()

        # Verify GitHubCopilotProvider can access these settings
        assert settings.github_copilot_max_retries == 5
        assert settings.github_copilot_retry_base_delay == 2.0
        assert settings.github_copilot_retry_max_delay == 20.0
        assert settings.github_copilot_request_timeout == 180.0
        assert settings.github_copilot_connect_timeout == 20.0
        assert settings.github_copilot_integration_id == "custom-integration"
        assert settings.github_copilot_editor_version == "custom/2.0"

    def test_tool_settings_accessible(self, minimal_env: dict[str, str]) -> None:
        """Verify tool limit settings are accessible with custom values."""
        os.environ["LOGAI_TOOL_LIST_LOG_GROUPS_DEFAULT_LIMIT"] = "25"
        os.environ["LOGAI_TOOL_LIST_LOG_GROUPS_MAX_LIMIT"] = "75"
        os.environ["LOGAI_TOOL_FETCH_LOGS_DEFAULT_LIMIT"] = "200"
        os.environ["LOGAI_TOOL_FETCH_LOGS_MAX_LIMIT"] = "5000"

        settings = reload_settings()

        # Verify tool functions can access these settings
        assert settings.tool_list_log_groups_default_limit == 25
        assert settings.tool_list_log_groups_max_limit == 75
        assert settings.tool_fetch_logs_default_limit == 200
        assert settings.tool_fetch_logs_max_limit == 5000

    def test_ui_settings_accessible(self, minimal_env: dict[str, str]) -> None:
        """Verify UI settings are accessible with custom values."""
        os.environ["LOGAI_UI_CONTEXT_UPDATE_THROTTLE"] = "2.5"
        os.environ["LOGAI_UI_TOOL_TIMEOUT_INITIAL"] = "20"
        os.environ["LOGAI_UI_TOOL_TIMEOUT_SUBSEQUENT"] = "15"
        os.environ["LOGAI_UI_TOOL_TIMEOUT_FINAL"] = "10"

        settings = reload_settings()

        # Verify UI components can access these settings
        assert settings.ui_context_update_throttle == 2.5
        assert settings.ui_tool_timeout_initial == 20
        assert settings.ui_tool_timeout_subsequent == 15
        assert settings.ui_tool_timeout_final == 10

    def test_orchestrator_settings_accessible(self, minimal_env: dict[str, str]) -> None:
        """Verify orchestrator settings are accessible with custom values."""
        os.environ["LOGAI_ORCHESTRATOR_RETRY_DELAYS"] = "2.0,4.0,8.0"

        settings = reload_settings()

        # Verify orchestrator can access these settings
        assert settings.orchestrator_retry_delays_list == [2.0, 4.0, 8.0]

    def test_github_oauth_settings_accessible(self, minimal_env: dict[str, str]) -> None:
        """Verify GitHub OAuth settings are accessible with custom values."""
        os.environ["LOGAI_GITHUB_OAUTH_CLIENT_ID"] = "custom-client-id"
        os.environ["LOGAI_GITHUB_OAUTH_SCOPES"] = "user:email read:org"
        os.environ["LOGAI_GITHUB_AUTH_TIMEOUT"] = "1200"
        os.environ["LOGAI_GITHUB_AUTH_POLL_INTERVAL"] = "10"
        os.environ["LOGAI_GITHUB_AUTH_SLOW_DOWN_INCREMENT"] = "10"

        settings = reload_settings()

        # Verify OAuth flow can access these settings
        assert settings.github_oauth_client_id == "custom-client-id"
        assert settings.github_oauth_scopes == "user:email read:org"
        assert settings.github_auth_timeout == 1200
        assert settings.github_auth_poll_interval == 10
        assert settings.github_auth_slow_down_increment == 10

    def test_model_cache_settings_accessible(self, minimal_env: dict[str, str]) -> None:
        """Verify model cache settings are accessible with custom values."""
        os.environ["LOGAI_GITHUB_MODEL_CACHE_HOURS"] = "48"
        os.environ["LOGAI_GITHUB_MODEL_CACHE_FILE"] = "custom_models.json"
        os.environ["LOGAI_MODEL_DISCOVERY_TIMEOUT"] = "20.0"

        settings = reload_settings()

        # Verify model discovery/cache can access these settings
        assert settings.github_model_cache_hours == 48
        assert settings.github_model_cache_file == "custom_models.json"
        assert settings.model_discovery_timeout == 20.0


# =============================================================================
# 5. BACKWARD COMPATIBILITY
# =============================================================================


class TestBackwardCompatibility:
    """Test that defaults maintain backward compatibility with hardcoded values."""

    def test_all_defaults_match_original_hardcoded_values(
        self, minimal_env: dict[str, str]
    ) -> None:
        """Comprehensive test that all 28 Phase 2 settings match original values."""
        settings = LogAISettings()

        # CloudWatch (4 settings)
        assert settings.cloudwatch_connect_timeout == 5
        assert settings.cloudwatch_read_timeout == 30
        assert settings.cloudwatch_max_retry_attempts == 3
        assert settings.cloudwatch_retry_mode == "adaptive"

        # GitHub Copilot Provider (7 settings)
        assert settings.github_copilot_max_retries == 3
        assert settings.github_copilot_retry_base_delay == 1.0
        assert settings.github_copilot_retry_max_delay == 8.0
        assert settings.github_copilot_integration_id == "vscode-chat"
        assert settings.github_copilot_editor_version == "vscode/1.98.2"
        assert settings.github_copilot_request_timeout == 120.0
        assert settings.github_copilot_connect_timeout == 10.0

        # GitHub Model Cache (2 settings)
        assert settings.github_model_cache_hours == 24
        assert settings.github_model_cache_file == "github_copilot_models.json"

        # GitHub OAuth (5 settings)
        assert settings.github_oauth_client_id == "Iv1.b507a08c87ecfe98"
        assert settings.github_oauth_scopes == "user:email read:user"
        assert settings.github_auth_timeout == 900
        assert settings.github_auth_poll_interval == 5
        assert settings.github_auth_slow_down_increment == 5

        # Tools (4 settings)
        assert settings.tool_list_log_groups_default_limit == 50
        assert settings.tool_list_log_groups_max_limit == 100
        assert settings.tool_fetch_logs_default_limit == 100
        assert settings.tool_fetch_logs_max_limit == 1000

        # Orchestrator (1 setting)
        assert settings.orchestrator_retry_delays == "0.5,1.0,2.0"

        # UI (4 settings)
        assert settings.ui_context_update_throttle == 1.0
        assert settings.ui_tool_timeout_initial == 10
        assert settings.ui_tool_timeout_subsequent == 8
        assert settings.ui_tool_timeout_final == 5

        # Model Discovery (1 setting)
        assert settings.model_discovery_timeout == 10.0

        # Total: 28 settings verified

    def test_no_env_vars_uses_all_defaults(self, minimal_env: dict[str, str]) -> None:
        """Test that with no custom env vars, all defaults are used."""
        settings = LogAISettings()

        # Just spot-check a few from each category
        assert settings.cloudwatch_connect_timeout == 5
        assert settings.github_copilot_max_retries == 3
        assert settings.github_oauth_client_id == "Iv1.b507a08c87ecfe98"
        assert settings.tool_list_log_groups_default_limit == 50
        assert settings.orchestrator_retry_delays == "0.5,1.0,2.0"
        assert settings.ui_context_update_throttle == 1.0
        assert settings.model_discovery_timeout == 10.0


# =============================================================================
# 6. SETTINGS RELOAD
# =============================================================================


class TestSettingsReload:
    """Test settings reload functionality with Phase 2 settings."""

    def test_reload_picks_up_new_values(self, minimal_env: dict[str, str]) -> None:
        """Test that reload_settings() picks up changed environment variables."""
        # Initial settings
        settings1 = LogAISettings()
        assert settings1.cloudwatch_connect_timeout == 5

        # Change environment
        os.environ["LOGAI_CLOUDWATCH_CONNECT_TIMEOUT"] = "20"

        # Old instance unchanged
        assert settings1.cloudwatch_connect_timeout == 5

        # Reload gets new value
        settings2 = reload_settings()
        assert settings2.cloudwatch_connect_timeout == 20

    def test_reload_multiple_phase2_settings(self, minimal_env: dict[str, str]) -> None:
        """Test reloading multiple Phase 2 settings at once."""
        # Initial
        settings1 = LogAISettings()
        assert settings1.github_copilot_max_retries == 3
        assert settings1.ui_tool_timeout_initial == 10
        assert settings1.model_discovery_timeout == 10.0

        # Change multiple
        os.environ["LOGAI_GITHUB_COPILOT_MAX_RETRIES"] = "7"
        os.environ["LOGAI_UI_TOOL_TIMEOUT_INITIAL"] = "25"
        os.environ["LOGAI_MODEL_DISCOVERY_TIMEOUT"] = "30.0"

        # Reload
        settings2 = reload_settings()
        assert settings2.github_copilot_max_retries == 7
        assert settings2.ui_tool_timeout_initial == 25
        assert settings2.model_discovery_timeout == 30.0
