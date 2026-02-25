"""Tests for LLM providers."""

from typing import cast
from unittest.mock import AsyncMock, Mock, patch

import pytest
from logai.config.settings import LogAISettings
from logai.providers.llm.base import (
    AuthenticationError,
    InvalidRequestError,
    LLMProviderError,
    LLMResponse,
    RateLimitError,
)
from logai.providers.llm.litellm_provider import LiteLLMProvider


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    settings = Mock(spec=LogAISettings)
    settings.llm_provider = "anthropic"
    settings.anthropic_api_key = "test-api-key"
    settings.anthropic_model = "claude-3-5-sonnet-20241022"
    settings.llm_request_timeout = 120.0
    return settings


class TestLLMResponse:
    """Tests for LLMResponse."""

    def test_response_without_tool_calls(self):
        """Test response without tool calls."""
        response = LLMResponse(content="Hello world", finish_reason="stop")

        assert response.content == "Hello world"
        assert response.has_tool_calls() is False
        assert len(response.tool_calls) == 0

    def test_response_with_tool_calls(self):
        """Test response with tool calls."""
        tool_calls = [
            {
                "id": "call_123",
                "type": "function",
                "function": {"name": "test_tool", "arguments": '{"arg": "value"}'},
            }
        ]
        response = LLMResponse(content="", tool_calls=tool_calls, finish_reason="tool_calls")

        assert response.has_tool_calls() is True
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0]["function"]["name"] == "test_tool"


