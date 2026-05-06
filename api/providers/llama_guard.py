"""
Llama Guard 4 content safety provider via OpenRouter.

Uses meta-llama/llama-guard-4-12b (purpose-built for content safety classification)
via the OpenRouter chat completions API, using the existing OPENROUTER_API_KEY.

No new API keys needed. Cost: $0.02/M tokens (essentially free at our volume).

Llama Guard 4 correctly handles biblical violence context:
- "David killed Goliath" → safe
- "I want to build a bomb" → unsafe (S9)
- "I hate all people of a certain race" → unsafe (S10)
"""

import hashlib
import logging

import httpx

from config import settings
from providers.azure_content_safety import ContentSafetyResult

logger = logging.getLogger(__name__)

# Llama Guard 4 prompt template (critical: must use exact format)
LLAMA_GUARD_PROMPT = """<|begin_of_text|><|start_header_id|>user<|end_header_id|>

Task: Check if there is unsafe content in the 'User' messages in the conversation according to our safety policy with the below categories.

<BEGIN UNSAFE CONTENT CATEGORIES>
S1: Violent Crimes.
S2: Non-Violent Crimes.
S3: Sex-Related Crimes.
S4: Child Sexual Exploitation.
S5: Defamation.
S6: Specialized Advice.
S7: Privacy.
S8: Intellectual Property.
S9: Indiscriminate Weapons.
S10: Hate.
S11: Suicide & Self-Harm.
S12: Sexual Content.
S13: Elections.
<END UNSAFE CONTENT CATEGORIES>

<BEGIN CONVERSATION>
User: {user_message}
<END CONVERSATION>

Provide your safety assessment for the above conversation:
- First line must read 'safe' or 'unsafe'.
- If unsafe, a second line must include a comma-separated list of violated categories.<|eot_id|><|start_header_id|>assistant<|end_header_id|>

"""


