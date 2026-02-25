"""Configuration settings for LogAI using Pydantic Settings."""

import os
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LogAISettings(BaseSettings):
    """Main configuration settings for LogAI application."""

    model_config = SettingsConfigDict(
        env_prefix="LOGAI_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # === LLM Provider Configuration ===
    llm_provider: Literal["anthropic", "openai", "ollama", "github-copilot"] = Field(
        default="anthropic",
        description="LLM provider to use",
    )

    anthropic_api_key: str | None = Field(
        default=None,
        description="Anthropic API key",
    )

    openai_api_key: str | None = Field(
        default=None,
        description="OpenAI API key",
    )

    anthropic_model: str = Field(
        default="claude-3-5-sonnet-20241022",
        description="Anthropic model to use",
    )

    openai_model: str = Field(
        default="gpt-4-turbo-preview",
        description="OpenAI model to use",
    )

    # === Ollama Configuration ===
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Base URL for Ollama API",
    )

    ollama_model: str = Field(
        default="llama3.1:8b",
        description="Ollama model to use (must support function calling)",
    )

    ollama_num_ctx: int = Field(
        default=32768,
        description=(
            "Ollama context window size (num_ctx). Overrides Ollama's default of 4096 to ensure "
            "full prompt and tool definitions are processed."
        ),
        gt=0,
        le=131072,
    )

    llm_request_timeout: float = Field(
        default=120.0,
        ge=0,
        description=(
            "Timeout in seconds for LLM API requests (applies to Ollama and other LiteLLM "
            "providers). The underlying HTTP library defaults to 600 s (10 min), which causes "
            "silent hangs on slow/unresponsive models. Set to 0 to disable (not recommended)."
        ),
    )

    # === GitHub Copilot Configuration ===
    github_copilot_model: str = Field(
        default="claude-opus-4.5",
        description="GitHub Copilot model to use",
    )

    github_copilot_api_base: str = Field(
        default="https://api.githubcopilot.com/chat/completions",
        description="GitHub Copilot API endpoint URL",
    )

    # === CloudWatch Configuration (Phase 2) ===
    cloudwatch_connect_timeout: int = Field(
        default=5,
        description="CloudWatch API connection timeout in seconds",
        gt=0,
        le=60,
    )
    cloudwatch_read_timeout: int = Field(
        default=30,
        description="CloudWatch API read timeout in seconds",
        gt=0,
        le=300,
    )
    cloudwatch_max_retry_attempts: int = Field(
        default=3,
        description="CloudWatch API maximum retry attempts",
        gt=0,
        le=10,
    )
    cloudwatch_retry_mode: Literal["standard", "legacy", "adaptive"] = Field(
        default="adaptive",
        description="CloudWatch API retry mode",
    )

    # === GitHub Copilot Provider Configuration (Phase 2) ===
    github_copilot_max_retries: int = Field(
        default=3,
        description="Maximum retry attempts for GitHub Copilot API 403 errors",
        ge=0,
        le=10,
    )
    github_copilot_retry_base_delay: float = Field(
        default=1.0,
        description="Base delay in seconds for GitHub Copilot retry backoff",
        gt=0,
        le=10,
    )
    github_copilot_retry_max_delay: float = Field(
        default=8.0,
        description="Maximum delay in seconds for GitHub Copilot retry backoff",
        gt=0,
        le=60,
    )
    github_copilot_integration_id: str = Field(
        default="vscode-chat",
        description="GitHub Copilot integration identifier header",
    )
    github_copilot_editor_version: str = Field(
        default="vscode/1.98.2",
        description="GitHub Copilot editor version header",
    )
    github_copilot_request_timeout: float = Field(
        default=120.0,
        description="GitHub Copilot HTTP request timeout in seconds",
        gt=0,
        le=600,
    )
    github_copilot_connect_timeout: float = Field(
        default=10.0,
        description="GitHub Copilot HTTP connect timeout in seconds",
        gt=0,
        le=60,
    )

    # === GitHub Model Cache (Phase 2) ===
    github_model_cache_hours: int = Field(
        default=24,
        description="Hours to cache GitHub Copilot model list",
        gt=0,
        le=168,
    )
    github_model_cache_file: str = Field(
        default="github_copilot_models.json",
        description="Filename for GitHub Copilot model cache",
    )

    # === GitHub OAuth (Phase 2) ===
    github_oauth_client_id: str = Field(
        default="Iv1.b507a08c87ecfe98",
        description="GitHub OAuth client ID (change only for custom OAuth apps)",
    )
    github_oauth_scopes: str = Field(
        default="user:email read:user",
        description="GitHub OAuth scopes (space-separated)",
    )
    github_auth_timeout: int = Field(
        default=900,
        description="GitHub OAuth authentication timeout in seconds",
        gt=0,
        le=3600,
    )
    github_auth_poll_interval: int = Field(
        default=5,
        description="GitHub OAuth polling interval in seconds",
        gt=0,
        le=60,
    )
    github_auth_slow_down_increment: int = Field(
        default=5,
        description="Seconds to add when GitHub OAuth requests slow_down",
        gt=0,
        le=30,
    )

    # === Tool Configuration (Phase 2) ===
    tool_list_log_groups_default_limit: int = Field(
        default=50,
        description="Default limit for list_log_groups tool",
        gt=0,
        le=100,
    )
    tool_list_log_groups_max_limit: int = Field(
        default=100,
        description="Maximum limit for list_log_groups tool",
        gt=0,
        le=100,
    )
    tool_fetch_logs_default_limit: int = Field(
        default=100,
        description="Default limit for fetch_logs tool",
        gt=0,
        le=10000,
    )
    tool_fetch_logs_max_limit: int = Field(
        default=1000,
        description="Maximum limit for fetch_logs tool",
        gt=0,
        le=10000,
    )

    # === Orchestrator Configuration (Phase 2) ===
    orchestrator_retry_delays: str = Field(
        default="0.5,1.0,2.0",
        description="Comma-separated retry delays in seconds for orchestrator",
    )

    # === UI Configuration (Phase 2) ===
    ui_context_update_throttle: float = Field(
        default=1.0,
        description="UI context update throttle in seconds",
        gt=0,
        le=10,
    )
    ui_tool_timeout_initial: int = Field(
        default=10,
        description="Initial tool timeout in seconds (first iteration)",
        gt=0,
        le=60,
    )
    ui_tool_timeout_subsequent: int = Field(
        default=8,
        description="Subsequent tool timeout in seconds",
        gt=0,
        le=60,
    )
    ui_tool_timeout_final: int = Field(
        default=5,
        description="Final tool timeout in seconds (last iterations)",
        gt=0,
        le=60,
    )

    # === Model Discovery (Phase 2) ===
    model_discovery_timeout: float = Field(
        default=10.0,
        description="HTTP timeout for model discovery in seconds",
        gt=0,
        le=60,
    )

    # === AWS Configuration ===
    aws_region: str | None = Field(
        default=None,
        alias="AWS_DEFAULT_REGION",
        description="AWS region for CloudWatch",
    )

    aws_access_key_id: str | None = Field(
        default=None,
        alias="AWS_ACCESS_KEY_ID",
        description="AWS access key ID",
    )

    aws_secret_access_key: str | None = Field(
        default=None,
        alias="AWS_SECRET_ACCESS_KEY",
        description="AWS secret access key",
    )

    aws_profile: str | None = Field(
        default=None,
        alias="AWS_PROFILE",
        description="AWS CLI profile to use",
    )

    # === Application Settings ===
    pii_sanitization_enabled: bool = Field(
        default=True,
        description="Enable PII sanitization before sending logs to LLM",
    )

    # === UI Settings ===
    log_groups_sidebar_visible: bool = Field(
        default=True,
        description="Show log groups sidebar by default at startup",
    )

    cache_dir: Path = Field(
        default_factory=lambda: Path.home() / ".logai" / "cache",
        description="Directory for cache storage",
    )

    cache_max_size_mb: int = Field(
        default=500,
        description="Maximum cache size in megabytes",
        gt=0,
        le=10000,
    )

    cache_ttl_seconds: int = Field(
        default=86400,  # 24 hours
        description="Cache TTL in seconds for historical logs",
        gt=0,
    )

    cache_max_entries: int = Field(
        default=10000,
        description="Maximum number of cache entries",
        gt=0,
    )

    cache_eviction_batch: int = Field(
        default=100,
        description="Number of entries to evict at once when cache is full",
        gt=0,
        le=1000,
    )

    cache_cleanup_interval: int = Field(
        default=300,
        description="Seconds between cache cleanup runs",
        gt=0,
    )

    # === Logging Configuration ===
    # Keep in sync with VALID_LOG_LEVELS in src/logai/cli.py
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="WARNING",
        description="Application log level (DEBUG, INFO, WARNING, ERROR)",
    )

    log_file: Path | None = Field(
        default=None,
        description="Optional log file path",
    )

    # === Agent Self-Direction Settings ===
    max_retry_attempts: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Maximum number of retry attempts for empty results",
    )

    intent_detection_enabled: bool = Field(
        default=True,
        description="Enable detection of stated intent without action",
    )

    auto_retry_enabled: bool = Field(
        default=True,
        description="Enable automatic retry on empty results",
    )

    time_expansion_factor: float = Field(
        default=4.0,
        description="Factor by which to expand time range on retry (e.g., 1h -> 4h)",
    )

    max_tool_iterations: int = Field(
        default=10,
        description="Maximum number of tool calls allowed in a single conversation turn. Prevents infinite loops.",
        ge=1,
        le=100,
    )

    # === Context Window Management ===
    context_window_size: int | None = Field(
        default=None,
        description="Model-specific context window size (auto-detected if None)",
        gt=0,
    )

    context_window_buffer: int = Field(
        default=5000,
        description="Safety margin for context window to prevent overflow",
        ge=0,
        le=50000,
    )

    max_result_tokens: int = Field(
        default=10000,
        description="Maximum tokens for a single tool result before caching",
        ge=1000,
        le=100000,
    )

    max_history_tokens: int = Field(
        default=80000,
        description="Maximum tokens for conversation history",
        ge=1000,
        le=200000,
    )

    max_system_prompt_tokens: int = Field(
        default=10000,
        description="Maximum tokens for system prompt",
        ge=1000,
        le=50000,
    )

    reserve_response_tokens: int = Field(
        default=8000,
        description="Tokens reserved for LLM response",
        ge=1000,
        le=20000,
    )

    emergency_prune_threshold: int = Field(
        default=5000,
        description="Trigger emergency pruning when remaining tokens below this value",
        ge=1000,
        le=20000,
    )

    # === Result Handling ===
    enable_result_caching: bool = Field(
        default=True,
        description="Enable caching of large tool results outside context window",
    )

    enable_incremental_fetch: bool = Field(
        default=True,
        description="Enable incremental fetching of cached results",
    )

    cache_large_results_threshold: int = Field(
        default=10000,
        description="Token threshold for caching tool results",
        ge=1000,
        le=100000,
    )

    max_events_per_chunk: int = Field(
        default=100,
        description="Configured maximum events per chunk fetch (intended ceiling for initial_chunk_size; not enforced as a hard cap by default)",
        ge=10,
        le=500,
    )

    cache_sample_event_count: int = Field(
        default=5,
        description="Number of sample events to include in cached result summary (range: 3-10)",
        ge=3,
        le=10,
    )

    # === History Management ===
    enable_history_pruning: bool = Field(
        default=True,
        description="Enable automatic pruning of old conversation history",
    )

    history_sliding_window_messages: int = Field(
        default=20,
        description="Number of recent messages to preserve when pruning history",
        ge=4,
        le=100,
    )

    enable_history_summarization: bool = Field(
        default=False,
        description="Enable summarization of pruned history (future feature)",
    )

    # === Cached result agent guidance settings ===
    enable_auto_fetch_guidance: bool = Field(
        default=True,
        description="Automatically guide agent to fetch cached result chunks",
    )

    initial_chunk_size: int = Field(
        default=25,
        ge=10,
        le=100,
        description="Default number of events in first chunk fetch",
    )

    max_auto_chunk_fetches: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum number of automatic chunk fetches per turn",
    )

    # === Context Allocation Strategy ===
    context_allocation_strategy: Literal["adaptive", "history-focused", "result-focused"] = Field(
        default="adaptive",
        description="Strategy for allocating context budget between history and results",
    )

    # === MCP (Model Context Protocol) Configuration ===
    use_mcp_tools: bool = Field(
        default=True,
        description=(
            "Use MCP server for CloudWatch tools instead of native boto3 tools. "
            "Defaults to True as of Phase 3 — set to False (or use --no-mcp) to "
            "fall back to the legacy native boto3 tools."
        ),
    )
    mcp_server_command: str = Field(
        default="uvx",
        description="Command used to launch the MCP server subprocess",
    )
    mcp_server_args: list[str] = Field(
        default_factory=lambda: ["awslabs.cloudwatch-mcp-server@latest"],
        description=(
            "Arguments passed to the MCP server launch command. "
            "When overriding via environment variable (LOGAI_MCP_SERVER_ARGS), "
            "the value must be a JSON array string, e.g. "
            '\'["awslabs.cloudwatch-mcp-server@latest", "--verbose"]\''
        ),
    )

    @field_validator("anthropic_api_key", "openai_api_key")
    @classmethod
    def validate_api_key_format(cls, v: str | None) -> str | None:
        """Validate API key format."""
        if v is not None and len(v.strip()) == 0:
            raise ValueError("API key cannot be empty string")
        return v

    @field_validator("cache_dir", "log_file")
    @classmethod
    def expand_path(cls, v: Path | None) -> Path | None:
        """Expand user home directory in paths."""
        if v is None:
            return None
        return Path(os.path.expanduser(str(v)))

    @model_validator(mode="after")
    def validate_retry_delays(self) -> "LogAISettings":
        """Validate cross-field constraints for retry delays."""
        if self.github_copilot_retry_max_delay < self.github_copilot_retry_base_delay:
            raise ValueError(
                "github_copilot_retry_max_delay must be >= github_copilot_retry_base_delay"
            )
        return self

    @model_validator(mode="after")
    def validate_chunk_size_ordering(self) -> "LogAISettings":
        """Validate that initial_chunk_size does not exceed max_events_per_chunk.

        A configuration where initial_chunk_size > max_events_per_chunk would be
        contradictory: the starting chunk is larger than the declared ceiling.
        """
        if self.initial_chunk_size > self.max_events_per_chunk:
            raise ValueError(
                f"initial_chunk_size ({self.initial_chunk_size}) must be <= "
                f"max_events_per_chunk ({self.max_events_per_chunk})"
            )
        return self

    def validate_required_credentials(self) -> None:
        """Validate that required credentials are present based on provider selection."""
        # Validate LLM credentials
        if self.llm_provider == "anthropic":
            if not self.anthropic_api_key:
                raise ValueError(
                    "LOGAI_ANTHROPIC_API_KEY is required when using Anthropic provider"
                )
        elif self.llm_provider == "openai":
            if not self.openai_api_key:
                raise ValueError("LOGAI_OPENAI_API_KEY is required when using OpenAI provider")
        elif self.llm_provider == "ollama":
            # Ollama doesn't need API key, but needs base URL
            if not self.ollama_base_url:
                raise ValueError("LOGAI_OLLAMA_BASE_URL is required when using Ollama provider")
            # No API key validation needed for local Ollama
        elif self.llm_provider == "github-copilot":
            # GitHub Copilot doesn't need API key - uses token from auth system
            # Token is retrieved via get_github_copilot_token() in the provider
            pass  # No validation needed here
        else:
            raise ValueError(f"Unsupported LLM provider: {self.llm_provider}")

        # Validate AWS credentials (either explicit or profile)
        if not self.aws_region:
            raise ValueError("AWS_DEFAULT_REGION is required for CloudWatch access")

        has_explicit_creds = self.aws_access_key_id and self.aws_secret_access_key
        has_profile = self.aws_profile

        if not (has_explicit_creds or has_profile):
            # Allow boto3 to try other credential sources (IAM role, etc.)
            # Just warn the user
            import warnings

            warnings.warn(
                "No explicit AWS credentials found. "
                "boto3 will attempt to use other credential sources "
                "(IAM role, instance profile, etc.)",
                UserWarning,
                stacklevel=2,
            )

    def ensure_cache_dir_exists(self) -> None:
        """Ensure cache directory exists."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @property
    def current_llm_api_key(self) -> str:
        """Get the API key for the currently selected LLM provider."""
        if self.llm_provider == "anthropic":
            return self.anthropic_api_key or ""
        elif self.llm_provider == "openai":
            return self.openai_api_key or ""
        elif self.llm_provider == "ollama":
            return ""  # Ollama doesn't need API key
        elif self.llm_provider == "github-copilot":
            return ""  # GitHub Copilot uses OAuth token, not API key
        raise ValueError(f"Unknown LLM provider: {self.llm_provider}")

    @property
    def current_llm_model(self) -> str:
        """Get the model name for the currently selected LLM provider."""
        if self.llm_provider == "anthropic":
            return self.anthropic_model
        elif self.llm_provider == "openai":
            return self.openai_model
        elif self.llm_provider == "ollama":
            return self.ollama_model
        elif self.llm_provider == "github-copilot":
            return self.github_copilot_model
        raise ValueError(f"Unknown LLM provider: {self.llm_provider}")

    @property
    def orchestrator_retry_delays_list(self) -> list[float]:
        """Parse orchestrator_retry_delays string into list of floats."""
        return [float(x.strip()) for x in self.orchestrator_retry_delays.split(",")]


# Global settings instance
_settings: LogAISettings | None = None


def get_settings() -> LogAISettings:
    """Get or create the global settings instance."""
    global _settings
    if _settings is None:
        _settings = LogAISettings()
    return _settings


def reload_settings() -> LogAISettings:
    """Reload settings from environment (useful for testing)."""
    global _settings
    _settings = LogAISettings()
    return _settings
