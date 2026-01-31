#!/usr/bin/env python3
"""
Verify OpenRouter Model Availability

This script checks if the configured OpenRouter models are available.
Use in CI to catch model deprecation/renaming early.

Usage:
    # Check default models
    python verify_openrouter_models.py

    # Check specific models
    python verify_openrouter_models.py meta-llama/llama-3.3-70b-instruct:free google/gemma-2-9b-it:free

    # Use specific API key
    OPENROUTER_API_KEY=sk-or-v1-xxx python verify_openrouter_models.py

Environment Variables:
    OPENROUTER_API_KEY: Your OpenRouter API key (required)
    OPENROUTER_MODEL: Primary model to check (optional)
    OPENROUTER_FALLBACK_MODELS: Comma-separated fallback models (optional)
"""

import asyncio
import os
import sys
from typing import NamedTuple

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

try:
    from openai import APIStatusError, AsyncOpenAI
except ImportError:
    print("ERROR: openai package not installed. Run: pip install openai")
    sys.exit(1)


class ModelCheckResult(NamedTuple):
    model: str
    available: bool
    message: str


# Default models to check if none specified
DEFAULT_MODELS = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemma-2-9b-it:free",
    "mistralai/mistral-7b-instruct:free",
]


async def check_model(client: AsyncOpenAI, model: str) -> ModelCheckResult:
    """Check if a model is available on OpenRouter."""
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=5,
        )
        if response and response.choices:
            actual_model = response.model or model
            return ModelCheckResult(
                model=model,
                available=True,
                message=f"OK (responded as: {actual_model})",
            )
        return ModelCheckResult(
            model=model,
            available=False,
            message="Empty response",
        )
    except APIStatusError as e:
        if e.status_code == 404:
            return ModelCheckResult(
                model=model,
                available=False,
                message=f"NOT FOUND (404): {e.message}",
            )
        elif e.status_code == 429:
            # Rate limited means model exists
            return ModelCheckResult(
                model=model,
                available=True,
                message="OK (rate limited but exists)",
            )
        elif e.status_code == 401:
            return ModelCheckResult(
                model=model,
                available=False,
                message="UNAUTHORIZED: Check your API key",
            )
        else:
            return ModelCheckResult(
                model=model,
                available=False,
                message=f"ERROR ({e.status_code}): {e.message}",
            )
    except Exception as e:
        return ModelCheckResult(
            model=model,
            available=False,
            message=f"ERROR: {str(e)}",
        )


async def main():
    # Get API key
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("ERROR: OPENROUTER_API_KEY environment variable not set")
        print("Get your API key at: https://openrouter.ai/keys")
        sys.exit(1)

    # Get models to check
    if len(sys.argv) > 1:
        # Models from command line
        models = sys.argv[1:]
    else:
        # Models from environment or defaults
        models = []

        # Add primary model from env
        primary = os.environ.get("OPENROUTER_MODEL")
        if primary:
            models.append(primary)

        # Add fallback models from env
        fallbacks = os.environ.get("OPENROUTER_FALLBACK_MODELS", "")
        if fallbacks:
            models.extend([m.strip() for m in fallbacks.split(",") if m.strip()])

        # Use defaults if nothing configured
        if not models:
            print("No models specified, checking defaults...")
            models = DEFAULT_MODELS

    # Create client
    client = AsyncOpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        max_retries=0,
    )

    print(f"\nChecking {len(models)} model(s) on OpenRouter...\n")
    print("-" * 70)

    results = []
    for model in models:
        result = await check_model(client, model)
        results.append(result)

        status = "✓" if result.available else "✗"
        print(f"{status} {result.model}")
        print(f"  {result.message}")
        print()

    print("-" * 70)

    # Summary
    available = sum(1 for r in results if r.available)
    total = len(results)

    if available == total:
        print(f"\n✓ All {total} models are available")
        sys.exit(0)
    else:
        unavailable = [r.model for r in results if not r.available]
        print(f"\n✗ {total - available}/{total} models UNAVAILABLE:")
        for model in unavailable:
            print(f"  - {model}")
        print("\nCheck available models at: https://openrouter.ai/models")
        print("Update your configuration with valid model names.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
