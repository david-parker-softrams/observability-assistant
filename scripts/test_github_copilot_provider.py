"""Manual test script for GitHub Copilot provider.

This script tests the GitHubCopilotProvider implementation manually.
Run this after authenticating with `logai auth login`.

Usage:
    python -m scripts.test_github_copilot_provider
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for testing
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from logai.auth import get_github_copilot_token
from logai.providers.llm import GitHubCopilotProvider, get_available_models


async def test_authentication():
    """Test 1: Check authentication status."""
    print("=" * 60)
    print("TEST 1: Authentication Status")
    print("=" * 60)

    token = get_github_copilot_token()
    if token:
        print(f"✓ Authenticated! Token prefix: {token[:10]}...")
        return True
    else:
        print("✗ Not authenticated. Run 'logai auth login' first.")
        return False


async def test_model_fetching():
    """Test 2: Fetch available models."""
    print("\n" + "=" * 60)
    print("TEST 2: Model List Fetching")
    print("=" * 60)

    try:
        models = await get_available_models()
        print(f"✓ Found {len(models)} models")
        print(f"  Sample models: {', '.join(models[:5])}...")
        return True
    except Exception as e:
        print(f"✗ Error fetching models: {e}")
        return False


async def test_basic_chat():
    """Test 3: Basic chat (non-streaming)."""
    print("\n" + "=" * 60)
    print("TEST 3: Basic Chat (Non-Streaming)")
    print("=" * 60)

    try:
        provider = GitHubCopilotProvider(model="claude-opus-4.6")
        print(f"  Using model: {provider.full_model_name}")

        messages = [{"role": "user", "content": "What is 2+2? Answer in one word."}]

        print("  Sending request...")
        response = await provider.chat(messages)

        print(f"✓ Response received!")
        print(f"  Content: {response.content}")
        print(f"  Finish reason: {response.finish_reason}")
        print(f"  Usage: {response.usage}")

        await provider.close()
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_streaming_chat():
    """Test 4: Streaming chat."""
    print("\n" + "=" * 60)
    print("TEST 4: Streaming Chat")
    print("=" * 60)

    try:
        provider = GitHubCopilotProvider(model="claude-opus-4.6")
        print(f"  Using model: {provider.full_model_name}")

        messages = [
            {
                "role": "user",
                "content": "Count from 1 to 5, one number per line. Be concise.",
            }
        ]

        print("  Streaming response: ", end="", flush=True)
        stream = await provider.chat(messages, stream=True)

        full_response = []
        async for chunk in stream:
            print(chunk, end="", flush=True)
            full_response.append(chunk)

        print(f"\n✓ Stream completed! Total: {''.join(full_response)}")

        await provider.close()
        return True
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_tool_calling():
    """Test 5: Tool calling (function calling)."""
    print("\n" + "=" * 60)
    print("TEST 5: Tool Calling")
    print("=" * 60)

    try:
        provider = GitHubCopilotProvider(model="claude-opus-4.6")
        print(f"  Using model: {provider.full_model_name}")

        # Define a simple tool
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_current_weather",
                    "description": "Get the current weather in a location",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "The city name, e.g. San Francisco",
                            },
                            "unit": {
                                "type": "string",
                                "enum": ["celsius", "fahrenheit"],
                            },
                        },
                        "required": ["location"],
                    },
                },
            }
        ]

        messages = [{"role": "user", "content": "What's the weather like in San Francisco?"}]

        print("  Sending request with tools...")
        response = await provider.chat(messages, tools=tools)

        print(f"✓ Response received!")
        print(f"  Content: {response.content}")
        print(f"  Finish reason: {response.finish_reason}")
        print(f"  Has tool calls: {response.has_tool_calls()}")

        if response.has_tool_calls():
            print(f"  Tool calls:")
            for tc in response.tool_calls:
                print(f"    - {tc['function']['name']}: {tc['function']['arguments']}")
        else:
            print("  (No tool calls - model may have responded directly or doesn't support tools)")

        await provider.close()
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_error_handling():
    """Test 6: Error handling (invalid model)."""
    print("\n" + "=" * 60)
    print("TEST 6: Error Handling")
    print("=" * 60)

    try:
        provider = GitHubCopilotProvider(model="invalid-model-that-doesnt-exist")
        print(f"  Using invalid model: {provider.full_model_name}")

        messages = [{"role": "user", "content": "Hello"}]

        print("  Sending request (should fail)...")
        try:
            response = await provider.chat(messages)
            print(f"✗ Request succeeded unexpectedly: {response.content}")
            await provider.close()
            return False
        except Exception as e:
            print(f"✓ Error caught as expected: {type(e).__name__}")
            print(f"  Message: {e}")
            await provider.close()
            return True
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    """Run all tests."""
    print("\n")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║     GitHub Copilot Provider Manual Test Suite            ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()

    results = []

    # Test 1: Authentication
    results.append(("Authentication", await test_authentication()))
    if not results[0][1]:
        print("\n⚠️  Cannot proceed without authentication. Run 'logai auth login'.")
        return

    # Test 2: Model fetching
    results.append(("Model Fetching", await test_model_fetching()))

    # Test 3: Basic chat
    results.append(("Basic Chat", await test_basic_chat()))

    # Test 4: Streaming
    results.append(("Streaming Chat", await test_streaming_chat()))

    # Test 5: Tool calling
    results.append(("Tool Calling", await test_tool_calling()))

    # Test 6: Error handling
    results.append(("Error Handling", await test_error_handling()))

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
        print("\n🎉 All tests passed!")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
