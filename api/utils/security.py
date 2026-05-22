"""
Security utilities for anti-abuse protection.

Provides:
- Content filtering (profanity, spam, URL detection)
- Multi-language violence & harm detection
- Rate limiting dependencies
- Security violation logging
"""

import hashlib
import re
import unicodedata
from enum import Enum
from typing import Annotated

from fastapi import Depends, HTTPException, Request

from config import settings

from .logging_config import get_logger
from .monitor_probe import is_monitor_probe
from .rate_limiter import get_rate_limiter

logger = get_logger(__name__)


class ViolationType(str, Enum):
    """Categories of security violations."""

    RATE_LIMIT_IP = "rate_limit_ip"
    RATE_LIMIT_SESSION = "rate_limit_session"
    RATE_LIMIT_LIFETIME = "rate_limit_lifetime"
    PROFANITY = "profanity"
    SPAM = "spam"
    URL_DETECTED = "url_detected"
    REPEATED_CHARS = "repeated_chars"
    MESSAGE_TOO_LONG = "message_too_long"
    VIOLENCE = "violence"
    SELF_HARM = "self_harm"
    HATE_SPEECH = "hate_speech"
    DIRECTED_HARM = "directed_harm"


def log_security_violation(
    violation_type: ViolationType,
    ip_address: str,
    session_id: str | None = None,
    message_preview: str | None = None,
    details: str | None = None,
) -> None:
    """Log a security violation for monitoring."""
    if not settings.security_log_violations:
        return

    # Truncate message preview to avoid logging full content
    preview = (
        message_preview[:50] + "..."
        if message_preview and len(message_preview) > 50
        else message_preview
    )

    logger.warning(
        "Security violation detected",
        extra={
            "violation_type": violation_type.value,
            "ip_address": ip_address,
            "session_id": session_id,
            "message_preview": preview,
            "details": details,
        },
    )


class ContentFilter:
    """
    Content filter for detecting abusive content.

    Detects:
    - Profanity (basic word list)
    - Spam patterns (excessive repetition)
    - URLs
    - Excessive repeated characters
    """

    # Basic profanity patterns (lowercase, can be expanded)
    PROFANITY_PATTERNS = [
        r"\bf+u+c+k+",
        r"\bs+h+i+t+",
        r"\ba+s+s+h+o+l+e+",
        r"\bb+i+t+c+h+",
        r"\bd+a+m+n+",
        r"\bc+u+n+t+",
        r"\bd+i+c+k+",
        r"\bp+i+s+s+",
    ]

    # URL patterns
    URL_PATTERN = re.compile(
        r"(?:https?://|www\.|ftp://)"  # Protocol or www
        r"|(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}",  # Domain pattern
        re.IGNORECASE,
    )

    def __init__(self):
        self._profanity_regex = re.compile(
            "|".join(self.PROFANITY_PATTERNS),
            re.IGNORECASE,
        )

    def check(self, message: str) -> tuple[bool, ViolationType | None, str | None]:
        """
        Check message content for violations.

        Args:
            message: The message to check

        Returns:
            Tuple of (allowed, violation_type, reason)
        """
        if not settings.content_filter_enabled:
            return True, None, None

        # Check profanity
        if settings.content_filter_block_profanity:
            if self._profanity_regex.search(message):
                return False, ViolationType.PROFANITY, "Message contains inappropriate language"

        # Check URLs
        if settings.content_filter_max_urls == 0:
            if self.URL_PATTERN.search(message):
                return False, ViolationType.URL_DETECTED, "URLs are not allowed in messages"

        # Check repeated characters
        if settings.content_filter_block_spam:
            max_repeat = settings.content_filter_max_repeated_chars
            repeat_pattern = re.compile(r"(.)\1{" + str(max_repeat) + r",}")
            if repeat_pattern.search(message):
                return (
                    False,
                    ViolationType.REPEATED_CHARS,
                    f"Message contains excessive repeated characters (more than {max_repeat})",
                )

        return True, None, None


# Global content filter instance
_content_filter: ContentFilter | None = None


def get_content_filter() -> ContentFilter:
    """Get or create the global content filter instance."""
    global _content_filter
    if _content_filter is None:
        _content_filter = ContentFilter()
    return _content_filter


def get_client_ip(request: Request) -> str:
    """Extract client IP from request, handling proxies."""
    # Check X-Forwarded-For header (set by proxies/load balancers)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Take the first IP (original client)
        return str(forwarded).split(",")[0].strip()

    # Check X-Real-IP header (nginx)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return str(real_ip).strip()

    # Fallback to direct client IP
    if request.client:
        return str(request.client.host)

    return "unknown"


