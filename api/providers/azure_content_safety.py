"""
Azure Content Safety API provider for context-aware harm detection.

Uses Azure Content Safety F0 (free) tier: 5,000 text records/month.
Provides context-aware analysis that distinguishes help-seeking from harmful intent.
"""

import asyncio
import hashlib
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from azure.ai.contentsafety import ContentSafetyClient

logger = logging.getLogger(__name__)


@dataclass
class ContentSafetyResult:
    """Result from content safety analysis."""

    allowed: bool
    reason: str = "clean"
    categories: dict[str, int] = field(default_factory=dict)
    max_severity: int = 0
    is_help_seeking: bool = False
    compassionate_response_needed: bool = False
    pattern_matched: str | None = None
    language: str = "en"


class AzureContentSafetyProvider:
    """
    Azure Content Safety API client.

    Uses the Azure Content Safety SDK to analyze text for harmful content.
    Implements the critical help-seeking vs harmful intent distinction:
    - SelfHarm detected but no Violence/Hate → likely help-seeking → ALLOW with compassion
    - Violence/Hate detected → harmful intent → BLOCK

    Falls back gracefully if SDK not installed or API unavailable.
    """

    def __init__(self, endpoint: str, key: str, threshold: int = 4):
        self.endpoint = endpoint
        self.key = key
        self.threshold = threshold
        self._client: Optional["ContentSafetyClient"] = None
        self._sdk_available = False
        self._init_client()

    def _init_client(self) -> None:
        """Initialize Azure Content Safety client, handling missing SDK gracefully."""
        try:
            from azure.ai.contentsafety import ContentSafetyClient
            from azure.core.credentials import AzureKeyCredential

            self._client = ContentSafetyClient(
                endpoint=self.endpoint,
                credential=AzureKeyCredential(self.key),
            )
            self._sdk_available = True
            logger.info("Azure Content Safety client initialized")
        except ImportError:
            logger.warning(
                "azure-ai-contentsafety SDK not installed. "
                "Install with: pip install azure-ai-contentsafety"
            )
            self._sdk_available = False
        except Exception as e:
            logger.error("Failed to initialize Azure Content Safety client: %s", e)
            self._sdk_available = False

    async def analyze_text(  # noqa: C901
        self, text: str, language: str = "en"
    ) -> ContentSafetyResult:
        """
        Analyze text for harmful content using Azure Content Safety API.

        Critical logic: Distinguishes help-seeking (SelfHarm only, low severity)
        from harmful intent (Violence/Hate/high severity).

        Returns ContentSafetyResult with allowed=True for help-seeking.
        Raises exception if API call fails (caller should handle fallback).
        """
        if not self._sdk_available or self._client is None:
            raise RuntimeError("Azure Content Safety SDK not available")

        try:
            from azure.ai.contentsafety.models import AnalyzeTextOptions

            # Run sync SDK call in thread pool (SDK is synchronous)
            loop = asyncio.get_event_loop()
            request = AnalyzeTextOptions(text=text[:1000])  # API limit
            response = await loop.run_in_executor(None, self._client.analyze_text, request)

            # Extract severity scores (0-6 scale)
            hate_severity = (
                response.categories_analysis[0].severity if response.categories_analysis else 0
            )
            self_harm_severity = (
                response.categories_analysis[1].severity
                if len(response.categories_analysis) > 1
                else 0
            )
            sexual_severity = (
                response.categories_analysis[2].severity
                if len(response.categories_analysis) > 2
                else 0
            )
            violence_severity = (
                response.categories_analysis[3].severity
                if len(response.categories_analysis) > 3
                else 0
            )

            # Try named access as fallback
            try:
                for cat in response.categories_analysis:
                    name = cat.category.lower() if hasattr(cat, "category") else ""
                    if "hate" in name:
                        hate_severity = cat.severity
                    elif "selfharm" in name or "self_harm" in name:
                        self_harm_severity = cat.severity
                    elif "sexual" in name:
                        sexual_severity = cat.severity
                    elif "violence" in name:
                        violence_severity = cat.severity
            except Exception:
                pass  # Use positional values above

            categories = {
                "hate": hate_severity,
                "self_harm": self_harm_severity,
                "sexual": sexual_severity,
                "violence": violence_severity,
            }
            max_severity = max(categories.values())

            # CRITICAL: Distinguish help-seeking from harmful intent
            # Help-seeking = self-harm signal but NO violence/hate directed at others
            is_help_seeking = (
                self_harm_severity > 0
                and violence_severity == 0
                and hate_severity == 0
                and self_harm_severity < self.threshold
            )

            # Determine if allowed
            if is_help_seeking:
                allowed = True
                reason = "help_seeking_detected"
            elif max_severity >= self.threshold:
                allowed = False
                reason = "harmful_intent_detected"
            else:
                allowed = True
                reason = "clean"

            text_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
            logger.info(
                "Azure Content Safety analysis complete",
                extra={
                    "text_hash": text_hash,
                    "language": language,
                    "max_severity": max_severity,
                    "is_help_seeking": is_help_seeking,
                    "allowed": allowed,
                    "reason": reason,
                },
            )

            return ContentSafetyResult(
                allowed=allowed,
                reason=reason,
                categories=categories,
                max_severity=max_severity,
                is_help_seeking=is_help_seeking,
                compassionate_response_needed=is_help_seeking,
                language=language,
            )

        except Exception as e:
            logger.error("Azure Content Safety API call failed: %s", e)
            raise
