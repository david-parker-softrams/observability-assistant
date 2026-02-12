#!/usr/bin/env python3
"""Quick test script to verify GitHub Copilot integration."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from logai.config.settings import LogAISettings
from logai.providers.llm.litellm_provider import LiteLLMProvider
from logai.auth import get_github_copilot_token


async def test_github_copilot():
    """Test GitHub Copilot provider integration."""

    print("=" * 60)
    print("GitHub Copilot Integration Test")
    print("=" * 60)

    # Step 1: Check authentication
    print("\n1. Checking authentication...")
    token = get_github_copilot_token()
    if not token:
        print("❌ Not authenticated!")
        print("Please run: logai auth login")
        return False
    print(f"✓ Authenticated (token: {token[:10]}...)")

    # Step 2: Create settings with GitHub Copilot
    print("\n2. Creating settings...")
    settings = LogAISettings(
        llm_provider="github-copilot",
        github_copilot_model="gpt-4o-mini",
    )
    print(f"✓ Settings created")
    print(f"  Provider: {settings.llm_provider}")
    print(f"  Model: {settings.github_copilot_model}")

    # Step 3: Create provider
    print("\n3. Creating provider...")
    try:
        provider = LiteLLMProvider.from_settings(settings)
        print(f"✓ Provider created: {type(provider).__name__}")
    except Exception as e:
        print(f"❌ Failed to create provider: {e}")
        return False

    # Step 4: Test basic chat
    print("\n4. Testing basic chat...")
    try:
        messages = [
            {"role": "user", "content": "Say 'Hello from GitHub Copilot!' and nothing else."}
        ]

        print("  Sending request...")
        response = await provider.chat(messages)
        print(f"✓ Response received!")
        print(f"  Content: {response.content}")
        print(f"  Finish reason: {response.finish_reason}")
        print(f"  Tokens: {response.usage}")

    except Exception as e:
        print(f"❌ Chat failed: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        await provider.close()

    print("\n" + "=" * 60)
    print("✓ All tests passed!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = asyncio.run(test_github_copilot())
    sys.exit(0 if success else 1)
