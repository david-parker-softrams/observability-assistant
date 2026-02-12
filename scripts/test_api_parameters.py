#!/usr/bin/env python3
"""Test which GitHub Copilot API parameters are accepted/rejected."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import httpx
from logai.auth import get_github_copilot_token


async def test_parameter(name: str, body: dict) -> tuple[str, int, str]:
    """Test a specific parameter combination."""
    token = get_github_copilot_token()

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "https://api.githubcopilot.com/chat/completions",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=30.0,
            )

            if response.status_code == 200:
                return (name, response.status_code, "✅ ACCEPTED")
            else:
                error = response.text[:100] if response.text else "No error message"
                return (name, response.status_code, f"❌ REJECTED: {error}")
        except Exception as e:
            return (name, 0, f"❌ ERROR: {str(e)[:100]}")


async def main():
    """Run comprehensive parameter tests."""
    print("=" * 70)
    print("GitHub Copilot API Parameter Testing")
    print("=" * 70)
    print()

    # Base message for all tests
    base_body = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "Say hi"}],
    }

    # Test cases
    tests = [
        ("Minimal (baseline)", base_body.copy()),
        ("+ stream: true", {**base_body, "stream": True}),
        ("+ stream: false", {**base_body, "stream": False}),
        ("+ temperature: 0.7", {**base_body, "temperature": 0.7}),
        ("+ temperature: 0.0", {**base_body, "temperature": 0.0}),
        ("+ max_tokens: 100", {**base_body, "max_tokens": 100}),
        ("+ top_p: 1.0", {**base_body, "top_p": 1.0}),
        ("+ top_p: 0.9", {**base_body, "top_p": 0.9}),
        ("+ n: 1", {**base_body, "n": 1}),
        ("+ presence_penalty: 0.0", {**base_body, "presence_penalty": 0.0}),
        ("+ frequency_penalty: 0.0", {**base_body, "frequency_penalty": 0.0}),
        ("+ top_p + stream", {**base_body, "top_p": 1.0, "stream": True}),
    ]

    results = []
    for i, (name, body) in enumerate(tests):
        if i > 0:
            await asyncio.sleep(4)  # Avoid rate limiting

        print(f"Test {i + 1}/{len(tests)}: {name}...", end=" ", flush=True)
        result = await test_parameter(name, body)
        results.append(result)
        print(result[2])

    # Summary
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print()

    accepted = [r for r in results if "✅" in r[2]]
    rejected = [r for r in results if "❌" in r[2]]

    print(f"✅ ACCEPTED PARAMETERS ({len(accepted)}):")
    for name, status, msg in accepted:
        print(f"   - {name}")

    print()
    print(f"❌ REJECTED PARAMETERS ({len(rejected)}):")
    for name, status, msg in rejected:
        print(f"   - {name} (HTTP {status})")

    print()
    print("=" * 70)
    print("RECOMMENDATION")
    print("=" * 70)
    print()
    print("Only include parameters that are consistently accepted.")
    print("Omit parameters that cause 403 errors or intermittent failures.")


if __name__ == "__main__":
    asyncio.run(main())