async def require_rate_limit(request: Request) -> None:
    """
    FastAPI dependency to enforce rate limits.

    Raises HTTPException 429 if rate limit exceeded.
    """
    if not settings.rate_limit_enabled:
        return

    if is_monitor_probe(request):
        logger.info(
            "Monitor probe — bypassing rate limit",
            extra={"path": request.url.path},
        )
        return

    ip_address = get_client_ip(request)

    # Try to get session_id from request body (for POST requests)
    session_id = None
    if request.method == "POST":
        try:
            # Read body - FastAPI caches this
            body = await request.json()
            session_id = body.get("session_id")
        except Exception:
            pass  # Body parsing failed, proceed without session_id

    rate_limiter = get_rate_limiter()
    allowed, reason = await rate_limiter.check_rate_limit(ip_address, session_id)

    if not allowed:
        # Determine violation type from reason
        if "IP" in reason:
            violation_type = ViolationType.RATE_LIMIT_IP
        elif "lifetime" in reason.lower():
            violation_type = ViolationType.RATE_LIMIT_LIFETIME
        else:
            violation_type = ViolationType.RATE_LIMIT_SESSION

        log_security_violation(
            violation_type=violation_type,
            ip_address=ip_address,
            session_id=session_id,
            details=reason,
        )

        # Session lifetime limit - frontend handles the user-facing message (i18n)
        if violation_type == ViolationType.RATE_LIMIT_LIFETIME:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "session_lifetime_limit",
                    "retry_after": None,
                },
            )

        # Generic error for IP and per-minute session limits
        raise HTTPException(
            status_code=429,
            detail={"error": "Rate limit exceeded", "retry_after": 60},
        )


async def check_content_filter(request: Request) -> None:
    """
    FastAPI dependency to check content against filter.

    Raises HTTPException 400 if content is blocked.
    """
    if not settings.content_filter_enabled:
        return

    # Only check POST requests with body
    if request.method != "POST":
        return

    try:
        body = await request.json()
        message = body.get("message", "")
        session_id = body.get("session_id")
    except Exception:
        return  # Can't parse body, let validation handle it

    if not message:
        return  # Empty message will be caught by validation

    content_filter = get_content_filter()
    allowed, violation_type, reason = content_filter.check(message)

    if not allowed:
        ip_address = get_client_ip(request)

        log_security_violation(
            violation_type=violation_type,
            ip_address=ip_address,
            session_id=session_id,
            message_preview=message,
            details=reason,
        )

        # Best-effort capture for filter tuning (no PII, TTL-bounded).
        try:
            from feedback.blocked_samples import record_blocked_sample

            await record_blocked_sample(
                message=message,
                stage="keyword",
                categories=[violation_type.value],
                session_id=session_id,
            )
        except Exception:
            pass  # capture must never affect the user response

        raise HTTPException(
            status_code=400,
            detail={
                "error": "content_blocked",
                "code": "content_blocked",
                "message": reason,
            },
        )


# Type alias for dependency injection
RateLimitDep = Annotated[None, Depends(require_rate_limit)]
ContentFilterDep = Annotated[None, Depends(check_content_filter)]


def normalize_text(text: str) -> str:
    """
    Normalize text to catch evasion attempts.

    - NFKC normalization (compatibility characters)
    - Zero-width character removal
    - Leet-speak substitution (b0mb → bomb)
    """
    # NFKC normalization
    text = unicodedata.normalize("NFKC", text)

    # Remove zero-width characters
    zero_width_chars = [
        "\u200b",  # Zero-width space
        "\u200c",  # Zero-width non-joiner
        "\u200d",  # Zero-width joiner
        "\ufeff",  # Zero-width no-break space
    ]
    for char in zero_width_chars:
        text = text.replace(char, "")

    # Leet-speak substitution (common patterns)
    leet_map = {
        "0": "o",
        "1": "i",
        "3": "e",
        "4": "a",
        "5": "s",
        "7": "t",
        "@": "a",
        "$": "s",
        "*": "",  # Remove asterisks (f*ck → fck)
    }
    for leet, normal in leet_map.items():
        text = text.replace(leet, normal)

    return text.lower()


