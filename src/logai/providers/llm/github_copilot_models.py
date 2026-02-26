"""GitHub Copilot model management."""

from __future__ import annotations

from typing import Any

# Static model list — current as of Feb 2026.
# Update this list when Anthropic, OpenAI, Google, or xAI release new models
# on the GitHub Copilot platform.
DEFAULT_MODELS = [
    # Claude models (Anthropic)
    "claude-haiku-4.5",
    "claude-sonnet-4",
    "claude-sonnet-4.5",
    "claude-opus-4.5",
    "claude-opus-4.6",
    # OpenAI models
    "gpt-4.1",
    "gpt-4o",
    "gpt-4o-mini",
    # Google models
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    # Other
    "grok-2-1212",
    "grok-code-fast-1",
]

# Model metadata for known models
MODEL_METADATA: dict[str, dict[str, Any]] = {
    # Claude models
    "claude-haiku-4.5": {"provider": "anthropic", "supports_tools": True, "tier": "fast"},
    "claude-sonnet-4": {"provider": "anthropic", "supports_tools": True, "tier": "balanced"},
    "claude-sonnet-4.5": {"provider": "anthropic", "supports_tools": True, "tier": "balanced"},
    "claude-opus-4.5": {"provider": "anthropic", "supports_tools": True, "tier": "powerful"},
    "claude-opus-4.6": {"provider": "anthropic", "supports_tools": True, "tier": "powerful"},
    # OpenAI models
    "gpt-4.1": {"provider": "openai", "supports_tools": True, "tier": "powerful"},
    "gpt-4o": {"provider": "openai", "supports_tools": True, "tier": "balanced"},
    "gpt-4o-mini": {"provider": "openai", "supports_tools": True, "tier": "fast"},
    # Google models
    "gemini-2.5-pro": {"provider": "google", "supports_tools": True, "tier": "powerful"},
    "gemini-2.5-flash": {"provider": "google", "supports_tools": True, "tier": "fast"},
    # Other
    "grok-2-1212": {"provider": "xai", "supports_tools": True, "tier": "powerful"},
    "grok-code-fast-1": {"provider": "xai", "supports_tools": True, "tier": "fast"},
}

# Default model — keep in sync with `github_copilot_model` default in settings.py
DEFAULT_MODEL = "gpt-4o-mini"


def get_available_models() -> list[str]:
    """
    Get the list of available GitHub Copilot models.

    Returns the static model list.  The previous implementation attempted a
    live fetch from an API endpoint that doesn't reliably exist, always falling
    back to this same list — so the async machinery has been removed.

    Returns:
        List of available model names (without github-copilot/ prefix)
    """
    return DEFAULT_MODELS


def refresh_model_cache() -> list[str]:
    """
    Return the current model list.

    Previously forced a refresh from the API; now simply returns the static
    list since the API endpoint was unconfirmed and the function always fell
    back to the static list anyway.

    Returns:
        List of available model names (without github-copilot/ prefix)
    """
    return DEFAULT_MODELS


def validate_model(model: str) -> bool:
    """
    Validate that a model name is in the known list.

    Args:
        model: Model name (without github-copilot/ prefix)

    Returns:
        True if model is known, False otherwise
    """
    # Strip prefix if present
    if model.startswith("github-copilot/"):
        model = model[len("github-copilot/") :]

    return model in get_available_models()


def get_model_metadata(model: str) -> dict[str, Any]:
    """
    Get metadata for a specific model.

    Args:
        model: Model name (without github-copilot/ prefix)

    Returns:
        Dictionary with model metadata (provider, supports_tools, tier).
        Returns sensible defaults if the model is not in the known list.
    """
    # Strip prefix if present
    if model.startswith("github-copilot/"):
        model = model[len("github-copilot/") :]

    return MODEL_METADATA.get(
        model,
        {
            "provider": "unknown",
            "supports_tools": True,  # Assume true for unknown models
            "tier": "unknown",
        },
    )
