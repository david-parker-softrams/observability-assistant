"""Base class for LLM providers."""

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from typing import Any


class LLMResponse:
    """Represents a response from an LLM provider."""

    def __init__(
        self,
        content: str | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
        finish_reason: str | None = None,
        usage: dict[str, int] | None = None,
    ):
        """
        Initialize LLM response.

        Args:
            content: Text content of the response
            tool_calls: List of tool/function calls requested by the LLM
            finish_reason: Reason the LLM stopped generating (e.g., 'stop', 'tool_calls')
            usage: Token usage information
        """
        self.content = content
        self.tool_calls = tool_calls or []
        self.finish_reason = finish_reason
        self.usage = usage or {}

    def has_tool_calls(self) -> bool:
        """Check if the response contains tool calls."""
        return len(self.tool_calls) > 0


class BaseLLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    Providers implement this interface to support different LLM services
    (Anthropic Claude, OpenAI GPT, AWS Bedrock, etc.).
    """

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> LLMResponse | AsyncGenerator[str, None]:
        """
        Send chat messages to the LLM and get a response.

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            tools: Optional list of tool/function definitions for function calling
            stream: Whether to stream the response token by token
            **kwargs: Additional provider-specific parameters

        Returns:
            LLMResponse object if not streaming, AsyncGenerator of tokens if streaming

        Raises:
            LLMProviderError: If the LLM request fails
        """
        pass

    @abstractmethod
    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat response token by token.

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            tools: Optional list of tool/function definitions for function calling
            **kwargs: Additional provider-specific parameters

        Yields:
            Response tokens as they become available

        Raises:
            LLMProviderError: If the LLM request fails
        """
        # This is an async generator, must yield
        if False:  # pragma: no cover
            yield


class LLMProviderError(Exception):
    """Base exception for LLM provider errors."""

    def __init__(
        self,
        message: str,
        provider: str | None = None,
        error_code: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        """
        Initialize LLM provider error.

        Args:
            message: Error message
            provider: Name of the provider (e.g., 'anthropic', 'openai')
            error_code: Provider-specific error code
            details: Additional error details
        """
        self.message = message
        self.provider = provider
        self.error_code = error_code
        self.details = details or {}
        super().__init__(f"LLM Provider Error ({provider}): {message}")


class RateLimitError(LLMProviderError):
    """Raised when the LLM provider rate limit is exceeded."""

    pass


class AuthenticationError(LLMProviderError):
    """Raised when authentication with the LLM provider fails."""

    pass


class InvalidRequestError(LLMProviderError):
    """Raised when the request to the LLM provider is invalid."""

    pass
