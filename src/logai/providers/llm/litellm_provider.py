"""LiteLLM provider implementation for unified LLM access."""

import asyncio
from typing import Any, AsyncGenerator

import litellm

from logai.config.settings import LogAISettings

from .base import (
    AuthenticationError,
    BaseLLMProvider,
    InvalidRequestError,
    LLMProviderError,
    LLMResponse,
    RateLimitError,
)


class LiteLLMProvider(BaseLLMProvider):
    """
    LiteLLM provider implementation.

    Uses the LiteLLM library to provide a unified interface to multiple LLM providers
    (Anthropic Claude, OpenAI GPT, etc.) with consistent function calling support.
    """

    def __init__(
        self,
        provider: str,
        api_key: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ):
        """
        Initialize LiteLLM provider.

        Args:
            provider: Provider name ('anthropic' or 'openai')
            api_key: API key for the provider
            model: Model name (e.g., 'claude-3-5-sonnet-20241022', 'gpt-4-turbo-preview')
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate (None for default)
        """
        self.provider = provider
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

        # Set API key in environment for litellm
        if provider == "anthropic":
            litellm.api_key = api_key
        elif provider == "openai":
            litellm.openai_key = api_key

    @classmethod
    def from_settings(cls, settings: LogAISettings) -> "LiteLLMProvider":
        """
        Create LiteLLM provider from settings.

        Args:
            settings: Application settings

        Returns:
            Configured LiteLLMProvider instance
        """
        return cls(
            provider=settings.llm_provider,
            api_key=settings.current_llm_api_key,
            model=settings.current_llm_model,
        )

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> LLMResponse | AsyncGenerator[str, None]:
        """
        Send chat messages to the LLM.

        Args:
            messages: List of message dictionaries
            tools: Optional tool definitions
            stream: Whether to stream the response
            **kwargs: Additional parameters

        Returns:
            LLMResponse or AsyncGenerator if streaming

        Raises:
            LLMProviderError: If request fails
        """
        if stream:
            return self.stream_chat(messages=messages, tools=tools, **kwargs)

        try:
            # Prepare litellm parameters
            params: dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "temperature": kwargs.get("temperature", self.temperature),
            }

            if self.max_tokens:
                params["max_tokens"] = self.max_tokens

            if tools:
                params["tools"] = tools

            # Run litellm completion in executor (it's synchronous)
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, lambda: litellm.completion(**params))

            # Extract response data
            choice = response.choices[0]
            content = choice.message.content if hasattr(choice.message, "content") else None
            finish_reason = choice.finish_reason

            # Extract tool calls if present
            tool_calls = []
            if hasattr(choice.message, "tool_calls") and choice.message.tool_calls:
                for tc in choice.message.tool_calls:
                    tool_calls.append(
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                    )

            # Extract usage information
            usage = {}
            if hasattr(response, "usage") and response.usage:
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }

            return LLMResponse(
                content=content,
                tool_calls=tool_calls,
                finish_reason=finish_reason,
                usage=usage,
            )

        except Exception as e:
            self._handle_error(e)

    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat response token by token.

        Args:
            messages: List of message dictionaries
            tools: Optional tool definitions
            **kwargs: Additional parameters

        Yields:
            Response tokens

        Raises:
            LLMProviderError: If request fails
        """
        try:
            # Prepare litellm parameters
            params: dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "temperature": kwargs.get("temperature", self.temperature),
                "stream": True,
            }

            if self.max_tokens:
                params["max_tokens"] = self.max_tokens

            if tools:
                params["tools"] = tools

            # Run litellm streaming in executor
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, lambda: litellm.completion(**params))

            # Stream tokens
            for chunk in response:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if hasattr(delta, "content") and delta.content:
                        yield delta.content

        except Exception as e:
            self._handle_error(e)

    def _handle_error(self, error: Exception) -> None:
        """
        Handle and convert litellm errors to our error types.

        Args:
            error: Exception from litellm

        Raises:
            Appropriate LLMProviderError subclass
        """
        error_str = str(error)
        error_type = type(error).__name__

        # Check for authentication errors
        if any(
            phrase in error_str.lower()
            for phrase in ["authentication", "api key", "unauthorized", "invalid_api_key"]
        ):
            raise AuthenticationError(
                message=f"Authentication failed: {error_str}",
                provider=self.provider,
                error_code="auth_error",
                details={"original_error": error_type},
            ) from error

        # Check for rate limit errors
        if any(
            phrase in error_str.lower() for phrase in ["rate limit", "too many requests", "429"]
        ):
            raise RateLimitError(
                message=f"Rate limit exceeded: {error_str}",
                provider=self.provider,
                error_code="rate_limit",
                details={"original_error": error_type},
            ) from error

        # Check for invalid request errors
        if any(
            phrase in error_str.lower()
            for phrase in [
                "invalid request",
                "bad request",
                "400",
                "invalid parameter",
                "validation error",
            ]
        ):
            raise InvalidRequestError(
                message=f"Invalid request: {error_str}",
                provider=self.provider,
                error_code="invalid_request",
                details={"original_error": error_type},
            ) from error

        # Generic LLM provider error
        raise LLMProviderError(
            message=f"LLM request failed: {error_str}",
            provider=self.provider,
            error_code="unknown_error",
            details={"original_error": error_type},
        ) from error