class TestLiteLLMProvider:
    """Tests for LiteLLMProvider."""

    def test_initialization(self):
        """Test provider initialization."""
        provider = LiteLLMProvider(
            provider="anthropic",
            api_key="test-key",
            model="claude-3-5-sonnet-20241022",
            temperature=0.5,
        )

        assert provider.provider == "anthropic"
        assert provider.model == "claude-3-5-sonnet-20241022"
        assert provider.temperature == 0.5

    def test_from_settings(self, mock_settings):
        """Test creating provider from settings."""
        provider = cast(LiteLLMProvider, LiteLLMProvider.from_settings(mock_settings))

        assert provider.provider == "anthropic"
        assert provider.model == "claude-3-5-sonnet-20241022"
        assert provider.api_key == "test-api-key"

    @pytest.mark.asyncio
    async def test_chat_success(self):
        """Test successful chat completion."""
        provider = LiteLLMProvider(
            provider="anthropic",
            api_key="test-key",
            model="claude-3-5-sonnet-20241022",
        )

        # Mock litellm.completion
        mock_choice = Mock()
        mock_choice.message.content = "Test response"
        mock_choice.finish_reason = "stop"
        mock_choice.message.tool_calls = None

        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20
        mock_response.usage.total_tokens = 30

        with patch("litellm.completion", return_value=mock_response):
            response = await provider.chat(messages=[{"role": "user", "content": "Hello"}])

            assert isinstance(response, LLMResponse)
            assert response.content == "Test response"
            assert response.finish_reason == "stop"
            assert response.usage["total_tokens"] == 30

    @pytest.mark.asyncio
    async def test_chat_with_tool_calls(self):
        """Test chat with tool calls."""
        provider = LiteLLMProvider(
            provider="anthropic",
            api_key="test-key",
            model="claude-3-5-sonnet-20241022",
        )

        # Mock tool call response
        mock_tool_call = Mock()
        mock_tool_call.id = "call_123"
        mock_tool_call.type = "function"
        mock_tool_call.function.name = "test_tool"
        mock_tool_call.function.arguments = '{"arg": "value"}'

        mock_choice = Mock()
        mock_choice.message.content = None
        mock_choice.message.tool_calls = [mock_tool_call]
        mock_choice.finish_reason = "tool_calls"

        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_response.usage = None

        with patch("litellm.completion", return_value=mock_response):
            response = cast(
                LLMResponse,
                await provider.chat(
                    messages=[{"role": "user", "content": "List log groups"}],
                    tools=[
                        {
                            "type": "function",
                            "function": {
                                "name": "test_tool",
                                "description": "Test",
                                "parameters": {},
                            },
                        }
                    ],
                ),
            )

            assert response.has_tool_calls()
            assert len(response.tool_calls) == 1
            assert response.tool_calls[0]["function"]["name"] == "test_tool"

    @pytest.mark.asyncio
    async def test_chat_authentication_error(self):
        """Test handling authentication errors."""
        provider = LiteLLMProvider(
            provider="anthropic",
            api_key="invalid-key",
            model="claude-3-5-sonnet-20241022",
        )

        with patch(
            "litellm.completion",
            side_effect=Exception("Authentication failed: invalid API key"),
        ):
            with pytest.raises(AuthenticationError) as exc_info:
                await provider.chat(messages=[{"role": "user", "content": "Hello"}])

            assert "Authentication failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_chat_rate_limit_error(self):
        """Test handling rate limit errors."""
        provider = LiteLLMProvider(
            provider="anthropic",
            api_key="test-key",
            model="claude-3-5-sonnet-20241022",
        )

        with patch(
            "litellm.completion",
            side_effect=Exception("Rate limit exceeded"),
        ):
            with pytest.raises(RateLimitError) as exc_info:
                await provider.chat(messages=[{"role": "user", "content": "Hello"}])

            assert "Rate limit" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_chat_invalid_request_error(self):
        """Test handling invalid request errors."""
        provider = LiteLLMProvider(
            provider="anthropic",
            api_key="test-key",
            model="claude-3-5-sonnet-20241022",
        )

        with patch(
            "litellm.completion",
            side_effect=Exception("Invalid request: bad parameter"),
        ):
            with pytest.raises(InvalidRequestError) as exc_info:
                await provider.chat(messages=[{"role": "user", "content": "Hello"}])

            assert "Invalid request" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_chat_generic_error(self):
        """Test handling generic errors."""
        provider = LiteLLMProvider(
            provider="anthropic",
            api_key="test-key",
            model="claude-3-5-sonnet-20241022",
        )

        with patch(
            "litellm.completion",
            side_effect=Exception("Something unexpected happened"),
        ):
            with pytest.raises(LLMProviderError) as exc_info:
                await provider.chat(messages=[{"role": "user", "content": "Hello"}])

            assert "LLM request failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_stream_chat(self):
        """Test streaming chat."""
        provider = LiteLLMProvider(
            provider="anthropic",
            api_key="test-key",
            model="claude-3-5-sonnet-20241022",
        )

        # Mock streaming response
        mock_chunks = []
        for text in ["Hello", " ", "world"]:
            mock_delta = Mock()
            mock_delta.content = text
            mock_choice = Mock()
            mock_choice.delta = mock_delta
            mock_chunk = Mock()
            mock_chunk.choices = [mock_choice]
            mock_chunks.append(mock_chunk)

        with patch("litellm.completion", return_value=iter(mock_chunks)):
            tokens = []
            async for token in provider.stream_chat(
                messages=[{"role": "user", "content": "Hello"}]
            ):
                tokens.append(token)

            assert tokens == ["Hello", " ", "world"]
            assert "".join(tokens) == "Hello world"

    def test_ollama_provider_initialization(self):
        """Test Ollama provider initialization."""
        provider = LiteLLMProvider(
            provider="ollama",
            api_key="",
            model="llama3.1:8b",
            api_base="http://localhost:11434",
        )

        assert provider.provider == "ollama"
        assert provider.model == "llama3.1:8b"
        assert provider.api_base == "http://localhost:11434"
        assert provider.api_key == ""  # No API key for Ollama

    def test_ollama_from_settings(self):
        """Test creating Ollama provider from settings."""
        settings = Mock(spec=LogAISettings)
        settings.llm_provider = "ollama"
        settings.ollama_base_url = "http://localhost:11434"
        settings.ollama_model = "llama3.1:8b"
        settings.ollama_num_ctx = 32768
        settings.llm_request_timeout = 120.0

        provider = cast(LiteLLMProvider, LiteLLMProvider.from_settings(settings))

        assert provider.provider == "ollama"
        assert provider.model == "llama3.1:8b"
        assert provider.api_base == "http://localhost:11434"
        assert provider.api_key == ""
        assert provider.num_ctx == 32768

    def test_ollama_model_name(self):
        """Test Ollama model name formatting."""
        provider = LiteLLMProvider(
            provider="ollama",
            api_key="",
            model="llama3.1:8b",
            api_base="http://localhost:11434",
        )

        assert provider._get_model_name() == "ollama_chat/llama3.1:8b"

    def test_anthropic_model_name(self):
        """Test Anthropic model name formatting."""
        provider = LiteLLMProvider(
            provider="anthropic",
            api_key="test-key",
            model="claude-3-5-sonnet-20241022",
        )

        assert provider._get_model_name() == "anthropic/claude-3-5-sonnet-20241022"

    def test_openai_model_name(self):
        """Test OpenAI model name formatting."""
        provider = LiteLLMProvider(
            provider="openai",
            api_key="test-key",
            model="gpt-4-turbo-preview",
        )

        assert provider._get_model_name() == "openai/gpt-4-turbo-preview"

    def test_anthropic_supports_tools(self):
        """Test Anthropic models support tool calling."""
        provider = LiteLLMProvider(
            provider="anthropic",
            api_key="test-key",
            model="claude-3-5-sonnet-20241022",
        )

        assert provider._supports_tools() is True

    def test_openai_supports_tools(self):
        """Test OpenAI models support tool calling."""
        provider = LiteLLMProvider(
            provider="openai",
            api_key="test-key",
            model="gpt-4-turbo-preview",
        )

        assert provider._supports_tools() is True

    def test_ollama_qwen_supports_tools(self):
        """Test Ollama Qwen models support tool calling."""
        provider = LiteLLMProvider(
            provider="ollama",
            api_key="",
            model="qwen3",
            api_base="http://localhost:11434",
        )

        assert provider._supports_tools() is True

    def test_ollama_llama_supports_tools(self):
        """Test Ollama Llama 3.1+ models support tool calling."""
        provider = LiteLLMProvider(
            provider="ollama",
            api_key="",
            model="llama3.1:8b",
            api_base="http://localhost:11434",
        )

        assert provider._supports_tools() is True

    def test_ollama_command_r_supports_tools(self):
        """Test Ollama Command-R models support tool calling."""
        provider = LiteLLMProvider(
            provider="ollama",
            api_key="",
            model="command-r",
            api_base="http://localhost:11434",
        )

        assert provider._supports_tools() is True

    def test_ollama_deepseek_r1_no_tool_support(self):
        """Test Ollama DeepSeek-R1 does NOT support tool calling."""
        provider = LiteLLMProvider(
            provider="ollama",
            api_key="",
            model="deepseek-r1",
            api_base="http://localhost:11434",
        )

        assert provider._supports_tools() is False

    def test_ollama_openthinker_no_tool_support(self):
        """Test Ollama OpenThinker does NOT support tool calling."""
        provider = LiteLLMProvider(
            provider="ollama",
            api_key="",
            model="openthinker",
            api_base="http://localhost:11434",
        )

        assert provider._supports_tools() is False

    def test_ollama_unsupported_model_no_tool_support(self):
        """Test unsupported Ollama models do NOT support tool calling."""
        provider = LiteLLMProvider(
            provider="ollama",
            api_key="",
            model="some-unknown-model",
            api_base="http://localhost:11434",
        )

        assert provider._supports_tools() is False