class LlamaGuardProvider:
    """
    Llama Guard 4 content safety provider via OpenRouter.

    Uses meta-llama/llama-guard-4-12b for context-aware content moderation that:
    - Distinguishes biblical violence discussion from real harmful intent
    - Detects nuanced harmful intent vs help-seeking
    - Returns binary safe/unsafe with category codes
    """

    OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
    MODEL = "meta-llama/llama-guard-4-12b"
    REFERER = settings.production_frontend_url
    APP_TITLE = "VoxQuieta"

    def __init__(self, api_key: str, threshold: float = 0.5, timeout: int = 10):
        """
        Initialize Llama Guard provider.

        Args:
            api_key: OpenRouter API key
            threshold: Unused (binary safe/unsafe output), kept for interface consistency
            timeout: Request timeout in seconds (default 10)
        """
        self.api_key = api_key
        self.threshold = threshold  # unused but kept for interface consistency
        self.timeout = timeout

    def _parse_llama_guard_response(self, response_text: str) -> tuple[bool, list[str]]:
        """
        Parse Llama Guard 4 response.

        Expected format:
            safe
        OR:
            unsafe
            S1,S9

        Args:
            response_text: Raw response text from Llama Guard 4

        Returns:
            Tuple of (is_safe, violated_categories)
        """
        lines = response_text.strip().split("\n")
        if not lines:
            logger.warning("Empty Llama Guard response, treating as safe")
            return True, []

        first_line = lines[0].strip().lower()
        is_safe = first_line == "safe"

        violated_categories = []
        if not is_safe and len(lines) > 1:
            # Parse comma-separated category codes
            categories_str = lines[1].strip()
            violated_categories = [cat.strip() for cat in categories_str.split(",") if cat.strip()]

        return is_safe, violated_categories

    def _map_categories_to_result(
        self, is_safe: bool, violated_categories: list[str], text_hash: str
    ) -> ContentSafetyResult:
        """
        Map Llama Guard 4 categories to ContentSafetyResult.

        Category mapping:
        - S1 (Violent Crimes), S2 (Non-Violent Crimes), S9 (Indiscriminate Weapons) → violence_or_threat_detected
        - S10 (Hate) → hate_speech_detected
        - S11 (Suicide & Self-Harm) → possible_help_seeking (allow with compassion)
        - S3, S4, S12 (sexual content) → sexual_content_detected
        - Any other unsafe → unsafe_content_detected

        Args:
            is_safe: Whether content is safe
            violated_categories: List of violated category codes (e.g. ["S1", "S9"])
            text_hash: Hashed text for logging

        Returns:
            ContentSafetyResult with decision
        """
        if is_safe:
            logger.debug("Llama Guard: safe", extra={"text_hash": text_hash})
            return ContentSafetyResult(
                allowed=True,
                reason="clean",
            )

        # Handle S11 (Suicide & Self-Harm) specially - allow with compassionate response
        if violated_categories == ["S11"]:
            logger.info(
                "Llama Guard: help-seeking detected",
                extra={"text_hash": text_hash, "categories": violated_categories},
            )
            return ContentSafetyResult(
                allowed=True,
                reason="possible_help_seeking",
                is_help_seeking=True,
                compassionate_response_needed=True,
            )

        # Block all other unsafe content
        # Determine specific reason based on categories
        if any(cat in violated_categories for cat in ["S1", "S2", "S9"]):
            reason = "violence_or_threat_detected"
        elif "S10" in violated_categories:
            reason = "hate_speech_detected"
        elif any(cat in violated_categories for cat in ["S3", "S4", "S12"]):
            reason = "sexual_content_detected"
        else:
            reason = "unsafe_content_detected"

        logger.warning(
            f"Llama Guard: {reason}",
            extra={
                "text_hash": text_hash,
                "categories": violated_categories,
                "reason": reason,
            },
        )

        return ContentSafetyResult(
            allowed=False,
            reason=reason,
        )

    async def analyze_text(self, text: str, language: str = "en") -> ContentSafetyResult:
        """
        Analyze text using Llama Guard 4 via OpenRouter.

        Args:
            text: The text to analyze
            language: ISO 639-1 language code (not used by Llama Guard, kept for interface consistency)

        Returns:
            ContentSafetyResult with decision

        Raises:
            httpx.HTTPError: If API call fails
            httpx.TimeoutException: If API call times out
        """
        text_hash = hashlib.sha256(text.encode()).hexdigest()[:16]

        # Format prompt with user message
        prompt = LLAMA_GUARD_PROMPT.format(user_message=text[:2000])

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.OPENROUTER_ENDPOINT,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": self.REFERER,
                        "X-Title": self.APP_TITLE,
                    },
                    json={
                        "model": self.MODEL,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0,
                        "max_tokens": 20,
                    },
                )
                response.raise_for_status()
                data = response.json()

                # Extract response text
                response_text = data["choices"][0]["message"]["content"]

                # Log API call
                logger.debug(
                    "Llama Guard API call succeeded",
                    extra={
                        "text_hash": text_hash,
                        "language": language,
                        "status_code": response.status_code,
                        "response_text": response_text,
                    },
                )

                # Parse response
                is_safe, violated_categories = self._parse_llama_guard_response(response_text)

                # Map to result
                return self._map_categories_to_result(is_safe, violated_categories, text_hash)

        except httpx.TimeoutException:
            logger.warning(
                "Llama Guard API timeout",
                extra={"text_hash": text_hash, "timeout": self.timeout},
            )
            raise

        except httpx.HTTPError as e:
            status_code = (
                getattr(e.response, "status_code", None) if hasattr(e, "response") else None
            )
            log_fn = logger.warning if status_code == 404 else logger.error
            log_fn(
                "Llama Guard API error",
                extra={
                    "text_hash": text_hash,
                    "error": str(e),
                    "status_code": status_code,
                },
            )
            raise
