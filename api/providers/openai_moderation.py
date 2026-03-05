"""
OpenAI Moderation API provider.

Uses omni-moderation-latest (free, unlimited) to detect harmful content
with context awareness — correctly distinguishes biblical violence discussion
from real harmful intent.

Auth: Bearer {OPENROUTER_API_KEY or OPENAI_API_KEY}
Endpoint: https://api.openai.com/v1/moderations
"""

import hashlib
import logging

import httpx

from providers.azure_content_safety import ContentSafetyResult

logger = logging.getLogger(__name__)


class OpenAIModerationProvider:
    """
    OpenAI Moderation API client using omni-moderation-latest.

    Free, unlimited, context-aware moderation that distinguishes
    biblical violence discussion from real harmful intent.

    Critical design:
    - Violence/harassment in biblical context → low scores → ALLOW
    - Real threats ("I want to bomb the school") → high scores → BLOCK
    - Help-seeking ("I want to die") → self-harm/intent only → ALLOW + compassionate
    """

    MODERATION_ENDPOINT = "https://api.openai.com/v1/moderations"
    MODEL = "omni-moderation-latest"

    def __init__(self, api_key: str, threshold: float = 0.5, timeout: int = 3):
        """
        Initialize OpenAI Moderation provider.

        Args:
            api_key: OpenAI or OpenRouter API key
            threshold: Block if category score >= threshold (default 0.5)
            timeout: Request timeout in seconds (default 3)
        """
        self.api_key = api_key
        self.threshold = threshold
        self.timeout = timeout

    def _interpret_scores(self, scores: dict[str, float], text_hash: str) -> ContentSafetyResult:
        """
        Interpret OpenAI moderation scores and return decision.

        Decision logic:
        1. Block: violence or threatening harassment
        2. Block: self-harm instructions
        3. Block: hate speech
        4. Allow + compassionate: self-harm intent only (help-seeking)
        5. Clean: all scores low

        Args:
            scores: Category scores from OpenAI (13 categories, 0.0-1.0)
            text_hash: Hashed text for logging

        Returns:
            ContentSafetyResult with decision and context
        """
        # Extract relevant scores
        violence = scores.get("violence", 0.0)
        harassment_threatening = scores.get("harassment/threatening", 0.0)
        self_harm_intent = scores.get("self-harm/intent", 0.0)
        self_harm_instructions = scores.get("self-harm/instructions", 0.0)
        hate = scores.get("hate", 0.0)
        hate_threatening = scores.get("hate/threatening", 0.0)

        # Convert to integer severity for consistency with Azure (0-10 scale)
        # OpenAI returns 0.0-1.0, we scale to 0-10 for category reporting
        categories = {k: int(v * 10) for k, v in scores.items()}

        # Decision logic
        # 1. Block: violence or threatening harassment
        if violence >= self.threshold or harassment_threatening >= self.threshold:
            logger.warning(
                "OpenAI Moderation: violence/threat detected",
                extra={
                    "text_hash": text_hash,
                    "violence": f"{violence:.3f}",
                    "harassment_threatening": f"{harassment_threatening:.3f}",
                    "threshold": self.threshold,
                },
            )
            return ContentSafetyResult(
                allowed=False,
                reason="violence_or_threat_detected",
                categories=categories,
            )

        # 2. Block: self-harm instructions
        if self_harm_instructions >= self.threshold:
            logger.warning(
                "OpenAI Moderation: self-harm instructions detected",
                extra={
                    "text_hash": text_hash,
                    "self_harm_instructions": f"{self_harm_instructions:.3f}",
                    "threshold": self.threshold,
                },
            )
            return ContentSafetyResult(
                allowed=False,
                reason="self_harm_instructions_detected",
                categories=categories,
            )

        # 3. Block: hate speech
        if hate >= self.threshold or hate_threatening >= self.threshold:
            logger.warning(
                "OpenAI Moderation: hate speech detected",
                extra={
                    "text_hash": text_hash,
                    "hate": f"{hate:.3f}",
                    "hate_threatening": f"{hate_threatening:.3f}",
                    "threshold": self.threshold,
                },
            )
            return ContentSafetyResult(
                allowed=False,
                reason="hate_speech_detected",
                categories=categories,
            )

        # 4. Allow + compassionate: self-harm intent only (help-seeking)
        # Low threshold (0.1) to catch help-seeking expressions
        if self_harm_intent > 0.1 and violence < 0.1 and hate < 0.1:
            logger.info(
                "OpenAI Moderation: help-seeking detected",
                extra={
                    "text_hash": text_hash,
                    "self_harm_intent": f"{self_harm_intent:.3f}",
                },
            )
            return ContentSafetyResult(
                allowed=True,
                reason="possible_help_seeking",
                is_help_seeking=True,
                compassionate_response_needed=True,
                categories=categories,
            )

        # 5. Clean
        logger.debug(
            "OpenAI Moderation: clean",
            extra={"text_hash": text_hash, "max_score": f"{max(scores.values()):.3f}"},
        )
        return ContentSafetyResult(
            allowed=True,
            reason="clean",
            categories=categories,
        )

    async def analyze_text(self, text: str, language: str = "en") -> ContentSafetyResult:
        """
        Analyze text using OpenAI Moderation API.

        Args:
            text: The text to analyze
            language: ISO 639-1 language code (not used by OpenAI, kept for interface consistency)

        Returns:
            ContentSafetyResult with decision

        Raises:
            httpx.HTTPError: If API call fails
            httpx.TimeoutException: If API call times out
        """
        text_hash = hashlib.sha256(text.encode()).hexdigest()[:16]

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.MODERATION_ENDPOINT,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.MODEL,
                        "input": text[:2000],  # Reasonable limit, API accepts more
                    },
                )
                response.raise_for_status()
                data = response.json()

                # Extract category scores
                scores = data["results"][0]["category_scores"]

                # Log API call
                logger.debug(
                    "OpenAI Moderation API call succeeded",
                    extra={
                        "text_hash": text_hash,
                        "language": language,
                        "status_code": response.status_code,
                    },
                )

                # Interpret scores and return decision
                return self._interpret_scores(scores, text_hash)

        except httpx.TimeoutException:
            logger.warning(
                "OpenAI Moderation API timeout",
                extra={"text_hash": text_hash, "timeout": self.timeout},
            )
            raise

        except httpx.HTTPError as e:
            logger.error(
                "OpenAI Moderation API error",
                extra={
                    "text_hash": text_hash,
                    "error": str(e),
                    "status_code": (
                        getattr(e.response, "status_code", None) if hasattr(e, "response") else None
                    ),
                },
            )
            raise
