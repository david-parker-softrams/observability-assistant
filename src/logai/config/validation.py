"""Validation functions for configuration values."""

import re
from pathlib import Path


def validate_api_key_format(api_key: str, provider: str) -> bool:
    """
    Validate API key format for given provider.

    Args:
        api_key: The API key to validate
        provider: The provider name ('anthropic' or 'openai')

    Returns:
        True if valid, False otherwise
    """
    if not api_key or not api_key.strip():
        return False

    if provider == "anthropic":
        # Anthropic keys start with 'sk-ant-'
        return api_key.startswith("sk-ant-") and len(api_key) > 20
    elif provider == "openai":
        # OpenAI keys start with 'sk-'
        return api_key.startswith("sk-") and len(api_key) > 20
    return False


def validate_aws_region(region: str) -> bool:
    """
    Validate AWS region format.

    Args:
        region: AWS region string

    Returns:
        True if valid, False otherwise
    """
    if not region:
        return False

    # AWS region format: us-east-1, eu-west-2, ap-southeast-1, etc.
    pattern = r"^[a-z]{2}-[a-z]+-\d+$"
    return bool(re.match(pattern, region))


def validate_path(path: str | Path) -> bool:
    """
    Validate that a path can be created/accessed.

    Args:
        path: Path to validate

    Returns:
        True if valid, False otherwise
    """
    try:
        p = Path(path).expanduser().resolve()
        # Check if parent exists or can be created
        if p.exists():
            return True
        # Check if parent directory exists
        return p.parent.exists() or p.parent == p
    except (ValueError, OSError):
        return False


def validate_cache_size(size_mb: int) -> bool:
    """
    Validate cache size is within reasonable bounds.

    Args:
        size_mb: Cache size in megabytes

    Returns:
        True if valid, False otherwise
    """
    return 1 <= size_mb <= 10000  # 1MB to 10GB


def validate_ttl(ttl_seconds: int) -> bool:
    """
    Validate TTL is within reasonable bounds.

    Args:
        ttl_seconds: TTL in seconds

    Returns:
        True if valid, False otherwise
    """
    # Minimum 1 minute, maximum 30 days
    return 60 <= ttl_seconds <= (30 * 24 * 60 * 60)
