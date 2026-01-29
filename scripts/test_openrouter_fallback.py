#!/usr/bin/env python3
"""
Test script for OpenRouter rate limit fallback functionality.

This tests whether we properly fall back from free models to paid models
when rate limits (429 errors) are hit.

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

# Test 1: Direct API test - simulate rate limit scenario
print("\n=== Test 1: Direct API - free model (may be rate limited) ===")
from openai import OpenAI, RateLimitError

client = OpenAI(
    api_key=api_key,
    base_url="https://openrouter.ai/api/v1",
)

try:
    response = client.chat.completions.create(
        model="meta-llama/llama-3.3-70b-instruct:free",
        messages=[{"role": "user", "content": "Say hello in one word"}],
        max_tokens=50,
    )
    print(f"SUCCESS: {response.choices[0].message.content}")
    print(f"Model used: {response.model}")
except RateLimitError as e:
    print(f"RATE LIMITED (expected): {e}")
except Exception as e:
    print(f"ERROR: {e}")

# Test 2: Direct API test - paid model (should always work)
print("\n=== Test 2: Direct API - paid model (should work) ===")
try:
    response = client.chat.completions.create(
        model="meta-llama/llama-3.3-70b-instruct",
        messages=[{"role": "user", "content": "Say hello in one word"}],
        max_tokens=50,
    )
    print(f"SUCCESS: {response.choices[0].message.content}")
    print(f"Model used: {response.model}")
except Exception as e:
    print(f"ERROR: {e}")

# Test 3: Test the actual provider class with fallback
print("\n=== Test 3: OpenRouterProvider with explicit fallback ===")
try:
    import asyncio
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'api'))
    from providers.openrouter import OpenRouterProvider
    from providers.base import ChatMessage

    async def test_provider_with_fallback():
        provider = OpenRouterProvider(
            api_key=api_key,
            model="meta-llama/llama-3.3-70b-instruct:free",
            fallback_models=["meta-llama/llama-3.3-70b-instruct"],
            allow_fallbacks=True,
        )

        messages = [ChatMessage(role="user", content="Say hello in one word")]

        print(f"Primary model: {provider.model}")
        print(f"Fallback models: {provider.fallback_models}")
        print("Sending request (may take time if rate limited and falling back)...")

        response = await provider.chat(messages=messages, max_tokens=50)
        print(f"SUCCESS!")
        print(f"Response: {response.content}")
        print(f"Model used: {response.model}")
        print(f"Provider: {response.provider}")

        # Check if we used fallback
        if response.model == "meta-llama/llama-3.3-70b-instruct":
            print("\n*** FALLBACK WAS USED ***")
        elif ":free" in response.model:
            print("\n*** PRIMARY (FREE) MODEL SUCCEEDED ***")

    asyncio.run(test_provider_with_fallback())
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()

# Test 4: Test streaming with fallback
print("\n=== Test 4: OpenRouterProvider streaming with fallback ===")
try:
    import asyncio
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'api'))
    from providers.openrouter import OpenRouterProvider
    from providers.base import ChatMessage

    async def test_streaming_with_fallback():
        provider = OpenRouterProvider(
            api_key=api_key,
            model="meta-llama/llama-3.3-70b-instruct:free",
            fallback_models=["meta-llama/llama-3.3-70b-instruct"],
            allow_fallbacks=True,
        )

        messages = [ChatMessage(role="user", content="Say hello in one word")]

        print("Streaming response...")
        chunks = []
        async for chunk in provider.chat_stream(messages=messages, max_tokens=50):
            chunks.append(chunk)
            print(chunk, end="", flush=True)

        full_response = "".join(chunks)
        print(f"\n\nFull response: {full_response}")

    asyncio.run(test_streaming_with_fallback())
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n=== All tests completed ===")
