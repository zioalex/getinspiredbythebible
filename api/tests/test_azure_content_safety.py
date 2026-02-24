"""
Tests for Azure Content Safety provider.
All Azure API calls are mocked — no real API keys needed.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_missing_sdk_gracefully():
    """Test provider handles missing SDK gracefully."""
    with patch.dict(
        "sys.modules", {"azure.ai.contentsafety": None, "azure.core.credentials": None}
    ):
        # Force reimport to trigger ImportError
        import importlib

        import providers.azure_content_safety

        importlib.reload(providers.azure_content_safety)

        from providers.azure_content_safety import AzureContentSafetyProvider

        provider = AzureContentSafetyProvider(
            "https://test.cognitiveservices.azure.com/", "test-key"
        )
        assert provider._sdk_available is False


async def test_help_seeking_allowed():
    """Test help-seeking detection (SelfHarm but no Violence/Hate)."""
    # Mock Azure SDK modules before import
    with patch.dict(
        "sys.modules",
        {
            "azure": MagicMock(),
            "azure.ai": MagicMock(),
            "azure.ai.contentsafety": MagicMock(),
            "azure.ai.contentsafety.models": MagicMock(),
            "azure.core": MagicMock(),
            "azure.core.credentials": MagicMock(),
        },
    ):
        from providers.azure_content_safety import AzureContentSafetyProvider

        # Mock Azure SDK response
        mock_response = MagicMock()
        mock_category_hate = MagicMock(severity=0)
        mock_category_self_harm = MagicMock(severity=2)
        mock_category_sexual = MagicMock(severity=0)
        mock_category_violence = MagicMock(severity=0)
        mock_response.categories_analysis = [
            mock_category_hate,
            mock_category_self_harm,
            mock_category_sexual,
            mock_category_violence,
        ]

        # Mock client
        mock_client = MagicMock()
        mock_client.analyze_text = MagicMock(return_value=mock_response)

        provider = AzureContentSafetyProvider(
            endpoint="https://test.cognitiveservices.azure.com/",
            key="test-key",
            threshold=4,
        )
        provider._client = mock_client
        provider._sdk_available = True

        # Mock asyncio.get_event_loop().run_in_executor
        with patch("asyncio.get_event_loop") as mock_loop:
            mock_executor = AsyncMock(return_value=mock_response)
            mock_loop.return_value.run_in_executor = mock_executor

            result = await provider.analyze_text("I want to die, can you help?", "en")

            assert result.allowed is True
            assert result.reason == "help_seeking_detected"
            assert result.is_help_seeking is True
            assert result.compassionate_response_needed is True
            assert result.categories["self_harm"] == 2
            assert result.categories["violence"] == 0


async def test_harmful_intent_blocked():
    """Test harmful intent blocked (Violence >= threshold)."""
    with patch.dict(
        "sys.modules",
        {
            "azure": MagicMock(),
            "azure.ai": MagicMock(),
            "azure.ai.contentsafety": MagicMock(),
            "azure.ai.contentsafety.models": MagicMock(),
            "azure.core": MagicMock(),
            "azure.core.credentials": MagicMock(),
        },
    ):
        from providers.azure_content_safety import AzureContentSafetyProvider

        # Mock Azure SDK response with high violence
        mock_response = MagicMock()
        mock_category_hate = MagicMock(severity=0)
        mock_category_self_harm = MagicMock(severity=0)
        mock_category_sexual = MagicMock(severity=0)
        mock_category_violence = MagicMock(severity=6)
        mock_response.categories_analysis = [
            mock_category_hate,
            mock_category_self_harm,
            mock_category_sexual,
            mock_category_violence,
        ]

        mock_client = MagicMock()
        mock_client.analyze_text = MagicMock(return_value=mock_response)

        provider = AzureContentSafetyProvider(
            endpoint="https://test.cognitiveservices.azure.com/",
            key="test-key",
            threshold=4,
        )
        provider._client = mock_client
        provider._sdk_available = True

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_executor = AsyncMock(return_value=mock_response)
            mock_loop.return_value.run_in_executor = mock_executor

            result = await provider.analyze_text("violent threat", "en")

            assert result.allowed is False
            assert result.reason == "harmful_intent_detected"
            assert result.is_help_seeking is False
            assert result.categories["violence"] == 6


async def test_clean_content_allowed():
    """Test clean content is allowed."""
    with patch.dict(
        "sys.modules",
        {
            "azure": MagicMock(),
            "azure.ai": MagicMock(),
            "azure.ai.contentsafety": MagicMock(),
            "azure.ai.contentsafety.models": MagicMock(),
            "azure.core": MagicMock(),
            "azure.core.credentials": MagicMock(),
        },
    ):
        from providers.azure_content_safety import AzureContentSafetyProvider

        # Mock Azure SDK response with all zeros
        mock_response = MagicMock()
        mock_response.categories_analysis = [
            MagicMock(severity=0),  # hate
            MagicMock(severity=0),  # self_harm
            MagicMock(severity=0),  # sexual
            MagicMock(severity=0),  # violence
        ]

        mock_client = MagicMock()
        provider = AzureContentSafetyProvider(
            endpoint="https://test.cognitiveservices.azure.com/",
            key="test-key",
            threshold=4,
        )
        provider._client = mock_client
        provider._sdk_available = True

        with patch("asyncio.get_event_loop") as mock_loop:
            mock_executor = AsyncMock(return_value=mock_response)
            mock_loop.return_value.run_in_executor = mock_executor

            result = await provider.analyze_text("I need guidance", "en")

            assert result.allowed is True
            assert result.reason == "clean"
            assert result.max_severity == 0


async def test_sdk_unavailable_raises_error():
    """Test that analyze_text raises RuntimeError if SDK unavailable."""
    from providers.azure_content_safety import AzureContentSafetyProvider

    provider = AzureContentSafetyProvider(
        endpoint="https://test.cognitiveservices.azure.com/",
        key="test-key",
    )
    provider._sdk_available = False
    provider._client = None

    with pytest.raises(RuntimeError, match="Azure Content Safety SDK not available"):
        await provider.analyze_text("test", "en")