# ---------------------------------------------------------------------------
# num_ctx injection tests (ollama context window fix)
# ---------------------------------------------------------------------------


def _make_mock_litellm_response(content: str = "ok") -> Mock:
    """Return a minimal Mock that looks like a litellm ModelResponse."""
    mock_choice = Mock()
    mock_choice.message.content = content
    mock_choice.message.tool_calls = None
    mock_choice.finish_reason = "stop"
    mock_response = Mock()
    mock_response.choices = [mock_choice]
    mock_response.usage = None
    return mock_response


def _make_mock_stream_chunks(tokens: list[str]) -> list[Mock]:
    """Return mock streaming chunks for the given token list."""
    chunks = []
    for text in tokens:
        mock_delta = Mock()
        mock_delta.content = text
        mock_choice = Mock()
        mock_choice.delta = mock_delta
        mock_chunk = Mock()
        mock_chunk.choices = [mock_choice]
        chunks.append(mock_chunk)
    return chunks


class TestOllamaNumCtxInjection:
    """Tests verifying that num_ctx → options injection in chat() and stream_chat()."""

    # ------------------------------------------------------------------
    # chat() tests
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_chat_injects_num_ctx_kwarg_for_ollama(self) -> None:
        """chat() must pass num_ctx=N as a top-level kwarg to litellm.completion for Ollama.

        LiteLLM's Ollama handler recognises num_ctx only when it arrives as a direct
        kwarg (routed via optional_params → "options" in the Ollama request body).
        Passing num_ctx=N as a top-level kwarg is the correct approach; wrapping it
        in an options dict is not in get_supported_openai_params and gets silently dropped.
        """
        provider = LiteLLMProvider(
            provider="ollama",
            api_key="",
            model="qwen3:32b",
            api_base="http://localhost:11434",
            num_ctx=32768,
        )

        mock_response = _make_mock_litellm_response()

        with patch("litellm.completion", return_value=mock_response) as mock_completion:
            await provider.chat(messages=[{"role": "user", "content": "Hello"}])

        call_kwargs = mock_completion.call_args[1]
        assert (
            "num_ctx" in call_kwargs
        ), "num_ctx must be a top-level kwarg in litellm.completion call"
        assert call_kwargs["num_ctx"] == 32768
        assert "options" not in call_kwargs, "options dict must NOT be used (LiteLLM drops it)"

    @pytest.mark.asyncio
    async def test_chat_num_ctx_not_injected_for_anthropic(self) -> None:
        """chat() must NOT pass options= for non-Ollama providers (e.g. Anthropic)."""
        provider = LiteLLMProvider(
            provider="anthropic",
            api_key="sk-ant-test",
            model="claude-3-5-sonnet-20241022",
            num_ctx=32768,  # num_ctx set but provider is not Ollama
        )

        mock_response = _make_mock_litellm_response()

        with patch("litellm.completion", return_value=mock_response) as mock_completion:
            await provider.chat(messages=[{"role": "user", "content": "Hello"}])

        call_kwargs = mock_completion.call_args[1]
        assert "options" not in call_kwargs, "options must NOT be forwarded to non-Ollama providers"
        assert "num_ctx" not in call_kwargs, "num_ctx must NOT be forwarded to non-Ollama providers"

    @pytest.mark.asyncio
    async def test_chat_num_ctx_not_injected_for_openai(self) -> None:
        """chat() must NOT pass options= for OpenAI provider."""
        provider = LiteLLMProvider(
            provider="openai",
            api_key="sk-openai-test",
            model="gpt-4-turbo-preview",
            num_ctx=32768,  # num_ctx set but provider is OpenAI
        )

        mock_response = _make_mock_litellm_response()

        with patch("litellm.completion", return_value=mock_response) as mock_completion:
            await provider.chat(messages=[{"role": "user", "content": "Hello"}])

        call_kwargs = mock_completion.call_args[1]
        assert "options" not in call_kwargs, "options must NOT be forwarded to OpenAI provider"
        assert "num_ctx" not in call_kwargs, "num_ctx must NOT be forwarded to OpenAI provider"

    @pytest.mark.asyncio
    async def test_chat_num_ctx_none_skips_options_for_ollama(self) -> None:
        """chat() must NOT inject options= when num_ctx is None (even for Ollama)."""
        provider = LiteLLMProvider(
            provider="ollama",
            api_key="",
            model="llama3.1:8b",
            api_base="http://localhost:11434",
            num_ctx=None,  # explicitly None — no override desired
        )

        mock_response = _make_mock_litellm_response()

        with patch("litellm.completion", return_value=mock_response) as mock_completion:
            await provider.chat(messages=[{"role": "user", "content": "Hello"}])

        call_kwargs = mock_completion.call_args[1]
        assert "options" not in call_kwargs, "options must not be injected when num_ctx is None"
        assert "num_ctx" not in call_kwargs, "num_ctx must not be injected when num_ctx is None"

    @pytest.mark.asyncio
    async def test_chat_num_ctx_value_is_passed_exactly(self) -> None:
        """The exact num_ctx value is forwarded, not a default or rounded value."""
        provider = LiteLLMProvider(
            provider="ollama",
            api_key="",
            model="qwen3:32b",
            api_base="http://localhost:11434",
            num_ctx=65536,
        )

        mock_response = _make_mock_litellm_response()

        with patch("litellm.completion", return_value=mock_response) as mock_completion:
            await provider.chat(messages=[{"role": "user", "content": "Hello"}])

        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs["num_ctx"] == 65536

    # ------------------------------------------------------------------
    # stream_chat() tests
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_stream_chat_injects_num_ctx_kwarg_for_ollama(self) -> None:
        """stream_chat() must pass num_ctx=N as a top-level kwarg to litellm.completion for Ollama."""
        provider = LiteLLMProvider(
            provider="ollama",
            api_key="",
            model="qwen3:32b",
            api_base="http://localhost:11434",
            num_ctx=32768,
        )

        chunks = _make_mock_stream_chunks(["Hello"])

        with patch("litellm.completion", return_value=iter(chunks)) as mock_completion:
            tokens = [
                t async for t in provider.stream_chat(messages=[{"role": "user", "content": "Hi"}])
            ]

        call_kwargs = mock_completion.call_args[1]
        assert (
            "num_ctx" in call_kwargs
        ), "num_ctx must be a top-level kwarg in streaming litellm.completion call"
        assert call_kwargs["num_ctx"] == 32768
        assert "options" not in call_kwargs, "options dict must NOT be used (LiteLLM drops it)"
        assert tokens == ["Hello"]

    @pytest.mark.asyncio
    async def test_stream_chat_num_ctx_not_injected_for_anthropic(self) -> None:
        """stream_chat() must NOT inject options= for non-Ollama providers."""
        provider = LiteLLMProvider(
            provider="anthropic",
            api_key="sk-ant-test",
            model="claude-3-5-sonnet-20241022",
            num_ctx=32768,
        )

        chunks = _make_mock_stream_chunks(["Hi"])

        with patch("litellm.completion", return_value=iter(chunks)) as mock_completion:
            [t async for t in provider.stream_chat(messages=[{"role": "user", "content": "Hi"}])]

        call_kwargs = mock_completion.call_args[1]
        assert (
            "options" not in call_kwargs
        ), "options must NOT be forwarded to non-Ollama providers in stream_chat"
        assert (
            "num_ctx" not in call_kwargs
        ), "num_ctx must NOT be forwarded to non-Ollama providers in stream_chat"

    @pytest.mark.asyncio
    async def test_stream_chat_num_ctx_none_skips_options_for_ollama(self) -> None:
        """stream_chat() must NOT inject options= when num_ctx is None."""
        provider = LiteLLMProvider(
            provider="ollama",
            api_key="",
            model="llama3.1:8b",
            api_base="http://localhost:11434",
            num_ctx=None,
        )

        chunks = _make_mock_stream_chunks(["Hello"])

        with patch("litellm.completion", return_value=iter(chunks)) as mock_completion:
            [t async for t in provider.stream_chat(messages=[{"role": "user", "content": "Hi"}])]

        call_kwargs = mock_completion.call_args[1]
        assert (
            "options" not in call_kwargs
        ), "options must not be injected when num_ctx is None in stream_chat"
        assert (
            "num_ctx" not in call_kwargs
        ), "num_ctx must not be injected when num_ctx is None in stream_chat"

    @pytest.mark.asyncio
    async def test_stream_chat_passes_stream_true_to_litellm(self) -> None:
        """stream_chat() must always pass stream=True to litellm.completion."""
        provider = LiteLLMProvider(
            provider="ollama",
            api_key="",
            model="llama3.1:8b",
            api_base="http://localhost:11434",
            num_ctx=32768,
        )

        chunks = _make_mock_stream_chunks(["token"])

        with patch("litellm.completion", return_value=iter(chunks)) as mock_completion:
            [t async for t in provider.stream_chat(messages=[{"role": "user", "content": "Hi"}])]

        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs.get("stream") is True

    # ------------------------------------------------------------------
    # from_settings() integration — num_ctx wired correctly
    # ------------------------------------------------------------------

    def test_from_settings_passes_num_ctx_to_ollama_provider(self) -> None:
        """from_settings() must forward ollama_num_ctx → LiteLLMProvider.num_ctx."""
        settings = Mock(spec=LogAISettings)
        settings.llm_provider = "ollama"
        settings.ollama_base_url = "http://localhost:11434"
        settings.ollama_model = "qwen3:32b"
        settings.ollama_num_ctx = 65536
        settings.llm_request_timeout = 120.0

        provider = cast(LiteLLMProvider, LiteLLMProvider.from_settings(settings))

        assert provider.num_ctx == 65536

    def test_from_settings_ollama_num_ctx_default(self) -> None:
        """from_settings() passes the num_ctx value from settings (default 32768)."""
        settings = Mock(spec=LogAISettings)
        settings.llm_provider = "ollama"
        settings.ollama_base_url = "http://localhost:11434"
        settings.ollama_model = "llama3.1:8b"
        settings.ollama_num_ctx = 32768  # the configured default
        settings.llm_request_timeout = 120.0

        provider = cast(LiteLLMProvider, LiteLLMProvider.from_settings(settings))

        assert provider.num_ctx == 32768

    def test_num_ctx_defaults_to_none_when_not_provided(self) -> None:
        """num_ctx defaults to None when not passed to the constructor."""
        provider = LiteLLMProvider(
            provider="ollama",
            api_key="",
            model="llama3.1:8b",
            api_base="http://localhost:11434",
        )
        assert provider.num_ctx is None


