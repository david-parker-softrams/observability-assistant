"""Configuration settings for LogAI using Pydantic Settings."""

import os
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
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

    # === GitHub Copilot Configuration ===
    github_copilot_model: str = Field(
        default="claude-opus-4.5",
        description="GitHub Copilot model to use",
    )

    github_copilot_api_base: str = Field(
        default="https://api.githubcopilot.com/chat/completions",
        description="GitHub Copilot API endpoint URL",
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

    # === Logging Configuration ===
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="Application log level",
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
        default=50000,
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
        description="Maximum events to return in a single cached result chunk",
        ge=10,
        le=500,
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

    # === Context Allocation Strategy ===
    context_allocation_strategy: Literal["adaptive", "history-focused", "result-focused"] = Field(
        default="adaptive",
        description="Strategy for allocating context budget between history and results",
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