class MultiLanguageContentFilter:
    """
    Multi-language content filter for violence, self-harm, hate speech.

    Supports 7 languages: EN, IT, DE, ES, FR, PT, AR

    Critical distinction:
    - Help-seeking (low confidence) → allow, flag for compassionate response
    - Harmful intent (high confidence) → block immediately
    """

    # Violence patterns by language
    VIOLENCE_PATTERNS = {
        "en": [
            r"\bbomb\b",
            r"\bexplosive\b",
            r"\bweapon\b",
            r"\bgun\b",
            r"\bkill\b",
            r"\bmurder\b",
            r"\battack\b",
            r"\bterror",
            r"\bshoot\b",
            r"\bstab\b",
            r"\bslaughter\b",
        ],
        "it": [
            r"\bbomba\b",
            r"\besplosi",
            r"\barma\b",
            r"\barmi\b",
            r"\buccidere\b",
            r"\bomicidio\b",
            r"\battacco\b",
            r"\bterror",
            r"\bsparare\b",
            r"\baccoltellare\b",
        ],
        "de": [
            r"\bbombe\b",
            r"\bsprengstoff\b",
            r"\bwaffe\b",
            r"\bwaffen\b",
            r"\btöten\b",
            r"\bmord\b",
            r"\bangriff\b",
            r"\bterror",
            r"\bschießen\b",
            r"\bstechen\b",
        ],
        "es": [
            r"\bbomba\b",
            r"\bexplosivo\b",
            r"\barma\b",
            r"\barmas\b",
            r"\bmatar\b",
            r"\basesinato\b",
            r"\bataque\b",
            r"\bterror",
            r"\bdisparar\b",
            r"\bapuñalar\b",
        ],
        "fr": [
            r"\bbombe\b",
            r"\bexplosif\b",
            r"\barme\b",
            r"\barmes\b",
            r"\btuer\b",
            r"\bmeurtre\b",
            r"\battaque\b",
            r"\bterror",
            r"\btirer\b",
            r"\bpoignarder\b",
        ],
        "pt": [
            r"\bbomba\b",
            r"\bexplosivo\b",
            r"\barma\b",
            r"\barmas\b",
            r"\bmatar\b",
            r"\bassassinato\b",
            r"\bataque\b",
            r"\bterror",
            r"\batirar\b",
            r"\besfaquear\b",
        ],
        "ar": [
            r"قنبلة",
            r"متفجر",
            r"سلاح",
            r"أسلحة",
            r"قتل",
            r"جريمة قتل",
            r"هجوم",
            r"إرهاب",
        ],
    }

    # Self-harm patterns by language
    SELF_HARM_PATTERNS = {
        "en": [
            r"\bsuicide\b",
            r"\bkill myself\b",
            r"\bend my life\b",
            r"\bself.harm\b",
            r"\bcut myself\b",
            r"\bwant to die\b",
            r"\bwish i was dead\b",
            r"\bno reason to live\b",
        ],
        "it": [
            r"\bsuicidio\b",
            r"\buccidermi\b",
            r"\bfinire la mia vita\b",
            r"\bautolesionism",
            r"\btagliarmi\b",
            r"\bvoglio morire\b",
        ],
        "de": [
            r"\bselbstmord\b",
            r"\bsuizid\b",
            r"\bmich umbringen\b",
            r"\bselbstverletzung\b",
            r"\bich will sterben\b",
        ],
        "es": [
            r"\bsuicidio\b",
            r"\bmatarme\b",
            r"\bterminar con mi vida\b",
            r"\bautolesion",
            r"\bquiero morir\b",
        ],
        "fr": [
            r"\bsuicide\b",
            r"\bme tuer\b",
            r"\bmettre fin à ma vie\b",
            r"\bauto.mutilation\b",
            r"\bje veux mourir\b",
        ],
        "pt": [
            r"\bsuicídio\b",
            r"\bsuicidio\b",
            r"\bme matar\b",
            r"\bautomutilação\b",
            r"\bquero morrer\b",
        ],
        "ar": [
            r"انتحار",
            r"أقتل نفسي",
            r"إنهاء حياتي",
            r"إيذاء النفس",
            r"أريد أن أموت",
        ],
    }

    # Hate speech patterns (language-agnostic)
    HATE_SPEECH_PATTERNS = {
        "all": [
            r"\bn[i1]gg[e3]r\b",
            r"\bfagg[o0]t\b",
            r"\bk[i1]ke\b",
            r"\bsp[i1]c\b",
            r"\bch[i1]nk\b",
            r"\bgod hates\b",
            r"\bdeath to\b",
            r"\bkill all\b",
            r"\bexterminate\b",
        ],
    }

    # Directed harm patterns (indicates harmful intent, not help-seeking)
    DIRECTED_HARM_PATTERNS = {
        "en": [
            r"\bgo kill yourself\b",
            r"\bkill yourself\b",
            r"\bgo die\b",
            r"\byou should die\b",
            r"\bi will kill you\b",
            r"\bi want to kill you\b",
            r"\bgo fuck yourself\b",
        ],
        "it": [
            r"\bvattene a fanculo\b",
            r"\bti ammazzo\b",
            r"\bmuori\b",
        ],
        "de": [
            r"\bgeh sterben\b",
            r"\bich töte dich\b",
            r"\bverpiss dich\b",
        ],
        "es": [
            r"\bvete a la mierda\b",
            r"\bte mato\b",
            r"\bmuérete\b",
        ],
        "fr": [
            r"\bva te faire foutre\b",
            r"\bje vais te tuer\b",
            r"\bcrève\b",
        ],
        "pt": [
            r"\bvá se foder\b",
            r"\bvou te matar\b",
            r"\bmorra\b",
        ],
    }

    def __init__(self):
        """Initialize compiled regex patterns."""
        self._violence_regex = {}
        self._self_harm_regex = {}
        self._hate_speech_regex = None
        self._directed_harm_regex = {}

        # Compile violence patterns
        for lang, patterns in self.VIOLENCE_PATTERNS.items():
            self._violence_regex[lang] = re.compile("|".join(patterns), re.IGNORECASE | re.UNICODE)

        # Compile self-harm patterns
        for lang, patterns in self.SELF_HARM_PATTERNS.items():
            self._self_harm_regex[lang] = re.compile("|".join(patterns), re.IGNORECASE | re.UNICODE)

        # Compile hate speech patterns
        self._hate_speech_regex = re.compile(
            "|".join(self.HATE_SPEECH_PATTERNS["all"]), re.IGNORECASE | re.UNICODE
        )

        # Compile directed harm patterns
        for lang, patterns in self.DIRECTED_HARM_PATTERNS.items():
            self._directed_harm_regex[lang] = re.compile(
                "|".join(patterns), re.IGNORECASE | re.UNICODE
            )

    def check_multilingual(
        self, text: str, language: str = "en"
    ) -> tuple[bool, str, str | None, str | None]:
        """
        Check text for harmful content in the specified language.

        Stage 1 filter: Checks ONLY directed harm and hate speech patterns.
        Violence and self-harm patterns are now handled by OpenAI Moderation (Stage 2).

        Args:
            text: The message to check
            language: ISO 639-1 language code (en, it, de, es, fr, pt, ar)

        Returns:
            Tuple of (blocked, confidence, violation_type, pattern_matched)
            - blocked: True if content should be blocked
            - confidence: "high" (block immediately) or "low" (may be help-seeking)
            - violation_type: Type of violation detected (or None)
            - pattern_matched: The pattern that matched (for logging)
        """
        # Normalize text to catch evasion attempts
        normalized = normalize_text(text)

        # Check directed harm first (highest priority - always block)
        directed_patterns = self._directed_harm_regex.get(
            language
        ) or self._directed_harm_regex.get("en")
        if directed_patterns and directed_patterns.search(normalized):
            match = directed_patterns.search(normalized)
            pattern = match.group(0) if match else "directed_harm"
            text_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
            logger.warning(
                "Content safety: directed harm detected",
                extra={
                    "text_hash": text_hash,
                    "language": language,
                    "pattern": pattern,
                    "violation_type": "directed_harm",
                },
            )
            return True, "high", ViolationType.DIRECTED_HARM.value, pattern

        # Check hate speech (always block, high confidence)
        if self._hate_speech_regex.search(normalized):
            match = self._hate_speech_regex.search(normalized)
            pattern = match.group(0) if match else "hate_speech"
            text_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
            logger.warning(
                "Content safety: hate speech detected",
                extra={
                    "text_hash": text_hash,
                    "language": language,
                    "pattern": pattern,
                    "violation_type": "hate_speech",
                },
            )
            return True, "high", ViolationType.HATE_SPEECH.value, pattern

        # Violence and self-harm patterns are retained as class attributes
        # for fallback use, but are NOT checked in Stage 1.
        # OpenAI Moderation (Stage 2) handles these with context awareness.

        # No violations detected in Stage 1
        return False, "high", None, None