# ---------------------------------------------------------------------------
# request_timeout injection tests
# ---------------------------------------------------------------------------


class TestRequestTimeoutInjection:
    """Tests verifying that request_timeout is forwarded to litellm.completion()
    in both chat() and stream_chat(), preventing the 10-minute httpcore default hang.
    """

    # ------------------------------------------------------------------
    # Constructor / default value
    # ------------------------------------------------------------------

    def test_request_timeout_default_is_120(self) -> None:
        """request_timeout defaults to 120.0 seconds when not supplied."""
        provider = LiteLLMProvider(
            provider="ollama",
            api_key="",
            model="llama3.1:8b",
            api_base="http://localhost:11434",
        )
        assert provider.request_timeout == 120.0

    def test_request_timeout_custom_value_stored(self) -> None:
        """A custom request_timeout value is stored on the instance."""
        provider = LiteLLMProvider(
            provider="ollama",
            api_key="",
            model="llama3.1:8b",
            api_base="http://localhost:11434",
            request_timeout=30.0,
        )
        assert provider.request_timeout == 30.0

    # ------------------------------------------------------------------
    # chat() — timeout forwarded to litellm.completion
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_chat_passes_request_timeout_to_litellm(self) -> None:
        """chat() must include request_timeout in the litellm.completion kwargs."""
        provider = LiteLLMProvider(
            provider="ollama",
            api_key="",
            model="llama3.1:8b",
            api_base="http://localhost:11434",
            request_timeout=45.0,
        )

        mock_response = _make_mock_litellm_response()

        with patch("litellm.completion", return_value=mock_response) as mock_completion:
            await provider.chat(messages=[{"role": "user", "content": "Hi"}])

        call_kwargs = mock_completion.call_args[1]
        assert (
            "request_timeout" in call_kwargs
        ), "request_timeout must be passed to litellm.completion"
        assert call_kwargs["request_timeout"] == 45.0

    @pytest.mark.asyncio
    async def test_chat_passes_request_timeout_for_anthropic(self) -> None:
        """chat() forwards request_timeout even for non-Ollama providers."""
        provider = LiteLLMProvider(
            provider="anthropic",
            api_key="sk-ant-test",
            model="claude-3-5-sonnet-20241022",
            request_timeout=60.0,
        )

        mock_response = _make_mock_litellm_response()

        with patch("litellm.completion", return_value=mock_response) as mock_completion:
            await provider.chat(messages=[{"role": "user", "content": "Hi"}])

        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs.get("request_timeout") == 60.0

    @pytest.mark.asyncio
    async def test_chat_uses_default_timeout_when_not_specified(self) -> None:
        """chat() uses the 120 s default when request_timeout is not overridden."""
        provider = LiteLLMProvider(
            provider="anthropic",
            api_key="sk-ant-test",
            model="claude-3-5-sonnet-20241022",
        )

        mock_response = _make_mock_litellm_response()

        with patch("litellm.completion", return_value=mock_response) as mock_completion:
            await provider.chat(messages=[{"role": "user", "content": "Hi"}])

        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs.get("request_timeout") == 120.0

    # ------------------------------------------------------------------
    # stream_chat() — timeout forwarded to litellm.completion
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_stream_chat_passes_request_timeout_to_litellm(self) -> None:
        """stream_chat() must include request_timeout in the litellm.completion kwargs."""
        provider = LiteLLMProvider(
            provider="ollama",
            api_key="",
            model="llama3.1:8b",
            api_base="http://localhost:11434",
            request_timeout=90.0,
        )

        chunks = _make_mock_stream_chunks(["Hi"])

        with patch("litellm.completion", return_value=iter(chunks)) as mock_completion:
            [t async for t in provider.stream_chat(messages=[{"role": "user", "content": "Hi"}])]

        call_kwargs = mock_completion.call_args[1]
        assert (
            "request_timeout" in call_kwargs
        ), "request_timeout must be passed to litellm.completion in stream_chat"
        assert call_kwargs["request_timeout"] == 90.0

    @pytest.mark.asyncio
    async def test_stream_chat_uses_default_timeout_when_not_specified(self) -> None:
        """stream_chat() uses the 120 s default when request_timeout is not overridden."""
        provider = LiteLLMProvider(
            provider="anthropic",
            api_key="sk-ant-test",
            model="claude-3-5-sonnet-20241022",
        )

        chunks = _make_mock_stream_chunks(["Hi"])

        with patch("litellm.completion", return_value=iter(chunks)) as mock_completion:
            [t async for t in provider.stream_chat(messages=[{"role": "user", "content": "Hi"}])]

        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs.get("request_timeout") == 120.0

    # ------------------------------------------------------------------
    # from_settings() — timeout read from settings and wired through
    # ------------------------------------------------------------------

    def test_from_settings_passes_timeout_to_ollama_provider(self) -> None:
        """from_settings() must forward llm_request_timeout to LiteLLMProvider for Ollama."""
        settings = Mock(spec=LogAISettings)
        settings.llm_provider = "ollama"
        settings.ollama_base_url = "http://localhost:11434"
        settings.ollama_model = "llama3.1:8b"
        settings.ollama_num_ctx = 32768
        settings.llm_request_timeout = 60.0

        provider = cast(LiteLLMProvider, LiteLLMProvider.from_settings(settings))

        assert provider.request_timeout == 60.0

    def test_from_settings_passes_timeout_to_anthropic_provider(self) -> None:
        """from_settings() must forward llm_request_timeout for Anthropic."""
        settings = Mock(spec=LogAISettings)
        settings.llm_provider = "anthropic"
        settings.anthropic_api_key = "sk-ant-test"
        settings.anthropic_model = "claude-3-5-sonnet-20241022"
        settings.llm_request_timeout = 180.0

        provider = cast(LiteLLMProvider, LiteLLMProvider.from_settings(settings))

        assert provider.request_timeout == 180.0

    def test_from_settings_passes_timeout_to_openai_provider(self) -> None:
        """from_settings() must forward llm_request_timeout for OpenAI."""
        settings = Mock(spec=LogAISettings)
        settings.llm_provider = "openai"
        settings.openai_api_key = "sk-openai-test"
        settings.openai_model = "gpt-4-turbo-preview"
        settings.llm_request_timeout = 30.0

        provider = cast(LiteLLMProvider, LiteLLMProvider.from_settings(settings))

        assert provider.request_timeout == 30.0
