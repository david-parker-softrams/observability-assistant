"""GitHub Copilot model management and discovery."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import aiofiles
import httpx

from logai.auth import get_github_copilot_token

# Static fallback model list (from Hans's investigation, Feb 2026)
DEFAULT_MODELS = [
    # Claude models
    "claude-haiku-4.5",
    "claude-sonnet-4",
    "claude-sonnet-4.5",
    "claude-opus-4.5",
    "claude-opus-4.6",
    "claude-opus-41",
    # OpenAI models
    "gpt-4.1",
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-5",
    "gpt-5-mini",
    "gpt-5.1",
    "gpt-5.1-codex",
    "gpt-5.1-codex-max",
    "gpt-5.1-codex-mini",
    "gpt-5.2",
    "gpt-5.2-codex",
    # Google models
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-3-flash-preview",
    "gemini-3-pro-preview",
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
    "claude-opus-41": {"provider": "anthropic", "supports_tools": True, "tier": "powerful"},
    # OpenAI models
    "gpt-4.1": {"provider": "openai", "supports_tools": True, "tier": "powerful"},
    "gpt-4o": {"provider": "openai", "supports_tools": True, "tier": "balanced"},
    "gpt-4o-mini": {"provider": "openai", "supports_tools": True, "tier": "fast"},
    "gpt-5": {"provider": "openai", "supports_tools": True, "tier": "powerful"},
    "gpt-5-mini": {"provider": "openai", "supports_tools": True, "tier": "fast"},
    "gpt-5.1": {"provider": "openai", "supports_tools": True, "tier": "powerful"},
    "gpt-5.1-codex": {"provider": "openai", "supports_tools": True, "tier": "powerful"},
    "gpt-5.1-codex-max": {"provider": "openai", "supports_tools": True, "tier": "powerful"},
    "gpt-5.1-codex-mini": {"provider": "openai", "supports_tools": True, "tier": "fast"},
    "gpt-5.2": {"provider": "openai", "supports_tools": True, "tier": "powerful"},
    "gpt-5.2-codex": {"provider": "openai", "supports_tools": True, "tier": "powerful"},
    # Google models
    "gemini-2.5-pro": {"provider": "google", "supports_tools": True, "tier": "powerful"},
    "gemini-2.5-flash": {"provider": "google", "supports_tools": True, "tier": "fast"},
    "gemini-3-flash-preview": {"provider": "google", "supports_tools": True, "tier": "fast"},
    "gemini-3-pro-preview": {"provider": "google", "supports_tools": True, "tier": "powerful"},
    # Other
    "grok-2-1212": {"provider": "xai", "supports_tools": True, "tier": "powerful"},
    "grok-code-fast-1": {"provider": "xai", "supports_tools": True, "tier": "fast"},
}

# Default model
DEFAULT_MODEL = "claude-opus-4.6"

# Cache configuration
CACHE_DURATION_HOURS = 24
CACHE_FILE_NAME = "github_copilot_models.json"


def get_cache_path() -> Path:
    """
    Get path to model cache file.

    Returns:
        Path to cache file in XDG data home
    """
    import os

    xdg_data_home = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))
    cache_dir = Path(xdg_data_home) / "logai"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / CACHE_FILE_NAME


def is_cache_valid(cache_path: Path) -> bool:
    """
    Check if cache file exists and is still valid (not expired).

    Args:
        cache_path: Path to cache file

    Returns:
        True if cache is valid and not expired, False otherwise
    """
    if not cache_path.exists():
        return False

    try:
        with open(cache_path, "r") as f:
            cache_data = json.load(f)

        cached_at = cache_data.get("cached_at", 0)
        cache_age_hours = (time.time() - cached_at) / 3600

        return cache_age_hours < CACHE_DURATION_HOURS
    except (json.JSONDecodeError, OSError, KeyError):
        return False


async def fetch_models_from_api() -> list[str] | None:
    """
    Fetch available models from GitHub Copilot API.

    This attempts to dynamically fetch the model list from the API.
    If the fetch fails, returns None to fall back to static list.

    Returns:
        List of model names if successful, None otherwise
    """
    token = get_github_copilot_token()
    if not token:
        # Not authenticated, can't fetch from API
        return None

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Note: This endpoint might not exist or might require different path
            # GitHub Copilot API may not expose a /models endpoint publicly
            # We'll try, but expect it might fail - that's why we have fallback
            response = await client.get(
                "https://api.githubcopilot.com/models",
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            )

            if response.status_code == 200:
                data = response.json()
                # Parse response - format might be:
                # {"data": [{"id": "claude-opus-4.6", ...}, ...]}
                # or just a list of model IDs
                if isinstance(data, dict) and "data" in data:
                    return [model.get("id") for model in data["data"] if model.get("id")]
                elif isinstance(data, list):
                    return [model if isinstance(model, str) else model.get("id") for model in data]
                else:
                    return None
            else:
                # API endpoint doesn't exist or returned error
                return None

    except Exception:
        # Network error, timeout, or other issue - fall back to static list
        return None


async def get_available_models(force_refresh: bool = False) -> list[str]:
    """
    Get list of available GitHub Copilot models.

    This function implements the dynamic model fetching with caching strategy:
    1. Check cache if not forcing refresh
    2. Try to fetch from API
    3. Fall back to static list if fetch fails

    Args:
        force_refresh: Force refresh from API, ignore cache

    Returns:
        List of available model names (without github-copilot/ prefix)
    """
    cache_path = get_cache_path()

    # Check cache first (unless forcing refresh)
    if not force_refresh and is_cache_valid(cache_path):
        try:
            with open(cache_path, "r") as f:
                cache_data = json.load(f)
                models = cache_data.get("models", [])
                if models:
                    return models
        except (json.JSONDecodeError, OSError):
            pass

    # Try to fetch from API
    api_models = await fetch_models_from_api()

    if api_models:
        # Success! Cache the results
        try:
            cache_data = {"models": api_models, "cached_at": time.time(), "source": "api"}

            async with aiofiles.open(cache_path, "w") as f:
                await f.write(json.dumps(cache_data, indent=2))

            return api_models
        except OSError:
            # Cache write failed, but we have data
            return api_models

    # Fall back to static list
    # Also cache it so we don't keep trying the API
    try:
        cache_data = {"models": DEFAULT_MODELS, "cached_at": time.time(), "source": "static"}

        async with aiofiles.open(cache_path, "w") as f:
            await f.write(json.dumps(cache_data, indent=2))
    except OSError:
        pass

    return DEFAULT_MODELS


def get_available_models_sync() -> list[str]:
    """
    Synchronous version of get_available_models.

    Uses cached data if available, otherwise returns static list.
    Does not attempt to fetch from API (use async version for that).

    Returns:
        List of available model names
    """
    cache_path = get_cache_path()

    # Check cache
    if is_cache_valid(cache_path):
        try:
            with open(cache_path, "r") as f:
                cache_data = json.load(f)
                models = cache_data.get("models", [])
                if models:
                    return models
        except (json.JSONDecodeError, OSError):
            pass

    # Return static list
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

    available = get_available_models_sync()
    return model in available


def get_model_metadata(model: str) -> dict[str, Any]:
    """
    Get metadata for a specific model.

    Args:
        model: Model name (without github-copilot/ prefix)

    Returns:
        Dictionary with model metadata (provider, supports_tools, tier)
        Returns default metadata if model is unknown
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


async def refresh_model_cache() -> list[str]:
    """
    Force refresh the model cache from API.

    This is useful for CLI commands like `logai models --refresh`.

    Returns:
        Updated list of available models
    """
    return await get_available_models(force_refresh=True)
