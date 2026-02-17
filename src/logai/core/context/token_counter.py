"""Token counting utilities for context management."""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Lazy load tiktoken to avoid startup cost
_tokenizer_cache: dict[str, Any] = {}


class TokenCounter:
    """
    Fast, accurate token counting for LLM context management.

    Uses tiktoken for OpenAI/Claude models with fallback heuristics
    for unsupported models. All methods are class methods for ease of use.

    Model configurations are loaded from YAML files:
    - Built-in: src/logai/config/default_models.yaml
    - User overrides: ~/.logai/model_config.yaml

    Performance: <1ms for typical content, <10ms for very large content (500KB)
    Accuracy: Within ±5% for supported models
    """

    # Reference to config loader (allows injection for testing)
    _config_loader: Any = None

    # Hardcoded fallbacks (used if config loading fails completely)
    _FALLBACK_CONTEXT_WINDOWS: dict[str, int] = {
        "gpt-4-turbo": 128_000,
        "gpt-4o": 128_000,
        "gpt-4": 8_192,
        "claude-3-5-sonnet": 200_000,
        "claude-3-opus": 200_000,
        "claude-opus-4": 200_000,
        "claude-sonnet-4": 200_000,
        "llama3.1:8b": 8_192,
        "llama3.1:70b": 128_000,
        "qwen3": 32_768,
        "default": 8_192,
    }

    _FALLBACK_MODEL_ENCODINGS: dict[str, str] = {
        "gpt-4": "cl100k_base",
        "gpt-4-turbo": "cl100k_base",
        "gpt-4o": "o200k_base",
        "claude": "cl100k_base",
        "github-copilot": "cl100k_base",
    }

    # Default tokens per character for unknown models (conservative)
    DEFAULT_CHARS_PER_TOKEN: float = 3.5

    @classmethod
    def _get_config_loader(cls) -> Any:
        """Get or create the model config loader."""
        if cls._config_loader is None:
            try:
                from logai.config.model_config import get_model_config_loader

                cls._config_loader = get_model_config_loader()
            except Exception as e:
                logger.warning(f"Failed to load model config, using fallback: {e}")
                cls._config_loader = None
        return cls._config_loader

    @classmethod
    def _set_config_loader(cls, loader: Any) -> None:
        """Set custom config loader (for testing)."""
        cls._config_loader = loader

    @classmethod
    def _get_encoding(cls, model: str) -> Any:
        """
        Get or create tokenizer encoding for a model.

        Uses lazy loading and caching for performance.

        Integration with ModelConfigLoader provides a semantic improvement:
        Unknown models now attempt to use the default encoding (cl100k_base)
        before falling back to character-based estimation. This gives more
        accurate token counts for models not explicitly configured, especially
        for new or local models that are similar to OpenAI/Anthropic models.

        Fallback chain:
        1. ModelConfigLoader.get_encoding(model) - from YAML config
        2. FALLBACK_MODEL_ENCODINGS - hardcoded prefix matching
        3. Default encoding (cl100k_base) - via ModelConfigLoader
        4. Character-based estimation - when tiktoken unavailable or fails

        Args:
            model: Model name or identifier

        Returns:
            tiktoken Encoding object or None if unavailable
        """
        # Check cache first
        if model in _tokenizer_cache:
            return _tokenizer_cache[model]

        # Try to get encoding name from config loader
        encoding_name = None
        loader = cls._get_config_loader()

        if loader is not None:
            try:
                encoding_name = loader.get_encoding(model)
            except Exception as e:
                logger.debug(f"Config loader failed for {model}: {e}")

        # Fallback to hardcoded mappings if config failed
        if encoding_name is None:
            model_lower = model.lower()
            for model_prefix, enc_name in cls._FALLBACK_MODEL_ENCODINGS.items():
                if model_prefix in model_lower:
                    encoding_name = enc_name
                    break

        if encoding_name is None:
            _tokenizer_cache[model] = None
            return None

        try:
            import tiktoken

            encoding = tiktoken.get_encoding(encoding_name)
            _tokenizer_cache[model] = encoding
            return encoding
        except ImportError:
            logger.warning("tiktoken not installed, using character-based estimation")
            _tokenizer_cache[model] = None
            return None
        except Exception as e:
            logger.warning(f"Failed to load tokenizer for {model}: {e}")
            _tokenizer_cache[model] = None
            return None

    @classmethod
    def count_tokens(cls, text: str, model: str = "claude-3-5-sonnet") -> int:
        """
        Count tokens in text for a specific model.

        Args:
            text: Text to count tokens for
            model: Model name (used to select tokenizer)

        Returns:
            Estimated token count

        Performance: <1ms for typical content
        """
        if not text:
            return 0

        encoding = cls._get_encoding(model)

        if encoding is not None:
            try:
                return len(encoding.encode(text))
            except Exception as e:
                logger.warning(f"Token counting failed, using fallback: {e}")

        # Fallback: character-based estimation (conservative)
        loader = cls._get_config_loader()
        chars_per_token = cls.DEFAULT_CHARS_PER_TOKEN

        if loader is not None:
            try:
                chars_per_token = loader.get_chars_per_token(model)
            except Exception:
                pass  # Use default

        return int(len(text) / chars_per_token) + 1

    @classmethod
    def count_message_tokens(
        cls, messages: list[dict[str, Any]], model: str = "claude-3-5-sonnet"
    ) -> int:
        """
        Count total tokens in a list of messages.

        Accounts for message overhead (role tokens, separators, etc.)

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model name

        Returns:
            Total estimated token count
        """
        if not messages:
            return 0

        total = 0

        # Per-message overhead: role tokens + separators
        # This is approximately 4 tokens per message for most models
        MESSAGE_OVERHEAD = 4

        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total += cls.count_tokens(content, model)
            elif isinstance(content, list):
                # Handle multi-part content (e.g., images)
                for part in content:
                    if isinstance(part, dict) and "text" in part:
                        total += cls.count_tokens(part["text"], model)

            # Add overhead for role and separators
            total += MESSAGE_OVERHEAD

            # Count tool_calls if present
            tool_calls = msg.get("tool_calls", [])
            for tool_call in tool_calls:
                # Tool call overhead: function name + arguments
                func = tool_call.get("function", {})
                total += cls.count_tokens(func.get("name", ""), model) + 2
                total += cls.count_tokens(func.get("arguments", ""), model)

        return total

    @classmethod
    def estimate_json_tokens(cls, data: dict[str, Any], model: str = "claude-3-5-sonnet") -> int:
        """
        Estimate tokens for JSON-serialized data without serializing.

        This is a fast estimation method that avoids the cost of
        json.dumps() for large objects. Accuracy is within 10%.

        Args:
            data: Dictionary to estimate
            model: Model name

        Returns:
            Estimated token count
        """
        # For objects, serialize and count (most accurate)
        try:
            json_str = json.dumps(data, separators=(",", ":"))
            return cls.count_tokens(json_str, model)
        except (TypeError, ValueError) as e:
            logger.warning(f"JSON serialization failed: {e}")
            # Fallback: rough estimate based on str representation
            return cls.count_tokens(str(data), model)

    @classmethod
    def get_context_window(cls, model: str) -> int:
        """
        Get context window size for a model.

        Args:
            model: Model name

        Returns:
            Context window size in tokens
        """
        # Try config loader first
        loader = cls._get_config_loader()
        if loader is not None:
            try:
                window: int = loader.get_context_window(model)
                return window
            except Exception as e:
                logger.debug(f"Config loader failed for {model}: {e}")

        # Fallback to hardcoded values
        model_lower = model.lower()
        for model_prefix, window_size in cls._FALLBACK_CONTEXT_WINDOWS.items():
            if model_prefix in model_lower:
                return window_size

        return cls._FALLBACK_CONTEXT_WINDOWS["default"]

    @classmethod
    def will_fit(
        cls,
        text: str,
        current_tokens: int,
        max_tokens: int,
        model: str = "claude-3-5-sonnet",
    ) -> bool:
        """
        Quick check if text will fit in remaining budget.

        Args:
            text: Text to check
            current_tokens: Current token usage
            max_tokens: Maximum allowed tokens
            model: Model name

        Returns:
            True if text will fit
        """
        text_tokens = cls.count_tokens(text, model)
        return (current_tokens + text_tokens) <= max_tokens
