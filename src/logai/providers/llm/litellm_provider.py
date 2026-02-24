"""LiteLLM provider implementation for unified LLM access."""

import asyncio
import logging
import re
from collections.abc import AsyncGenerator
from typing import Any, NoReturn, cast

import litellm
from litellm.types.utils import Choices, ModelResponse

from logai.config.settings import LogAISettings

from .base import (
    AuthenticationError,
    BaseLLMProvider,
    InvalidRequestError,
    LLMProviderError,
    LLMResponse,
    RateLimitError,
)

# Suppress LiteLLM console logging - ensure logs only go to file
# This prevents debug logs from appearing in the TUI
# LiteLLM creates multiple loggers, all with default stderr handlers
for logger_name in ["LiteLLM", "LiteLLM Router", "LiteLLM Proxy"]:
    logger = logging.getLogger(logger_name)
    logger.handlers.clear()  # Remove default stderr handler
    logger.propagate = True  # Keep propagation for file logging

# Use LiteLLM's built-in suppression for extra safety
litellm.suppress_debug_info = True

# Register Ollama models with their tool calling capabilities
# Based on LiteLLM documentation: https://docs.litellm.ai/docs/providers/ollama
#
# Models WITH native tool calling support (as of Feb 2026):
# - Qwen 2.5/3 series: Native function calling support
# - Llama 3.1+: Native function calling support
# - Command-R (Cohere): Native function calling support
#
# Reasoning models WITHOUT native tool calling support:
# - OpenThinker: O1-style reasoning model (no native tool support)
# - DeepSeek-R1: O1-style reasoning model (no native tool support)
#
# Usage guidance:
# - For agentic tasks requiring tools: Use Qwen3, Llama 3.1, or Command-R
# - For pure reasoning tasks: Use DeepSeek-R1 or OpenThinker
#
# Note: If your model isn't listed, LiteLLM will fall back to JSON mode
# for tool calling, which may have reduced accuracy.
litellm.register_model(
    model_cost={
        "ollama_chat/qwen2.5": {"supports_function_calling": True},
        "ollama_chat/qwen3": {"supports_function_calling": True},
        "ollama_chat/llama3.1": {"supports_function_calling": True},
        "ollama_chat/llama3.2": {"supports_function_calling": True},
        "ollama_chat/command-r": {"supports_function_calling": True},
        "ollama_chat/openthinker": {"supports_function_calling": False},
        "ollama_chat/deepseek-r1": {"supports_function_calling": False},
    }
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
        api_base: str | None = None,
        num_ctx: int | None = None,
    ):
        """
        Initialize LiteLLM provider.

        Args:
            provider: Provider name ('anthropic', 'openai', or 'ollama')
            api_key: API key for the provider (empty string for Ollama)
            model: Model name (e.g., 'claude-3-5-sonnet-20241022', 'gpt-4-turbo-preview', 'llama3.1:8b')
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate (None for default)
            api_base: Base URL for API (used by Ollama)
            num_ctx: Ollama context window size. Overrides Ollama's default of 4096 tokens so that
                     the full prompt (including tool definitions) is never silently truncated.
        """
        self.provider = provider
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.api_base = api_base
        self.num_ctx = num_ctx

        # Set API key in environment for litellm
        if provider == "anthropic":
            litellm.api_key = api_key
        elif provider == "openai":
            litellm.openai_key = api_key
        # Ollama doesn't need API key to be set

    @classmethod
    def from_settings(cls, settings: LogAISettings) -> "BaseLLMProvider":
        """
        Create LLM provider from settings.

        Args:
            settings: Application settings

        Returns:
            Configured provider instance (LiteLLMProvider or GitHubCopilotProvider)
        """
        if settings.llm_provider == "anthropic":
            return cls(
                provider="anthropic",
                api_key=settings.anthropic_api_key or "",
                model=settings.anthropic_model,
            )
        elif settings.llm_provider == "openai":
            return cls(
                provider="openai",
                api_key=settings.openai_api_key or "",
                model=settings.openai_model,
            )
        elif settings.llm_provider == "ollama":
            return cls(
                provider="ollama",
                api_key="",  # Ollama doesn't need API key
                model=settings.ollama_model,
                api_base=settings.ollama_base_url,
                num_ctx=settings.ollama_num_ctx,
            )
        elif settings.llm_provider == "github-copilot":
            # Import here to avoid circular dependency
            from .github_copilot_provider import GitHubCopilotProvider

            return GitHubCopilotProvider(
                model=settings.github_copilot_model,
                api_base=settings.github_copilot_api_base,
                settings=settings,
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")

    def _supports_tools(self) -> bool:
        """Check if the current model supports tool calling."""
        if self.provider in ["anthropic", "openai"]:
            return True
        if self.provider == "ollama":
            # Check if model family is registered as supporting tools.
            # Use word-boundary regex so "qwen2.5" matches "ollama_chat/qwen2.5:7b"
            # but NOT a hypothetical "ollama_chat/notqwen2.5" variant.
            # Only models with native tool calling support are listed;
            # reasoning models (openthinker, deepseek-r1) are intentionally excluded.
            model_name = self._get_model_name()
            supported_families = [
                "qwen2.5",
                "qwen3",
                "llama3.1",
                "llama3.2",
                "mistral-nemo",
                "firefunction",
                "command-r",
            ]
            return any(
                re.search(rf"ollama_chat/{re.escape(family)}(?:[:/]|$)", model_name)
                for family in supported_families
            )
        return False

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
                "model": self._get_model_name(),
                "messages": messages,
                "temperature": kwargs.get("temperature", self.temperature),
            }

            # Add API base for Ollama
            if self.api_base:
                params["api_base"] = self.api_base

            # Only add API key if it's not empty (Ollama doesn't need it)
            if self.api_key:
                params["api_key"] = self.api_key

            if self.max_tokens:
                params["max_tokens"] = self.max_tokens

            # Pass num_ctx to Ollama to override the default 4096-token context window.
            # Without this, Ollama silently truncates prompts even when the model supports
            # a larger context window (e.g. qwen3:32b supports 32768 tokens).
            # IMPORTANT: num_ctx must be passed as a top-level kwarg to litellm.completion(),
            # NOT as options={"num_ctx": ...}. LiteLLM's Ollama handler only recognises
            # num_ctx when it arrives via optional_params (i.e. as a direct kwarg); an
            # "options" dict key is not in get_supported_openai_params and gets dropped.
            if self.provider == "ollama" and self.num_ctx:
                params["num_ctx"] = self.num_ctx

            # Only send tools if the model supports them
            if tools and self._supports_tools():
                params["tools"] = tools

            # Run litellm completion in executor (it's synchronous)
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, lambda: litellm.completion(**params))

            # Cast to ModelResponse for type checking
            response = cast(ModelResponse, response)

            # Extract response data
            choice = cast(Choices, response.choices[0])
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
            # Type cast needed because usage attribute may not be in type stubs
            usage_data = getattr(response, "usage", None)
            if usage_data:
                usage = {
                    "prompt_tokens": usage_data.prompt_tokens,
                    "completion_tokens": usage_data.completion_tokens,
                    "total_tokens": usage_data.total_tokens,
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
                "model": self._get_model_name(),
                "messages": messages,
                "temperature": kwargs.get("temperature", self.temperature),
                "stream": True,
            }

            # Add API base for Ollama
            if self.api_base:
                params["api_base"] = self.api_base

            # Only add API key if it's not empty (Ollama doesn't need it)
            if self.api_key:
                params["api_key"] = self.api_key

            if self.max_tokens:
                params["max_tokens"] = self.max_tokens

            # Pass num_ctx to Ollama to override the default 4096-token context window.
            # Without this, Ollama silently truncates prompts even when the model supports
            # a larger context window (e.g. qwen3:32b supports 32768 tokens).
            # IMPORTANT: num_ctx must be passed as a top-level kwarg to litellm.completion(),
            # NOT as options={"num_ctx": ...}. LiteLLM's Ollama handler only recognises
            # num_ctx when it arrives via optional_params (i.e. as a direct kwarg); an
            # "options" dict key is not in get_supported_openai_params and gets dropped.
            if self.provider == "ollama" and self.num_ctx:
                params["num_ctx"] = self.num_ctx

            # Only send tools if the model supports them
            if tools and self._supports_tools():
                params["tools"] = tools

            # Run litellm streaming in executor
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, lambda: litellm.completion(**params))

            # Stream tokens - response is a generator
            # Type cast needed because litellm.completion with stream=True returns a generator
            for chunk in cast(Any, response):
                # chunk is a ModelResponse with StreamingChoices
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if hasattr(delta, "content") and delta.content:
                        yield delta.content

        except Exception as e:
            self._handle_error(e)

    def _get_model_name(self) -> str:
        """
        Get the full model name for LiteLLM.

        Returns:
            Model name in the format expected by LiteLLM
        """
        if self.provider == "anthropic":
            return f"anthropic/{self.model}"
        elif self.provider == "openai":
            return f"openai/{self.model}"
        elif self.provider == "ollama":
            return f"ollama_chat/{self.model}"
        else:
            return self.model

    def _handle_error(self, error: Exception) -> NoReturn:
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
