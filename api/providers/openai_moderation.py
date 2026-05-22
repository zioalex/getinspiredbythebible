"""
OpenAI Moderation API provider (free, unlimited).

Uses the omni-moderation-latest model — a dedicated classification model that:
- Is free with no rate limits
- Takes ~100-150ms (much faster than generative LLM providers)
- Returns 13 category scores (float 0.0-1.0)
- Understands biblical context: "David killed Goliath" → violence score ~0.02

Endpoint: POST https://api.openai.com/v1/moderations
Auth: Bearer {api_key}

Used as Stage 2 in keyword_only and hybrid content safety modes.
"""

import hashlib
import logging

import httpx

from providers.azure_content_safety import ContentSafetyResult

logger = logging.getLogger(__name__)

OPENAI_MODERATION_ENDPOINT = "https://api.openai.com/v1/moderations"
OPENAI_MODERATION_MODEL = "omni-moderation-latest"

# self-harm/intent threshold for compassionate-response flag (not configurable —
# this is a stable behavioral guarantee, not a tunable accuracy knob)
_SELF_HARM_INTENT_FLAG_THRESHOLD = 0.1


class OpenAIModerationProvider:
    """
    OpenAI Moderation API provider.

    Returns ContentSafetyResult compatible with the existing provider interface.
    Category scores (floats 0.0-1.0) are scaled to int 0-100 before storing in
    ContentSafetyResult.categories to satisfy the dict[str, int] type contract.

    Transport errors (timeout, HTTP errors) are re-raised so the orchestrator
    (ContentSafetyService) can apply the appropriate fallback.
    """

    def __init__(self, api_key: str, threshold: float = 0.5, timeout: int = 3):
        self.api_key = api_key
        self.threshold = threshold
        self.timeout = timeout

    def _interpret_result(self, scores: dict[str, float], text_hash: str) -> ContentSafetyResult:
        """
        Map OpenAI Moderation category scores to a ContentSafetyResult.

        Decision order (stops at first match):
        1. violence or violence/graphic >= threshold → BLOCK
        2. harassment/threatening >= threshold → BLOCK
        3. self-harm/instructions >= threshold → BLOCK
        4. hate or hate/threatening >= threshold → BLOCK
        5. sexual/minors or sexual >= threshold → BLOCK
        6. self-harm/intent > 0.1 AND violence < 0.1 AND hate < 0.1 → ALLOW + compassionate flag
        7. else → ALLOW clean
        """
        violence = scores.get("violence", 0.0)
        violence_graphic = scores.get("violence/graphic", 0.0)
        harassment_threatening = scores.get("harassment/threatening", 0.0)
        self_harm_instructions = scores.get("self-harm/instructions", 0.0)
        self_harm_intent = scores.get("self-harm/intent", 0.0)
        hate = scores.get("hate", 0.0)
        hate_threatening = scores.get("hate/threatening", 0.0)
        sexual = scores.get("sexual", 0.0)
        sexual_minors = scores.get("sexual/minors", 0.0)

        threshold = self.threshold
        int_categories = {k: int(round(v * 100)) for k, v in scores.items()}

        if violence >= threshold or violence_graphic >= threshold:
            logger.warning(
                "OpenAI Moderation: violence detected",
                extra={
                    "text_hash": text_hash,
                    "violence": violence,
                    "violence_graphic": violence_graphic,
                },
            )
            return ContentSafetyResult(
                allowed=False,
                reason="violence_or_threat_detected",
                categories=int_categories,
            )

        if harassment_threatening >= threshold:
            logger.warning(
                "OpenAI Moderation: threatening harassment detected",
                extra={"text_hash": text_hash, "harassment_threatening": harassment_threatening},
            )
            return ContentSafetyResult(
                allowed=False,
                reason="violence_or_threat_detected",
                categories=int_categories,
            )

        if self_harm_instructions >= threshold:
            logger.warning(
                "OpenAI Moderation: self-harm instructions detected",
                extra={"text_hash": text_hash, "self_harm_instructions": self_harm_instructions},
            )
            return ContentSafetyResult(
                allowed=False,
                reason="self_harm_instructions_detected",
                categories=int_categories,
            )

        if hate >= threshold or hate_threatening >= threshold:
            logger.warning(
                "OpenAI Moderation: hate speech detected",
                extra={"text_hash": text_hash, "hate": hate, "hate_threatening": hate_threatening},
            )
            return ContentSafetyResult(
                allowed=False,
                reason="hate_speech_detected",
                categories=int_categories,
            )

        if sexual_minors >= threshold or sexual >= threshold:
            logger.warning(
                "OpenAI Moderation: sexual content detected",
                extra={"text_hash": text_hash, "sexual": sexual, "sexual_minors": sexual_minors},
            )
            return ContentSafetyResult(
                allowed=False,
                reason="sexual_content_detected",
                categories=int_categories,
            )

        # Help-seeking: self-harm intent without violence/hate → compassionate response
        if (
            self_harm_intent > _SELF_HARM_INTENT_FLAG_THRESHOLD
            and violence < _SELF_HARM_INTENT_FLAG_THRESHOLD
            and hate < _SELF_HARM_INTENT_FLAG_THRESHOLD
        ):
            logger.info(
                "OpenAI Moderation: help-seeking detected",
                extra={"text_hash": text_hash, "self_harm_intent": self_harm_intent},
            )
            return ContentSafetyResult(
                allowed=True,
                reason="possible_help_seeking",
                categories=int_categories,
                is_help_seeking=True,
                compassionate_response_needed=True,
            )

        logger.debug("OpenAI Moderation: clean", extra={"text_hash": text_hash})
        return ContentSafetyResult(
            allowed=True,
            reason="clean",
            categories=int_categories,
        )

    async def analyze_text(self, text: str, language: str = "en") -> ContentSafetyResult:
        """
        Analyze text using the OpenAI Moderation API.

        Args:
            text: The text to analyze (truncated to 2000 chars)
            language: ISO 639-1 language code (not used by the API, kept for interface parity)

        Returns:
            ContentSafetyResult with decision and category scores

        Raises:
            httpx.TimeoutException: If request exceeds timeout (caller should fail-open)
            httpx.HTTPError: If API returns an error (caller should fail-open)
        """
        text_hash = hashlib.sha256(text.encode()).hexdigest()[:16]

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                OPENAI_MODERATION_ENDPOINT,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": OPENAI_MODERATION_MODEL,
                    "input": text[:2000],
                },
            )
            response.raise_for_status()
            data = response.json()

        scores: dict[str, float] = data["results"][0]["category_scores"]

        logger.debug(
            "OpenAI Moderation API call succeeded",
            extra={
                "text_hash": text_hash,
                "language": language,
                "flagged": data["results"][0].get("flagged", False),
                "top_scores": dict(sorted(scores.items(), key=lambda x: x[1], reverse=True)[:3]),
            },
        )

        return self._interpret_result(scores, text_hash)
