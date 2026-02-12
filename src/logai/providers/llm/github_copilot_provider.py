"""GitHub Copilot LLM provider implementation."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

import httpx

from logai.auth import get_github_copilot_token

from .base import (
    AuthenticationError,
    BaseLLMProvider,
    InvalidRequestError,
    LLMProviderError,
    LLMResponse,
    RateLimitError,
)
from .github_copilot_models import (
    DEFAULT_MODEL,
    get_available_models_sync,
    get_model_metadata,
    validate_model,
)

# Logger for retry operations
logger = logging.getLogger(__name__)


class GitHubCopilotProvider(BaseLLMProvider):
    """
    GitHub Copilot LLM provider.

    Provides access to 24+ models through the GitHub Copilot API,
    including Claude, GPT, Gemini, and Grok models.

    The API is OpenAI-compatible, making request/response handling straightforward.

    Example:
        ```python
        provider = GitHubCopilotProvider(model="claude-opus-4.6")
        response = await provider.chat([
            {"role": "user", "content": "What is 2+2?"}
        ])
        print(response.content)
        ```

    Authentication:
        Uses token from `logai auth login`. Automatically retrieves token
        via `get_github_copilot_token()` function. If not authenticated,
        raises AuthenticationError with instructions to run `logai auth login`.
    """

    # GitHub Copilot API endpoint
    API_ENDPOINT = "https://api.githubcopilot.com/chat/completions"

    # Retry configuration for handling temporary 403 errors
    # GitHub Copilot API sometimes returns 403 for rate limiting instead of 429
    MAX_RETRIES = 3  # Total of 4 attempts (1 original + 3 retries)
    RETRY_BASE_DELAY = 1.0  # Initial delay in seconds
    RETRY_MAX_DELAY = 8.0  # Maximum delay in seconds

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        api_base: str | None = None,
        timeout: float = 120.0,
    ):
        """
        Initialize GitHub Copilot provider.

        Args:
            model: Model name (with or without github-copilot/ prefix)
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate (None for model default)
            api_base: Override API base URL (for testing)
            timeout: Request timeout in seconds
        """
        # Strip provider prefix if present (API expects model name without prefix)
        if model.startswith("github-copilot/"):
            model = model[len("github-copilot/") :]

        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._api_base = api_base or self.API_ENDPOINT
        self._timeout = timeout

        # HTTP client (created on first use)
        self._http_client: httpx.AsyncClient | None = None

        # Validate model if possible (won't fail if validation can't be done)
        if not validate_model(model):
            # Model not in our known list - but might still work
            # Log a warning but don't fail (could be a new model)
            pass

    @classmethod
    def from_settings(cls, settings: Any) -> GitHubCopilotProvider:
        """
        Create provider from LogAI settings.

        Args:
            settings: LogAI settings instance with github_copilot_* fields

        Returns:
            Configured GitHubCopilotProvider instance
        """
        return cls(
            model=getattr(settings, "github_copilot_model", DEFAULT_MODEL),
            temperature=getattr(settings, "github_copilot_temperature", 0.7),
            max_tokens=getattr(settings, "github_copilot_max_tokens", None),
        )

    @classmethod
    def get_available_models(cls) -> list[str]:
        """
        Get list of available models (synchronous).

        Returns:
            List of model names (without github-copilot/ prefix)
        """
        return get_available_models_sync()

    @property
    def full_model_name(self) -> str:
        """Get full model name with provider prefix."""
        return f"github-copilot/{self.model}"

    def _supports_tools(self) -> bool:
        """
        Check if current model supports tool calling.

        Returns:
            True if model supports tools, False otherwise
        """
        metadata = get_model_metadata(self.model)
        supports: bool = metadata.get("supports_tools", True)
        return supports

    async def _get_http_client(self) -> httpx.AsyncClient:
        """
        Get or create async HTTP client.

        Returns:
            Configured AsyncClient instance
        """
        if self._http_client is None:
            # Note: httpx adds default headers (Accept, User-Agent, etc.) automatically
            # GitHub Copilot API requires Copilot-Integration-Id and Editor-Version headers
            # These are added per-request to identify the client application
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout, connect=10.0),
            )
        return self._http_client

    async def close(self) -> None:
        """Close HTTP client and release resources."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    def _get_auth_token(self) -> str:
        """
        Get authentication token or raise error.

        Returns:
            GitHub Copilot access token

        Raises:
            AuthenticationError: If not authenticated
        """
        token = get_github_copilot_token()
        if not token:
            raise AuthenticationError(
                message=(
                    "Not authenticated with GitHub Copilot. Run 'logai auth login' to authenticate."
                ),
                provider="github-copilot",
                error_code="not_authenticated",
            )
        return token

    def _format_request(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Format request body for GitHub Copilot API.

        API format is OpenAI-compatible.

        Args:
            messages: List of message dictionaries
            tools: Optional tool definitions
            stream: Whether to stream the response
            **kwargs: Additional parameters

        Returns:
            Request body dictionary
        """
        body: dict[str, Any] = {
            "model": self.model,  # Send without prefix
            "messages": messages,
        }

        # GitHub Copilot API has strict parameter requirements:
        # - Does NOT support: temperature, max_tokens (cause 403 Forbidden)
        # - stream parameter: only add if streaming (stream=True)
        #   Setting stream=False explicitly causes 403 errors
        #   Omit the parameter entirely for non-streaming requests
        if stream:
            body["stream"] = True

        # Add tools if model supports them and tools are provided
        if tools and self._supports_tools():
            body["tools"] = tools

        return body

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> LLMResponse | AsyncGenerator[str, None]:
        """
        Send chat messages to GitHub Copilot API.

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            tools: Optional tool definitions for function calling
            stream: Whether to stream the response
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            LLMResponse if not streaming, AsyncGenerator[str, None] if streaming

        Raises:
            AuthenticationError: If not authenticated or token is invalid
            RateLimitError: If rate limited by API
            InvalidRequestError: If request format is invalid
            LLMProviderError: For other errors
        """
        if stream:
            return self.stream_chat(messages=messages, tools=tools, **kwargs)

        # Retry loop for handling intermittent 403 errors
        last_exception: Exception | None = None

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                token = self._get_auth_token()
                client = await self._get_http_client()

                # Build request
                body = self._format_request(messages=messages, tools=tools, stream=False, **kwargs)

                # Make API request
                response = await client.post(
                    self._api_base,
                    json=body,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                        # Required by GitHub Copilot API for client identification and routing
                        # Copilot-Integration-Id identifies the integration type (vscode-chat is standard)
                        # Editor-Version must follow vscode/X.Y.Z format for API to accept request
                        "Copilot-Integration-Id": "vscode-chat",
                        "Editor-Version": "vscode/1.98.2",
                    },
                )

                # Check for retriable 403 errors (GitHub's intermittent rate limiting)
                if response.status_code == 403 and attempt < self.MAX_RETRIES:
                    # Calculate exponential backoff delay: 1s, 2s, 4s
                    delay = min(self.RETRY_BASE_DELAY * (2**attempt), self.RETRY_MAX_DELAY)
                    logger.debug(
                        f"GitHub Copilot API returned 403 (attempt {attempt + 1}/{self.MAX_RETRIES + 1}), "
                        f"retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)
                    continue  # Retry the request

                # Handle errors (either non-403 or last attempt)
                if response.status_code != 200:
                    self._handle_http_error(response)

                # Parse response
                data = response.json()
                return self._parse_response(data)

            except AuthenticationError:
                # Re-raise authentication errors as-is (don't retry auth failures)
                raise
            except httpx.TimeoutException as e:
                last_exception = e
                # Don't retry timeouts
                raise LLMProviderError(
                    message=f"Request timed out after {self._timeout}s: {e}",
                    provider="github-copilot",
                    error_code="timeout",
                ) from e
            except httpx.ConnectError as e:
                last_exception = e
                raise LLMProviderError(
                    message=f"Failed to connect to GitHub Copilot API: {e}",
                    provider="github-copilot",
                    error_code="connection_error",
                ) from e
            except httpx.RequestError as e:
                last_exception = e
                raise LLMProviderError(
                    message=f"Network error: {e}",
                    provider="github-copilot",
                    error_code="network_error",
                ) from e
            except Exception as e:
                last_exception = e
                # Re-raise our own errors
                if isinstance(e, LLMProviderError):
                    raise
                # Wrap unexpected errors
                raise LLMProviderError(
                    message=f"Unexpected error: {e}",
                    provider="github-copilot",
                    error_code="unknown",
                ) from e

        # Should not reach here, but handle gracefully
        if last_exception:
            raise last_exception
        raise LLMProviderError(
            message="Max retries exceeded",
            provider="github-copilot",
            error_code="max_retries_exceeded",
        )

    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat response from GitHub Copilot API.

        Args:
            messages: List of message dictionaries
            tools: Optional tool definitions
            **kwargs: Additional parameters

        Yields:
            Response tokens as they arrive

        Raises:
            AuthenticationError: If not authenticated
            LLMProviderError: For other errors
        """
        # Retry loop for handling intermittent 403 errors
        last_exception: Exception | None = None

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                token = self._get_auth_token()
                client = await self._get_http_client()

                # Build request with streaming
                body = self._format_request(messages=messages, tools=tools, stream=True, **kwargs)

                # Make streaming request
                async with client.stream(
                    "POST",
                    self._api_base,
                    json=body,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                        # Required by GitHub Copilot API for client identification and routing
                        # Copilot-Integration-Id identifies the integration type (vscode-chat is standard)
                        # Editor-Version must follow vscode/X.Y.Z format for API to accept request
                        "Copilot-Integration-Id": "vscode-chat",
                        "Editor-Version": "vscode/1.98.2",
                    },
                ) as response:
                    # Check for retriable 403 errors (GitHub's intermittent rate limiting)
                    if response.status_code == 403 and attempt < self.MAX_RETRIES:
                        # Calculate exponential backoff delay: 1s, 2s, 4s
                        delay = min(self.RETRY_BASE_DELAY * (2**attempt), self.RETRY_MAX_DELAY)
                        logger.debug(
                            f"GitHub Copilot streaming API returned 403 (attempt {attempt + 1}/{self.MAX_RETRIES + 1}), "
                            f"retrying in {delay:.1f}s..."
                        )
                        await asyncio.sleep(delay)
                        continue  # Retry the request

                    # Check status (either non-403 or last attempt)
                    if response.status_code != 200:
                        # Read full response for error handling
                        await response.aread()
                        self._handle_http_error(response)

                    # Parse SSE stream
                    async for line in response.aiter_lines():
                        # SSE format: "data: {json}" or "data: [DONE]"
                        if line.startswith("data: "):
                            data_str = line[6:]  # Strip "data: " prefix

                            # Check for stream end
                            if data_str.strip() == "[DONE]":
                                break

                            # Parse JSON chunk
                            try:
                                data = json.loads(data_str)
                                if data.get("choices"):
                                    delta = data["choices"][0].get("delta", {})
                                    content = delta.get("content")
                                    if content:
                                        yield content
                            except json.JSONDecodeError:
                                # Skip malformed chunks
                                continue

                    # Successfully completed streaming
                    return

            except AuthenticationError:
                # Don't retry auth failures
                raise
            except httpx.TimeoutException as e:
                last_exception = e
                raise LLMProviderError(
                    message=f"Stream timed out: {e}",
                    provider="github-copilot",
                    error_code="timeout",
                ) from e
            except Exception as e:
                last_exception = e
                if isinstance(e, LLMProviderError):
                    raise
                raise LLMProviderError(
                    message=f"Stream error: {e}",
                    provider="github-copilot",
                    error_code="stream_error",
                ) from e

        # Should not reach here, but handle gracefully
        if last_exception:
            raise last_exception
        raise LLMProviderError(
            message="Max retries exceeded for streaming",
            provider="github-copilot",
            error_code="max_retries_exceeded",
        )

    def _parse_response(self, data: dict[str, Any]) -> LLMResponse:
        """
        Parse OpenAI-compatible response into LLMResponse.

        Args:
            data: Response JSON from API

        Returns:
            Parsed LLMResponse object
        """
        # Extract first choice
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})

        # Extract content
        content = message.get("content")

        # Extract tool calls if present
        tool_calls = []
        if message.get("tool_calls"):
            for tc in message["tool_calls"]:
                tool_calls.append(
                    {
                        "id": tc.get("id", ""),
                        "type": tc.get("type", "function"),
                        "function": {
                            "name": tc.get("function", {}).get("name", ""),
                            "arguments": tc.get("function", {}).get("arguments", "{}"),
                        },
                    }
                )

        # Extract usage information
        usage = {}
        if data.get("usage"):
            usage = {
                "prompt_tokens": data["usage"].get("prompt_tokens", 0),
                "completion_tokens": data["usage"].get("completion_tokens", 0),
                "total_tokens": data["usage"].get("total_tokens", 0),
            }

        # Extract finish reason
        finish_reason = choice.get("finish_reason")

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage=usage,
        )

    def _handle_http_error(self, response: httpx.Response) -> None:
        """
        Handle HTTP error responses and raise appropriate exceptions.

        Args:
            response: HTTP response with error status

        Raises:
            AuthenticationError: For 401/403 errors
            RateLimitError: For 429 errors
            InvalidRequestError: For 400 errors
            LLMProviderError: For other errors
        """
        status_code = response.status_code

        # Try to extract error message from response
        try:
            error_data = response.json()
            error_message = error_data.get("error", {}).get("message", response.text)
        except Exception:
            error_message = response.text or f"HTTP {status_code}"

        # Sanitize error message (don't leak tokens)
        if "gho_" in error_message:
            error_message = "Authentication failed (invalid token)"

        # Handle specific status codes
        if status_code == 401:
            raise AuthenticationError(
                message=(
                    f"Authentication failed: {error_message}. "
                    "Your token may be expired or invalid. "
                    "Run 'logai auth login' to re-authenticate."
                ),
                provider="github-copilot",
                error_code="unauthorized",
            )
        elif status_code == 403:
            raise AuthenticationError(
                message=(
                    f"Access forbidden: {error_message}. "
                    "You may not have GitHub Copilot access. "
                    "Please check your GitHub Copilot subscription."
                ),
                provider="github-copilot",
                error_code="forbidden",
            )
        elif status_code == 429:
            raise RateLimitError(
                message=f"Rate limit exceeded: {error_message}. Please try again later.",
                provider="github-copilot",
                error_code="rate_limit",
            )
        elif status_code == 400:
            raise InvalidRequestError(
                message=f"Invalid request: {error_message}",
                provider="github-copilot",
                error_code="bad_request",
            )
        elif status_code >= 500:
            raise LLMProviderError(
                message=f"GitHub Copilot API error ({status_code}): {error_message}",
                provider="github-copilot",
                error_code=f"server_error_{status_code}",
            )
        else:
            raise LLMProviderError(
                message=f"API error ({status_code}): {error_message}",
                provider="github-copilot",
                error_code=f"http_{status_code}",
            )
