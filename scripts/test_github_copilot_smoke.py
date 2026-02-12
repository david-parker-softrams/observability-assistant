"""Smoke tests for GitHub Copilot provider (no authentication required).

These tests validate the provider code structure and basic functionality
without requiring actual authentication.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_imports():
    """Test that all imports work correctly."""
    print("=" * 60)
    print("TEST: Imports")
    print("=" * 60)

    try:
        from logai.providers.llm import (
            GitHubCopilotProvider,
            get_available_models,
            get_model_metadata,
            refresh_model_cache,
            validate_model,
        )

        print("✓ GitHubCopilotProvider imported")
        print("✓ get_available_models imported")
        print("✓ get_model_metadata imported")
        print("✓ refresh_model_cache imported")
        print("✓ validate_model imported")
        return True
    except Exception as e:
        print(f"✗ Import error: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_provider_initialization():
    """Test provider can be initialized."""
    print("\n" + "=" * 60)
    print("TEST: Provider Initialization")
    print("=" * 60)

    try:
        from logai.providers.llm import GitHubCopilotProvider

        # Test default initialization
        provider = GitHubCopilotProvider()
        print(f"✓ Default model: {provider.model}")
        print(f"✓ Full model name: {provider.full_model_name}")
        print(f"✓ Temperature: {provider.temperature}")
        print(f"✓ Supports tools: {provider._supports_tools()}")

        # Test with custom model
        provider2 = GitHubCopilotProvider(model="gpt-4.1", temperature=0.5)
        print(f"✓ Custom model: {provider2.model}")
        print(f"✓ Custom temperature: {provider2.temperature}")

        # Test prefix stripping
        provider3 = GitHubCopilotProvider(model="github-copilot/claude-opus-4.6")
        assert provider3.model == "claude-opus-4.6", "Provider should strip github-copilot/ prefix"
        print(f"✓ Prefix stripping works: {provider3.model}")

        return True
    except Exception as e:
        print(f"✗ Initialization error: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_model_utilities():
    """Test model utility functions."""
    print("\n" + "=" * 60)
    print("TEST: Model Utilities")
    print("=" * 60)

    try:
        from logai.providers.llm import (
            get_available_models,
            get_model_metadata,
            validate_model,
        )
        from logai.providers.llm.github_copilot_models import (
            DEFAULT_MODEL,
            DEFAULT_MODELS,
            get_available_models_sync,
        )

        # Test get_available_models_sync (doesn't require async)
        models = get_available_models_sync()
        print(f"✓ Found {len(models)} models (sync)")
        print(f"  Sample: {', '.join(models[:3])}")

        # Test validate_model
        assert validate_model("claude-opus-4.6"), "Should validate known model"
        print("✓ validate_model('claude-opus-4.6') = True")

        assert validate_model("github-copilot/claude-opus-4.6"), "Should strip prefix"
        print("✓ validate_model('github-copilot/claude-opus-4.6') = True")

        assert not validate_model("invalid-model-xyz"), "Should reject unknown model"
        print("✓ validate_model('invalid-model-xyz') = False")

        # Test get_model_metadata
        metadata = get_model_metadata("claude-opus-4.6")
        print(f"✓ Metadata for claude-opus-4.6:")
        print(f"    Provider: {metadata['provider']}")
        print(f"    Supports tools: {metadata['supports_tools']}")
        print(f"    Tier: {metadata['tier']}")

        # Test default model constant
        print(f"✓ Default model: {DEFAULT_MODEL}")
        assert DEFAULT_MODEL in DEFAULT_MODELS, "Default model should be in model list"

        return True
    except Exception as e:
        print(f"✗ Model utilities error: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_request_formatting():
    """Test request formatting (without sending)."""
    print("\n" + "=" * 60)
    print("TEST: Request Formatting")
    print("=" * 60)

    try:
        from logai.providers.llm import GitHubCopilotProvider

        provider = GitHubCopilotProvider(model="claude-opus-4.6")

        # Test basic request
        messages = [{"role": "user", "content": "Hello"}]
        request = provider._format_request(messages)

        assert request["model"] == "claude-opus-4.6", "Model should be in request"
        assert request["messages"] == messages, "Messages should be in request"
        assert "temperature" in request, "Temperature should be in request"
        assert request["stream"] is False, "Stream should be False by default"

        print("✓ Basic request format:")
        print(f"    Model: {request['model']}")
        print(f"    Messages: {len(request['messages'])} message(s)")
        print(f"    Temperature: {request['temperature']}")
        print(f"    Stream: {request['stream']}")

        # Test request with tools
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "test_function",
                    "description": "A test function",
                    "parameters": {},
                },
            }
        ]
        request_with_tools = provider._format_request(messages, tools=tools)

        assert "tools" in request_with_tools, "Tools should be in request"
        print("✓ Request with tools includes 'tools' field")

        # Test streaming request
        request_streaming = provider._format_request(messages, stream=True)
        assert request_streaming["stream"] is True, "Stream should be True"
        print("✓ Streaming request format correct")

        return True
    except Exception as e:
        print(f"✗ Request formatting error: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_response_parsing():
    """Test response parsing logic."""
    print("\n" + "=" * 60)
    print("TEST: Response Parsing")
    print("=" * 60)

    try:
        from logai.providers.llm import GitHubCopilotProvider

        provider = GitHubCopilotProvider()

        # Test parsing a basic response
        mock_response = {
            "choices": [
                {
                    "message": {"content": "Hello, world!", "role": "assistant"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30,
            },
        }

        result = provider._parse_response(mock_response)
        assert result.content == "Hello, world!", "Content should be extracted"
        assert result.finish_reason == "stop", "Finish reason should be extracted"
        assert result.usage["total_tokens"] == 30, "Usage should be extracted"
        assert not result.has_tool_calls(), "Should have no tool calls"

        print("✓ Basic response parsing:")
        print(f"    Content: {result.content}")
        print(f"    Finish reason: {result.finish_reason}")
        print(f"    Usage: {result.usage}")

        # Test parsing response with tool calls
        mock_tool_response = {
            "choices": [
                {
                    "message": {
                        "content": None,
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "id": "call_123",
                                "type": "function",
                                "function": {
                                    "name": "get_weather",
                                    "arguments": '{"location": "SF"}',
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

        result_with_tools = provider._parse_response(mock_tool_response)
        assert result_with_tools.has_tool_calls(), "Should have tool calls"
        assert len(result_with_tools.tool_calls) == 1, "Should have 1 tool call"
        assert result_with_tools.tool_calls[0]["function"]["name"] == "get_weather", (
            "Function name should match"
        )

        print("✓ Tool call response parsing:")
        print(f"    Has tool calls: {result_with_tools.has_tool_calls()}")
        print(f"    Tool: {result_with_tools.tool_calls[0]['function']['name']}")
        print(f"    Args: {result_with_tools.tool_calls[0]['function']['arguments']}")

        return True
    except Exception as e:
        print(f"✗ Response parsing error: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all smoke tests."""
    print("\n")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║     GitHub Copilot Provider Smoke Tests                  ║")
    print("║     (No authentication required)                           ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()

    results = []

    # Run tests
    results.append(("Imports", test_imports()))
    results.append(("Provider Initialization", test_provider_initialization()))
    results.append(("Model Utilities", test_model_utilities()))
    results.append(("Request Formatting", test_request_formatting()))
    results.append(("Response Parsing", test_response_parsing()))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status:8} | {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All smoke tests passed!")
        print("\nNext steps:")
        print("  1. Run 'logai auth login' to authenticate")
        print("  2. Run 'python -m scripts.test_github_copilot_provider' for full tests")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
