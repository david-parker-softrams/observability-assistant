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
    llm_provider: Literal["anthropic", "openai"] = Field(
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
        raise ValueError(f"Unknown LLM provider: {self.llm_provider}")

    @property
    def current_llm_model(self) -> str:
        """Get the model name for the currently selected LLM provider."""
        if self.llm_provider == "anthropic":
            return self.anthropic_model
        elif self.llm_provider == "openai":
            return self.openai_model
        raise ValueError(f"Unknown LLM provider: {self.llm_provider}")


# Global settings instance
_settings: LogAISettings | None = None


def get_settings() -> LogAISettings:
    """Get or create the global settings instance."""
    global _settings
    if _settings is None:
        _settings = LogAISettings()  # type: ignore
    return _settings


def reload_settings() -> LogAISettings:
    """Reload settings from environment (useful for testing)."""
    global _settings
    _settings = LogAISettings()  # type: ignore
    return _settings
