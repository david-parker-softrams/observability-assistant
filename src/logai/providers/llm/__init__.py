"""LLM provider abstractions and implementations."""

from .base import (
    AuthenticationError,
    BaseLLMProvider,
    InvalidRequestError,
    LLMProviderError,
    LLMResponse,
    RateLimitError,
)
from .github_copilot_models import (
    get_available_models,
    get_model_metadata,
    refresh_model_cache,
    validate_model,
)
from .github_copilot_provider import GitHubCopilotProvider
from .litellm_provider import LiteLLMProvider

__all__ = [
    # Base classes and types
    "BaseLLMProvider",
    "LLMResponse",
    "LLMProviderError",
    "RateLimitError",
    "AuthenticationError",
    "InvalidRequestError",
    # Provider implementations
    "LiteLLMProvider",
    "GitHubCopilotProvider",
    # GitHub Copilot model utilities
    "get_available_models",
    "validate_model",
    "get_model_metadata",
    "refresh_model_cache",
]
