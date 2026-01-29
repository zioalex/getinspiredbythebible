#!/usr/bin/env python3
"""
Test script for OpenRouter auto-router fallback functionality.

This tests whether the auto-router plugin properly falls back from
free models to paid models when rate limits are hit.

Usage:
    export OPENROUTER_API_KEY=your-key
    python test_openrouter_fallback.py
"""

import os
import sys

# Check for API key
api_key = os.getenv("OPENROUTER_API_KEY")
if not api_key:
    print("ERROR: OPENROUTER_API_KEY environment variable not set")
    sys.exit(1)

from openai import OpenAI

client = OpenAI(
    api_key=api_key,
    base_url="https://openrouter.ai/api/v1",
)

# Test 1: Using auto-router plugin (same as api/providers/openrouter.py implementation)
print("\n=== Test 1: auto-router with plugins in extra_body ===")
print("This mimics the actual implementation in api/providers/openrouter.py")
try:
    response = client.chat.completions.create(
        model="openrouter/auto",
        messages=[{"role": "user", "content": "Say hello in one word"}],
        max_tokens=50,
        extra_body={
            "plugins": [
                {
                    "id": "auto-router",
                    "allowed_models": [
                        "meta-llama/llama-3.3-70b-instruct:free",
                        "meta-llama/llama-3.3-70b-instruct",
                    ],
                }
            ]
        },
    )
    print(f"Response: {response.choices[0].message.content}")
    print(f"Model used: {response.model}")
except Exception as e:
    print(f"Error: {e}")

# Test 2: Direct paid model call (baseline)
print("\n=== Test 2: Direct paid model call (baseline) ===")
try:
    response = client.chat.completions.create(
        model="meta-llama/llama-3.3-70b-instruct",
        messages=[{"role": "user", "content": "Say hello in one word"}],
        max_tokens=50,
    )
    print(f"Response: {response.choices[0].message.content}")
    print(f"Model used: {response.model}")
except Exception as e:
    print(f"Error: {e}")

# Test 3: Free model (to see if rate limited)
print("\n=== Test 3: Direct free model call (to check rate limit) ===")
try:
    response = client.chat.completions.create(
        model="meta-llama/llama-3.3-70b-instruct:free",
        messages=[{"role": "user", "content": "Say hello in one word"}],
        max_tokens=50,
    )
    print(f"Response: {response.choices[0].message.content}")
    print(f"Model used: {response.model}")
except Exception as e:
    print(f"Error (expected if rate limited): {e}")

# Test 4: Test the actual provider class
print("\n=== Test 4: Test actual OpenRouterProvider class ===")
try:
    import asyncio
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'api'))
    from providers.openrouter import OpenRouterProvider

    async def test_provider():
        provider = OpenRouterProvider(
            api_key=api_key,
            model="meta-llama/llama-3.3-70b-instruct:free",
            fallback_models=["meta-llama/llama-3.3-70b-instruct"],
            allow_fallbacks=True,
        )

        from providers.base import ChatMessage
        messages = [ChatMessage(role="user", content="Say hello in one word")]

        response = await provider.chat(messages=messages, max_tokens=50)
        print(f"Response: {response.content}")
        print(f"Model used: {response.model}")
        print(f"Provider: {response.provider}")

    asyncio.run(test_provider())
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
