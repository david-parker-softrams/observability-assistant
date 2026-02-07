"""Pytest configuration and shared fixtures."""

import os
from pathlib import Path
from typing import Any, Generator

import pytest


@pytest.fixture
def clean_env() -> Generator[None, None, None]:
    """Clean environment variables before and after test."""
    # Save original environment
    original_env = os.environ.copy()

    # Clear LogAI and AWS environment variables
    env_prefixes = ["LOGAI_", "AWS_"]
    for key in list(os.environ.keys()):
        if any(key.startswith(prefix) for prefix in env_prefixes):
            del os.environ[key]

    yield

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def sample_env_vars() -> dict[str, str]:
    """Sample environment variables for testing."""
    return {
        "LOGAI_LLM_PROVIDER": "anthropic",
        "LOGAI_ANTHROPIC_API_KEY": "sk-ant-test-key-12345678901234567890",
        "LOGAI_OPENAI_API_KEY": "sk-test-openai-key-12345678901234567890",
        "AWS_DEFAULT_REGION": "us-east-1",
        "AWS_ACCESS_KEY_ID": "AKIAIOSFODNN7EXAMPLE",
        "AWS_SECRET_ACCESS_KEY": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        "LOGAI_PII_SANITIZATION_ENABLED": "true",
        "LOGAI_CACHE_MAX_SIZE_MB": "500",
    }


@pytest.fixture
def set_env_vars(sample_env_vars: dict[str, str]) -> Generator[dict[str, str], None, None]:
    """Set sample environment variables for testing."""
    for key, value in sample_env_vars.items():
        os.environ[key] = value
    yield sample_env_vars
    # Cleanup is handled by clean_env fixture


@pytest.fixture
def temp_cache_dir(tmp_path: Path) -> Path:
    """Create a temporary cache directory."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return cache_dir
