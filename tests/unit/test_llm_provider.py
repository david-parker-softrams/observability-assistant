"""Tests for LLM providers."""

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
        provider = LiteLLMProvider.from_settings(mock_settings)

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
            response = await provider.chat(
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

        provider = LiteLLMProvider.from_settings(settings)

        assert provider.provider == "ollama"
        assert provider.model == "llama3.1:8b"
        assert provider.api_base == "http://localhost:11434"
        assert provider.api_key == ""

    def test_ollama_model_name(self):
        """Test Ollama model name formatting."""
        provider = LiteLLMProvider(
            provider="ollama",
            api_key="",
            model="llama3.1:8b",
            api_base="http://localhost:11434",
        )

        assert provider._get_model_name() == "ollama/llama3.1:8b"

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
