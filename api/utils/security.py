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

from . import translation_registry as tr
from .client_ip import resolve_client_ip
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
    message_length: int | None = None,
    details: str | None = None,
) -> None:
    """Log a security violation for monitoring."""
    if not settings.security_log_violations:
        return

    logger.warning(
        "Security violation detected",
        extra={
            "violation_type": violation_type.value,
            "ip_address": ip_address,
            "session_id": session_id,
            "message_length": message_length,
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

    # Recognized TLDs for detecting *bare* domains (no scheme). Requiring a real
    # TLD prevents false positives on run-together text and abbreviations — most
    # importantly German Bible references such as "1.Timotheus" or "2.Mose", where
    # "<chapter>.<Book>" looks like "label.label". (Scheme/www URLs are matched by
    # the first alternative below and are unaffected.)
    _COMMON_TLDS = (
        "com|org|net|edu|gov|mil|int|io|co|info|biz|app|dev|ai|xyz|online|site|"
        "shop|store|me|tv|cc|"
        # ccTLDs for supported locales / common regions
        "de|it|es|fr|pt|uk|us|ca|eu|ru|cn|in|kr|jp|br|mx|ch|at|nl|be|pl|se|no|"
        "dk|fi|sa|ae|eg|au"
    )

    # URL patterns
    URL_PATTERN = re.compile(
        r"(?:https?://|www\.|ftp://)"  # Protocol or www — always treated as a URL
        r"|(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"  # one or more domain labels
        rf"(?:{_COMMON_TLDS})\b",  # …ending in a recognized TLD (bare-domain spam)
        re.IGNORECASE,
    )

    def __init__(self):
        self._profanity_regex = re.compile(
            "|".join(self.PROFANITY_PATTERNS),
            re.IGNORECASE,
        )

    def check(
        self,
        message: str,
        skip: frozenset[ViolationType] = frozenset(),
    ) -> tuple[bool, ViolationType | None, str | None]:
        """
        Check message content for violations.

        Args:
            message: The message to check
            skip: Violation types to ignore. ``check`` returns only the FIRST violation, so a
                caller that deliberately tolerates one type (the BITB-255 crisis bypass) uses
                this to still surface any later, non-tolerated violation (e.g. a URL).

        Returns:
            Tuple of (allowed, violation_type, reason)
        """
        if not settings.content_filter_enabled:
            return True, None, None

        # Check profanity
        if settings.content_filter_block_profanity and ViolationType.PROFANITY not in skip:
            if self._profanity_regex.search(message):
                return False, ViolationType.PROFANITY, "Message contains inappropriate language"

        # Check URLs
        if settings.content_filter_max_urls == 0 and ViolationType.URL_DETECTED not in skip:
            if self.URL_PATTERN.search(message):
                return False, ViolationType.URL_DETECTED, "URLs are not allowed in messages"

        # Check repeated characters
        if settings.content_filter_block_spam and ViolationType.REPEATED_CHARS not in skip:
            max_repeat = settings.content_filter_max_repeated_chars
            # Only flag stretched *word* characters (e.g. "Hellooooooo", "aaaaaa").
            # Punctuation/whitespace/emoji repetition — ellipses "......", "!!!",
            # "???", "----" — is natural in real messages and must not be treated as
            # spam. `\w` is Unicode-aware for str patterns, so accented letters (e.g.
            # Italian "perché") are still covered. (Fixes ellipsis false positive.)
            repeat_pattern = re.compile(r"(\w)\1{" + str(max_repeat) + r",}", re.UNICODE)
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
    """Client IP resolved through the trusted-proxy chain (see utils/client_ip.py)."""
    return resolve_client_ip(request)


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

        # Session lifetime limit - frontend handles the user-facing message (i18n).
        # "limit" is a number, not prose, so it doesn't need translation; it lets
        # clients render the exact cap without a second /config round-trip.
        if violation_type == ViolationType.RATE_LIMIT_LIFETIME:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "session_lifetime_limit",
                    "retry_after": None,
                    "limit": settings.rate_limit_session_max_requests,
                },
            )

        # Generic error for IP and per-minute session limits
        raise HTTPException(
            status_code=429,
            detail={"error": "Rate limit exceeded", "retry_after": 60},
        )


# Cosmetic violations that must never pre-empt the crisis path (BITB-255).
_CRISIS_BYPASS_VIOLATIONS = frozenset({ViolationType.PROFANITY, ViolationType.REPEATED_CHARS})

_crisis_keyword_filter: "MultiLanguageContentFilter | None" = None
_REPEAT_RUN = re.compile(r"(\w)\1{2,}", re.UNICODE)


def _has_crisis_wording(message: str) -> bool:
    """True when the text contains self-harm, violence or murder-suicide wording (any language).

    Deliberately broad: it only decides whether the *cosmetic* route filter steps aside; the
    real safety pipeline (ChatService._check_content_safety) still decides allow/block.
    """
    global _crisis_keyword_filter
    if _crisis_keyword_filter is None:
        _crisis_keyword_filter = MultiLanguageContentFilter()
    normalized = normalize_text(message)
    flt = _crisis_keyword_filter
    # A stretched word ("morireeeeee", "nooooo I want to die") is exactly what trips the
    # repeated-chars filter, so also try the text with every 3+ run collapsed to one/two.
    variants = (
        normalized,
        _REPEAT_RUN.sub(r"\1", normalized),
        _REPEAT_RUN.sub(r"\1\1", normalized),
    )
    return any(
        flt.find_all_self_harm_spans(text)
        or flt.find_violence_matches(text)
        or flt.find_hard_violence_matches(text)
        or flt.find_murder_suicide_matches(text)
        for text in dict.fromkeys(variants)
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

    if not allowed and violation_type in _CRISIS_BYPASS_VIOLATIONS and _has_crisis_wording(message):
        # BITB-255: "f*** this, I want to kill myself" / "nooooo I want to die" must reach
        # the safety pipeline so the crisis card is shown, not the generic blocked toast.
        # Only the cosmetic filters (profanity, repeated chars) yield. `check` reports just
        # the first violation, so re-run it ignoring those two: a URL / spam hidden behind
        # the profanity must still block. Never log message text.
        rest_allowed, rest_type, rest_reason = content_filter.check(
            message, skip=_CRISIS_BYPASS_VIOLATIONS
        )
        if rest_allowed:
            logger.info(
                "Content filter bypassed for crisis wording",
                extra={"violation_type": violation_type.value if violation_type else None},
            )
            return
        allowed, violation_type, reason = rest_allowed, rest_type, rest_reason

    if not allowed:
        ip_address = get_client_ip(request)

        log_security_violation(
            violation_type=violation_type,
            ip_address=ip_address,
            session_id=session_id,
            message_length=len(message),
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


# ---------------------------------------------------------------------------
# BITB-196: murder-suicide / elliptical third-party phrasing
# ---------------------------------------------------------------------------
# "I want to kill myself and my family" carries a self-harm span, and the remaining words
# ("my family", "everyone") are not violence keywords. These tables match ONLY the
# third-party part so the fallback can route the message to the ambiguous branch.
# A clause-end guard keeps "I want to die and my family doesn't understand" out.
_MS_PUNCT = "[.,;:!?)\\]}\"'…。、」』）،؛؟।\n]"


# BITB-193: single-word imperatives ("muori", "crève", "morra") are also ordinary words in other
# languages ("morra" = Italian game / Portuguese subjunctive). They only count as directed harm
# when they open a clause and close it, or are followed by an insult.
_DH_START = r"(?:^|[.!;:\n]\s*|[¡¿]\s*)"
_DH_END = r"(?=\s*(?:[!.,;]|$))"
# BITB-239: recall restored after the BITB-193 tightening. A comma-led clause ("Sei inutile, muori.")
# needs a stronger terminator (! . or end) so "Ok, muori?" / "Se muori, ..." stay clean.
_DH_END_STRONG = r"(?=\s*(?:[!.]|$))"
_DH_IT_LEAD = r"(?:(?:ok(?:ay)?|adesso|ora|dai|forza)[,!]?\s+)?"
_DH_IT_TAIL = r"(?:\s+(?:adesso|ora|subito|presto))?"
# "die to sin / in Christ" is theology, not a threat (it/pt).
_DH_IT_DIE_TO = (
    r"(?!\s+(?:in|con|al|alla|allo|a)\s+"
    r"(?:cristo|gesù|gesu|peccato|te\s+stess|se\s+stess|mondo|carne))"
)
_DH_PT_DIE_TO = (
    r"(?!\s+(?:para|em|com|ao|no|à)\s+(?:o\s+|a\s+)?"
    r"(?:pecado|cristo|jesus|mundo|carne|si\s+mesm|voc[êe]\s+mesm|ti\s+mesm))"
)

# BITB-238: English help-seeking / theological exemptions for the directed-harm table.
# The English patterns ("kill yourself", "go die", "you should die") run under every language
# code (BITB-193), so questions like "Is it a sin to kill yourself?" or "Why did Jesus have to go
# die on the cross?" were blocked as directed harm. The exemption is a STRICT WHOLE-MESSAGE
# ALLOWLIST: it applies only when the ENTIRE normalized message is a single sentence, carries no
# hostile / insulting / encouraging word anywhere, and fully matches one closed-form frame.
# Anything else (unusual phrasings included) takes the normal block path.
_DH_PREFIX = re.compile(r"^(?:pastor,\s*)?(?:quick\s+question:\s*)?")
_DH_MAX_LEN = 200
_DH_VETO = re.compile(
    r"\b(?:loser|idiot|moron|clown|trash|scum|retard\w*|pathetic|worthless|deserve\w*|"
    r"try\s+it|find\s+out|your\s+turn|so\s+should\s+you|go\s+on|go\s+ahead|do\s+it|"
    r"just\s*do|let\s+us\s+know|for\s+everyone|i\s+hope|i\s+wish|hope|wish|we\s+all|lol|"
    r"asking\s+for\s+you|act\s+on\s+it|bitch|stupid|freak|dumb|ugly|useless|fool|jerk|"
    r"coward|disgusting|waste|shit|ass|nobody|no\s*one)\b"
    r"|\byou\s+should(?!\s+die\s+(?:to|unto)\s|\s+die\s+daily|\s+die\s+every)"
)
# Same veto with every non-letter dropped, so "d o it" / "d.o.i.t" are caught too.
_DH_VETO_SQUASHED = re.compile(
    r"doit|tryit|findout|yourturn|soshouldyou|goahead|justdo|letusknow|foreveryone|ihope|"
    r"iwish|weall|askingforyou|lol|actonit"
)
_DH_ADJ = (
    r"(?:a\s+)?(?:sin|sinful|wrong|ok|okay|forgivable|selfish|allowed|normal|biblical|"
    r"unforgivable)"
)
_DH_FRAMES = re.compile(
    r"(?:"
    # (a) kill-yourself help-seeking: moral frame
    r"(?:is\s+it|is\s+that|was\s+it|would\s+it\s+be|can\s+it\s+be|could\s+it\s+be|"
    r"why\s+is\s+it)\s+" + _DH_ADJ + r"\s+to\s+kill\s+yourself\??"
    # (a) religious-outcome conditionals
    r"|what\s+happens\s+(?:if|when)\s+you\s+kill\s+yourself\??"
    r"|do\s+you\s+go\s+to\s+(?:hell|heaven)\s+(?:if|when)\s+you\s+kill\s+yourself\??"
    r"|will\s+god\s+forgive\s+you\s+(?:if|when)\s+you\s+kill\s+yourself\??"
    r"|(?:if|when)\s+you\s+kill\s+yourself,\s*do\s+you\s+go\s+to\s+(?:heaven|hell)\??"
    # (a) want / urge frame, closed form only
    r"|(?:how\s+do\s+i\s+stop|how\s+to\s+stop)\s+wanting\s+to\s+kill\s+yourself\??"
    r"|is\s+it\s+(?:wrong|a\s+sin|normal|ok)\s+to\s+want\s+to\s+kill\s+yourself\??"
    # (b) 'go die' theological
    r"|(?:why\s+did|did)\s+(?:jesus|christ)\s+(?:have\s+to\s+)?go\s+die"
    r"(?:\s+(?:on\s+the\s+cross|for\s+(?:our|my)\s+sins|for\s+(?:sinners|mankind|humanity)))?\?"
    # (c) 'you should die' theological
    r"|does\s+(?:paul|the\s+bible|jesus|scripture|the\s+apostle)\s+say\s+you\s+should\s+die"
    r"\s+(?:to\s+sin|to\s+self|to\s+the\s+flesh|to\s+the\s+world|daily|every\s+day)"
    r"(?:\s+(?:daily|every\s+day))?\??"
    r")"
)
_DH_WRAP_OPEN = "([\u201c\"'\u00ab"
_DH_WRAP_CLOSE = ")]\u201d\"'\u00bb"


def _dh_whole_message_exempt(normalized: str) -> bool:
    """True only when the ENTIRE message is a closed-form help-seeking / theological frame."""
    msg = re.sub(r"\s+", " ", normalized).strip()
    if not msg or len(msg) > _DH_MAX_LEN:
        return False
    if _DH_VETO.search(msg) or _DH_VETO_SQUASHED.search(re.sub(r"[^a-z]+", "", msg)):
        return False
    body = msg.lstrip(_DH_WRAP_OPEN).rstrip(_DH_WRAP_CLOSE).strip()
    body = _DH_PREFIX.sub("", body, count=1)
    # Single sentence: no sentence punctuation except one terminal '?' / '.'.
    core = body[:-1] if body[-1:] in ("?", ".") else body
    if any(c in core for c in ".!?;:\n"):
        return False
    return _DH_FRAMES.fullmatch(body.rstrip(".")) is not None


def _ms_end(extra: str = "") -> str:
    """Clause-end guard: optional filler words, then punctuation or end of text."""
    words = "too|also|as well|first" if not extra else extra
    return r"(?:\s+(?:" + words + r"))*\s*(?:" + _MS_PUNCT + r"|$)"


_MS_EN_N = (
    r"(?:(?:my|our)\s+(?:whole\s+|entire\s+)?(?:family|wife|husband|kids|children|son|sons|"
    r"daughter|daughters|parents|mom|mother|dad|father|coworkers|co-workers|classmates|"
    r"friends|girlfriend|boyfriend|baby|babies)|everyone(?:\s+else)?|everybody|them\s+all|"
    r"all\s+of\s+(?:them|you|us)|the\s+whole\s+family|anyone\s+else)"
)
_MS_IT_N = (
    r"(?:la\s+mia\s+(?:intera\s+)?famiglia|mia\s+moglie|mio\s+marito|(?:i\s+miei|le\s+mie)\s+"
    r"(?:figli|figlie|genitori|colleghi|compagni|amici|amiche)|mio\s+figlio|mia\s+figlia|"
    r"tutti|tutta\s+la\s+famiglia|chiunque)"
)
_MS_DE_N = (
    r"(?:meine[rn]?\s+(?:ganze\s+)?(?:familie|frau|kinder|eltern|kollegen|mitschüler|"
    r"freunde|tochter|töchter|söhne)|mein(?:en)?\s+(?:mann|sohn)|alle(?:\s+anderen)?|jeden)"
)
_MS_ES_N = (
    r"(?:a\s+)?(?:mi\s+(?:familia|esposa|esposo|marido|mujer|hij[oa]|compañeros|amigos|"
    r"colegas)|mis\s+(?:hijos|hijas|padres|compañeros|amigos|colegas)|toda\s+mi\s+familia|"
    r"todos|todo\s+el\s+mundo)"
)
_MS_FR_N = (
    r"(?:(?:aussi\s+)?(?:ma\s+(?:famille|femme|fille|mère)|mon\s+(?:mari|fils|père)|"
    r"mes\s+(?:enfants|parents|collègues|camarades|amis|fils|filles)|toute\s+ma\s+famille|"
    r"tout\s+le\s+monde|tous))"
)
_MS_PT_N = (
    r"(?:minha\s+(?:família|familia|esposa|mulher|filha)|meu\s+(?:marido|filho)|"
    r"meus\s+(?:filhos|pais|colegas|amigos)|minhas\s+filhas|toda\s+a\s+minha\s+(?:família|familia)|"
    r"todos|todo\s+mundo)"
)
_MS_AR_N = (
    r"(?:كل\s+)?(?:عائلتي|عايلتي|أسرتي|اسرتي|زوجتي|زوجي|أولادي|اولادي|أطفالي|اطفالي|ابني|"
    r"ابنتي|بناتي|والدي|والديّ|أهلي|اهلي|زملائي|أصدقائي|الجميع|الناس|الكل|من\s+حولي)"
)
_MS_RU_N = (
    r"(?:(?:свою\s+|мою\s+|всю\s+)?(?:семью|жену|мужа|детей|родителей|сына|дочь|коллег|"
    r"одноклассников|друзей)|всех(?:\s+вокруг)?)"
)
_MS_ZH_N = r"(?:全家人?|一家人|家人|孩子们?|老婆|妻子|丈夫|所有人|大家)"
_MS_KO_N = (
    r"(?:온\s*가족|가족|아내|남편|아이들|애들|자식들?|부모님?|동료들?|친구들|모두|사람들|다들)"
)
_MS_HI_N = r"(?:परिवार|पत्नी|पति|बच्चों|बच्चे|बेटे|बेटी|माता-पिता|माँ-बाप|सबको|सभी|सब)"

_MURDER_SUICIDE_PATTERNS: dict[str, list[str]] = {
    "en": [
        r"(?<!\bme )(?<!\bme, )\b(?:and|plus)\s+"
        + _MS_EN_N
        + _ms_end(r"too|also|as well|first|and\s+(?:my\s+)?\w+(?:\s+too)?"),
        r"\b(?:take|bring|drag|carry)\s+" + _MS_EN_N + r"\s+(?:down\s+)?with\s+me\b",
        r"\bmurder[\s-]*suicide\b",
        r"\bfamilicide\b",
    ],
    "it": [
        r"(?<!\bme )\b(?:e|ed|con|più)\s+" + _MS_IT_N + _ms_end("anche|pure|insieme|prima"),
        r"\b(?:port\w+|trasc\w+)\s+(?:via\s+)?" + _MS_IT_N + r"\s+con\s+me\b",
        r"\bomicidio[\s-]+suicidio\b",
    ],
    "de": [
        r"(?<!für mich )(?<!für mir )(?<!\bmir )\b(?:und|sowie)\s+"
        + _MS_DE_N
        + _ms_end("auch|mit|gleich|zuerst|umbringen|töten|mitnehmen|mit\\s+in\\s+den\\s+tod"),
        r"\balle(?:\s+anderen)?\s+mit\s+in\s+den\s+tod\b",
        r"\b(?:mit\s+in\s+den\s+tod\s+nehmen|erweiterter\s+suizid)\b",
    ],
    "es": [
        r"(?<!\bmí )(?<!\bmi )\b(?:y|e|con)\s+"
        + _MS_ES_N
        + _ms_end("también|tambien|igual|primero"),
        r"\b(?:llev\w+|arrastr\w+)\s+(?:a\s+)?" + _MS_ES_N + r"\s+conmigo\b",
        r"\b(?:homicidio|asesinato)[\s-]+suicidio\b",
    ],
    "fr": [
        r"(?<!\bmoi )\b(?:et|avec|ainsi\s+que)\s+" + _MS_FR_N + _ms_end("aussi|également|d'abord"),
        r"\b(?:emmen\w+|entra[îi]n\w+|emport\w+|prendre)\s+" + _MS_FR_N + r"\s+avec\s+moi\b",
        r"\bmeurtre[\s-]+suicide\b",
    ],
    "pt": [
        r"(?<!\bmim )\b(?:e|com)\s+" + _MS_PT_N + _ms_end("também|tambem|junto|primeiro"),
        r"\b(?:lev\w+|arrast\w+)\s+" + _MS_PT_N + r"\s+comigo\b",
        r"\bhomic[ií]dio[\s-]+suic[ií]dio\b",
    ],
    "ar": [
        r"(?<![؀-ۿ])و" + _MS_AR_N + _ms_end("أيضا|أيضاً|معي|كذلك|معا|أولا"),
        r"(?:آخذ|اخذ|أخذ|أصطحب|اصطحب|أسحب)\s+" + _MS_AR_N + r"\s+معي",
        r"قتل\s+ثم\s+انتحار",
    ],
    "ru": [
        r"(?<!\bменя )\bи\s+" + _MS_RU_N + _ms_end("тоже|также|с собой|заодно|вместе с собой"),
        r"\b(?:забра\w+|взя\w+|утащ\w+|увест\w+)\s+" + _MS_RU_N + r"\s+с\s+собой\b",
        r"\bубийств\w*[\s-]+(?:и\s+)?самоубийств",
    ],
    "zh": [
        r"[带帶]着?" + _MS_ZH_N + r"(?:一起|一同)(?:去)?(?:死|走|上路)",
        r"和?" + _MS_ZH_N + r"一起(?:去)?(?:死|自[杀殺]|上路)",
        r"(?:拉着|拖着|带上|帶上)" + _MS_ZH_N + r"(?:一起|陪葬|垫背|墊背)",
        r"(?:想|要|打算|准备|準備)[^，。,.？?\n]{0,6}同归于尽",
        r"(?:想|要|打算|准备|準備)[^，。,.？?\n]{0,6}同歸於盡",
        r"[杀殺]了?" + _MS_ZH_N,
        r"一家人?(?:一起)?(?:去死|自[杀殺]|上路)",
    ],
    "hi": [
        r"(?<!आत्म)हत्या[-\s]*आत्महत्या",
        r"आत्महत्या\s+और\s+हत्या",
        _MS_HI_N + r"(?:\s+को)?\s+(?:भी\s+)?(?:मार|साथ\s+(?:में\s+)?ले|ख़?त्म)",
        _MS_HI_N + r"\s+को\s+भी" + _ms_end("साथ|ले जाना"),
    ],
    "ko": [
        _MS_KO_N + r"(?:을|를|도|과|와|이랑|랑|까지)?\s*(?:모두\s*)?(?:죽이|죽일|죽여|죽였)",
        _MS_KO_N
        + r"(?:을|를|도|과|와|이랑|랑)?\s*(?:같이|함께|데리고|끌고)\s*(?:\S{0,4}\s*)?(?:죽|가|떠나|갈|데려|끌)",
        r"동반\s*자살|일가족\s*(?:동반|자살|살해)|가족\s*동반",
    ],
}

# Hindi lookbehinds (BITB-198): skip reflexive "kill myself" spans (owned by the self-harm
# table) and avoid matching inside longer Devanagari words such as आत्महत्या.
_HI_NOT_SELF = r"(?<!खुद को )(?<!ख़ुद को )(?<!अपने आप को )(?<!स्वयं को )"
_HI_NB = r"(?<![\u0900-\u097f\-])"


def _registry_book_names(lang: str) -> set[str]:
    """Book names (+ aliases / citation forms) of ``lang``, derived from translation_registry."""
    if lang == "en":
        return set(tr.ENGLISH_TO_ITALIAN) | set(tr.ENGLISH_ALIASES)
    mapping = {
        "it": (tr.ENGLISH_TO_ITALIAN, tr.ITALIAN_ALIASES),
        "es": (tr.ENGLISH_TO_SPANISH, tr.ITALIAN_ALIASES),  # "Salmo" alias is shared
        "pt": (tr.ENGLISH_TO_PORTUGUESE, tr.ITALIAN_ALIASES),
        "fr": (tr.ENGLISH_TO_FRENCH, tr.FRENCH_ALIASES),
        "de": (tr.ENGLISH_TO_GERMAN, tr.GERMAN_ALIASES),
        "ar": (tr.ENGLISH_TO_ARABIC, tr.ARABIC_CITATION_FORMS),
    }[lang]
    names: set[str] = set()
    for table in mapping:
        names |= set(table.values()) if table is mapping[0] else set(table)
    return names


# ---------------------------------------------------------------------------
# BITB-257 round 5: curated Bible killing EVENTS (killer -> victim)
# ---------------------------------------------------------------------------
# Owner decision 2026-11-08. A violence-table match is exempt ONLY when the ENTIRE normalized
# message (<= 200 chars, one sentence, optional "In <book>," prefix) fully matches one closed
# frame AND its (killer, victim) pair is a curated Bible killing event below. Rounds 1-4 tried
# name lists (distinctive / common / group names) and a per-match denylist; verification broke
# each one, because every list leaked a modern given name or an everyday word ("Why did Abel
# kill the children?"). A name therefore never qualifies on its own: only the PAIR does, so
# "Why did Cain kill Abel?" passes while "Why did Abel kill Cain?" or "Why did Cain kill the
# children?" block like on main. Anything outside a frame or an event blocks (fail safe).
# The design mirrors the BITB-238 directed-harm allowlist (`_dh_whole_message_exempt`,
# PR #1249); the two helpers can be unified once both merge. Book names are DERIVED from
# translation_registry (never hardcoded). God is only ever a killer inside its own event.
#
# Each name key lists its surface forms per language (en, it, de, es, fr, pt, ar), "|"-separated,
# lower case, with the article where the language needs one. Forms are matched after Latin
# accents and Arabic harakat are stripped; Arabic forms are written without the leading ال and
# the message may carry a leading و/ف/ب/ل/ال, which is stripped before the pair check.
_BIBLE_NAMES: dict[str, dict[str, str]] = {
    "cain": {
        "en": "cain", "it": "caino", "de": "kain", "es": "caín", "fr": "caïn", "pt": "caim",
        "ar": "قايين|قابيل",
    },
    "abel": {
        "en": "abel", "it": "abele", "de": "abel", "es": "abel", "fr": "abel", "pt": "abel",
        "ar": "هابيل",
    },
    "brother": {
        "en": "his brother", "it": "suo fratello|il fratello", "de": "seinen bruder",
        "es": "su hermano", "fr": "son frère|son frere", "pt": "seu irmão|o irmão",
        "ar": "أخاه|اخاه|أخيه|اخيه",
    },
    "david": {
        "en": "david", "it": "davide", "de": "david", "es": "david", "fr": "david", "pt": "davi",
        "ar": "داود|داوود",
    },
    "goliath": {
        "en": "goliath", "it": "golia", "de": "goliat|goliath", "es": "goliat", "fr": "goliath",
        "pt": "golias", "ar": "جليات|جالوت",
    },
    "saul": {
        "en": "saul", "it": "saul", "de": "saul", "es": "saúl", "fr": "saül", "pt": "saul",
        "ar": "شاول",
    },
    "moses": {
        "en": "moses", "it": "mosè", "de": "mose|moses", "es": "moisés", "fr": "moïse",
        "pt": "moisés", "ar": "موسى",
    },
    "egyptian": {
        "en": "the egyptian", "it": "l'egiziano|un egiziano", "de": "den ägypter|einen ägypter",
        "es": "al egipcio|un egipcio|el egipcio", "fr": "l'égyptien|un égyptien",
        "pt": "o egípcio|um egípcio", "ar": "المصري|مصريا",
    },
    "pharaoh": {
        "en": "pharaoh", "it": "faraone|il faraone", "de": "pharao|der pharao",
        "es": "faraón|el faraón", "fr": "pharaon|le pharaon", "pt": "faraó|o faraó",
        "ar": "فرعون",
    },
    "firstborn": {
        "en": "the firstborn|the firstborn of egypt|the firstborn of the egyptians",
        "it": "i primogeniti|i primogeniti d'egitto|i primogeniti degli egiziani",
        "de": "die erstgeborenen|die erstgeborenen ägyptens|die erstgeborenen der ägypter",
        "es": "los primogénitos|los primogénitos de egipto",
        "fr": "les premiers-nés|les premiers-nés d'égypte",
        "pt": "os primogênitos|os primogênitos do egito|os primogénitos",
        "ar": "أبكار مصر|الأبكار|أبكار المصريين|بكر مصر",
    },
    "hebrew_babies": {
        "en": "the hebrew babies|the hebrew boys|the hebrew children|the israelite babies",
        "it": "i neonati ebrei|i bambini ebrei|i maschi ebrei",
        "de": "die hebräischen babys|die hebräischen jungen|die hebräischen kinder",
        "es": "los bebés hebreos|los niños hebreos|los varones hebreos",
        "fr": "les bébés hébreux|les garçons hébreux|les enfants hébreux",
        "pt": "os bebês hebreus|os meninos hebreus|as crianças hebreias",
        "ar": "الأطفال العبرانيين|أطفال العبرانيين|الأطفال الإسرائيليين|أطفال بني إسرائيل",
    },
    "herod": {
        "en": "herod", "it": "erode", "de": "herodes", "es": "herodes", "fr": "hérode",
        "pt": "herodes", "ar": "هيرودس",
    },
    "bethlehem_children": {
        "en": "the babies|the children|the infants|the innocents|the babies of bethlehem"
        "|the children of bethlehem|the infants of bethlehem",
        "it": "i bambini|i neonati|gli innocenti|i bambini di betlemme",
        "de": "die kinder|die babys|die unschuldigen|die kinder von bethlehem",
        "es": "los niños|los bebés|los inocentes|los niños de belén",
        "fr": "les enfants|les bébés|les innocents|les enfants de bethléem|les nourrissons",
        "pt": "as crianças|os bebês|os inocentes|as crianças de belém",
        "ar": "الأطفال|أطفال بيت لحم|الأبرياء|الصبيان",
    },
    "john_baptist": {
        "en": "john the baptist", "it": "giovanni battista",
        "de": "johannes den täufer|johannes der täufer", "es": "juan el bautista",
        "fr": "jean-baptiste|jean le baptiste", "pt": "joão batista",
        "ar": "يوحنا المعمدان|يحيى",
    },
    "herodias": {
        "en": "herodias", "it": "erodiade", "de": "herodias", "es": "herodías",
        "fr": "hérodiade", "pt": "herodias", "ar": "هيروديا",
    },
    "jesus": {
        "en": "jesus", "it": "gesù", "de": "jesus", "es": "jesús", "fr": "jésus", "pt": "jesus",
        "ar": "يسوع|المسيح",
    },
    "james": {
        "en": "james", "it": "giacomo", "de": "jakobus", "es": "santiago", "fr": "jacques",
        "pt": "tiago", "ar": "يعقوب",
    },
    "jael": {
        "en": "jael", "it": "giaele", "de": "jael", "es": "jael", "fr": "jaël", "pt": "jael",
        "ar": "ياعيل|يايل",
    },
    "sisera": {
        "en": "sisera", "it": "sisera", "de": "sisera", "es": "sísara", "fr": "sisera",
        "pt": "sísera", "ar": "سيسرا",
    },
    "ehud": {
        "en": "ehud", "it": "eud", "de": "ehud", "es": "aod", "fr": "éhoud", "pt": "eúde",
        "ar": "إهود|ايهود",
    },
    "eglon": {
        "en": "eglon", "it": "eglon", "de": "eglon", "es": "eglón", "fr": "églon",
        "pt": "eglom", "ar": "عجلون",
    },
    "samson": {
        "en": "samson", "it": "sansone", "de": "simson", "es": "sansón", "fr": "samson",
        "pt": "sansão", "ar": "شمشون",
    },
    "philistines": {
        "en": "the philistines", "it": "i filistei", "de": "die philister",
        "es": "los filisteos", "fr": "les philistins", "pt": "os filisteus",
        "ar": "الفلسطينيين|الفلسطينيون",
    },
    "absalom": {
        "en": "absalom", "it": "assalonne", "de": "absalom", "es": "absalón", "fr": "absalom",
        "pt": "absalão", "ar": "أبشالوم|ابشالوم",
    },
    "amnon": {
        "en": "amnon", "it": "amnon", "de": "amnon", "es": "amnón", "fr": "amnon",
        "pt": "amnom", "ar": "أمنون",
    },
    "joab": {
        "en": "joab", "it": "ioab", "de": "joab", "es": "joab", "fr": "joab", "pt": "joabe",
        "ar": "يوآب",
    },
    "abner": {
        "en": "abner", "it": "abner", "de": "abner", "es": "abner", "fr": "abner",
        "pt": "abner", "ar": "أبنير",
    },
    "uriah": {
        "en": "uriah", "it": "uria", "de": "urija", "es": "urías", "fr": "urie", "pt": "urias",
        "ar": "أوريا|اوريا",
    },
    "jezebel": {
        "en": "jezebel", "it": "gezabele", "de": "isebel", "es": "jezabel", "fr": "jézabel",
        "pt": "jezabel", "ar": "إيزابل|ايزابل",
    },
    "naboth": {
        "en": "naboth", "it": "nabot", "de": "nabot", "es": "nabot", "fr": "naboth",
        "pt": "nabote", "ar": "نابوت",
    },
    "elijah": {
        "en": "elijah", "it": "elia", "de": "elia", "es": "elías", "fr": "élie", "pt": "elias",
        "ar": "إيليا|الياس",
    },
    "jehu": {
        "en": "jehu", "it": "ieu", "de": "jehu", "es": "jehú", "fr": "jéhu", "pt": "jeú",
        "ar": "ياهو",
    },
    "ahab_house": {
        "en": "the house of ahab|the sons of ahab",
        "it": "la casa di acab|i figli di acab",
        "de": "das haus ahabs|die söhne ahabs",
        "es": "la casa de acab|los hijos de acab",
        "fr": "la maison d'achab|les fils d'achab",
        "pt": "a casa de acabe|os filhos de acabe",
        "ar": "بيت أخآب|بيت اخاب|أبناء أخآب|أبناء اخاب",
    },
    "baal_prophets": {
        "en": "the prophets of baal", "it": "i profeti di baal", "de": "die propheten baals",
        "es": "los profetas de baal", "fr": "les prophètes de baal",
        "pt": "os profetas de baal", "ar": "أنبياء البعل|انبياء البعل",
    },
    "phinehas": {
        "en": "phinehas", "it": "fineas", "de": "pinhas", "es": "finees", "fr": "phinées",
        "pt": "finéias", "ar": "فينحاس",
    },
    "zimri": {
        "en": "zimri", "it": "zimri", "de": "simri", "es": "zimri", "fr": "zimri",
        "pt": "zinri", "ar": "زمري",
    },
    "haman": {
        "en": "haman", "it": "aman", "de": "haman", "es": "amán", "fr": "haman", "pt": "hamã",
        "ar": "هامان",
    },
    "jews": {
        "en": "the jews", "it": "i giudei", "de": "die juden", "es": "los judíos",
        "fr": "les juifs", "pt": "os judeus", "ar": "اليهود",
    },
    "abimelech": {
        "en": "abimelech", "it": "abimelech", "de": "abimelech", "es": "abimelec",
        "fr": "abimélec", "pt": "abimeleque", "ar": "أبيمالك",
    },
    "gideon_sons": {
        "en": "his brothers|the sons of gideon", "it": "i suoi fratelli|i figli di gedeone",
        "de": "seine brüder|die söhne gideons", "es": "sus hermanos|los hijos de gedeón",
        "fr": "ses frères|les fils de gédéon", "pt": "seus irmãos|os filhos de gideão",
        "ar": "إخوته|اخوته|أبناء جدعون",
    },
    "god": {
        "en": "god", "it": "dio", "de": "gott", "es": "dios", "fr": "dieu", "pt": "deus",
        "ar": "الله|الرب",
    },
    "nob_priests": {
        "en": "the priests of nob", "it": "i sacerdoti di nob", "de": "die priester von nob",
        "es": "los sacerdotes de nob", "fr": "les prêtres de nob",
        "pt": "os sacerdotes de nobe", "ar": "كهنة نوب",
    },
    "doeg": {
        "en": "doeg", "it": "doeg", "de": "doeg", "es": "doeg", "fr": "doëg", "pt": "doegue",
        "ar": "دوآج",
    },
    "pharisees": {
        "en": "the pharisees", "it": "i farisei", "de": "die pharisäer", "es": "los fariseos",
        "fr": "les pharisiens", "pt": "os fariseus", "ar": "الفريسيون|الفريسيين",
    },
    "chief_priests": {
        "en": "the chief priests", "it": "i capi dei sacerdoti",
        "de": "die hohenpriester", "es": "los sumos sacerdotes|los principales sacerdotes",
        "fr": "les grands prêtres", "pt": "os sumos sacerdotes|os principais sacerdotes",
        "ar": "رؤساء الكهنة",
    },
    "crowd": {
        "en": "the crowd|the mob", "it": "la folla", "de": "die menge", "es": "la multitud",
        "fr": "la foule", "pt": "a multidão", "ar": "الجموع|الجمهور",
    },
    "stephen": {
        "en": "stephen", "it": "stefano", "de": "stephanus", "es": "esteban", "fr": "étienne",
        "pt": "estêvão", "ar": "إسطفانوس|اسطفانوس|استفانوس",
    },
    "esau": {
        "en": "esau", "it": "esaù", "de": "esau", "es": "esaú", "fr": "ésaü", "pt": "esaú",
        "ar": "عيسو",
    },
    "jacob": {
        "en": "jacob", "it": "giacobbe", "de": "jakob", "es": "jacob", "fr": "jacob",
        "pt": "jacó", "ar": "يعقوب",
    },
    "joseph": {
        "en": "joseph", "it": "giuseppe", "de": "josef", "es": "josé", "fr": "joseph",
        "pt": "josé", "ar": "يوسف",
    },
    "joseph_brothers": {
        "en": "joseph's brothers", "it": "i fratelli di giuseppe",
        "de": "die brüder josefs", "es": "los hermanos de josé", "fr": "les frères de joseph",
        "pt": "os irmãos de josé", "ar": "إخوة يوسف|اخوة يوسف",
    },
    "athaliah": {
        "en": "athaliah", "it": "atalia", "de": "atalja", "es": "atalía", "fr": "athalie",
        "pt": "atalia", "ar": "عثليا",
    },
    "royal_family": {
        "en": "the royal family|her grandchildren", "it": "la famiglia reale|i suoi nipoti",
        "de": "die königliche familie|ihre enkel", "es": "la familia real|sus nietos",
        "fr": "la famille royale|ses petits-enfants",
        "pt": "a família real|os seus netos|seus netos", "ar": "النسل الملكي|أحفادها",
    },
    "samuel": {
        "en": "samuel", "it": "samuele", "de": "samuel", "es": "samuel", "fr": "samuel",
        "pt": "samuel", "ar": "صموئيل",
    },
    "agag": {
        "en": "agag", "it": "agag", "de": "agag", "es": "agag", "fr": "agag", "pt": "agague",
        "ar": "أجاج",
    },
}  # fmt: skip

# (killer, victim, completed): completed=False means the Bible records only an ATTEMPT / plot,
# so the pair is accepted in "wanted / tried to kill" frames but not in "did X kill Y".
_BIBLE_KILLING_EVENTS: tuple[tuple[str, str, bool], ...] = (
    ("cain", "abel", True),
    ("cain", "brother", True),
    ("david", "goliath", True),
    ("saul", "david", False),
    ("moses", "egyptian", True),
    ("pharaoh", "firstborn", False),
    ("pharaoh", "hebrew_babies", True),
    ("god", "firstborn", True),
    ("herod", "bethlehem_children", True),
    ("herod", "john_baptist", True),
    ("herod", "jesus", False),
    ("herod", "james", True),
    ("herodias", "john_baptist", False),
    ("jael", "sisera", True),
    ("ehud", "eglon", True),
    ("samson", "philistines", True),
    ("absalom", "amnon", True),
    ("joab", "abner", True),
    ("joab", "absalom", True),
    ("david", "uriah", True),
    ("jezebel", "naboth", True),
    ("jezebel", "elijah", False),
    ("jehu", "jezebel", True),
    ("jehu", "ahab_house", True),
    ("elijah", "baal_prophets", True),
    ("phinehas", "zimri", True),
    ("haman", "jews", False),
    ("abimelech", "gideon_sons", True),
    ("saul", "nob_priests", True),
    ("doeg", "nob_priests", True),
    ("pharisees", "jesus", False),
    ("chief_priests", "jesus", False),
    ("crowd", "stephen", True),
    ("esau", "jacob", False),
    ("esau", "brother", False),
    ("joseph_brothers", "joseph", False),
    ("athaliah", "royal_family", True),
    ("samuel", "agag", True),
)

_VN_MAX_LEN = 200
_VN_LANGS = ("en", "it", "de", "es", "fr", "pt", "ar")
_VN_AR_MARKS = re.compile("[ً-ٰٟـ]")  # harakat + superscript alef + tatweel
_VN_WRAP_OPEN = "([«“‘„\"'¿¡"
_VN_WRAP_CLOSE = ")]»”’\"'"
# Letters of one word from two scripts (Latin + Cyrillic/Greek) = homoglyph evasion.
_VN_MIXED_SCRIPT = re.compile(
    r"(?=\w*[a-zà-ɏ])\w*[Ͱ-ϿЀ-ԯ]" r"|(?=\w*[Ͱ-ϿЀ-ԯ])\w*[a-zà-ɏ]",
    re.IGNORECASE,
)
# First-person words of ALL supported languages (union). The closed frames already have no
# pronoun slot, so this only guards frame vocabulary growth. Bare "i" is skipped on purpose:
# it is a numbered-book prefix ("i samuel") and the Italian article ("i bambini").
_VN_VETO = re.compile(
    r"\b(?:i['’](?:m|ll|d|ve)|me|my|mine|myself|we|us|our|ours"
    r"|je|nous|moi|mon|mes|notre|nos|ich|wir|mich|mir|uns|io|noi|mio|mia|miei|mie|mi"
    r"|voglio|vorrei|vogliamo|yo|nosotros|nosotras|mis|quiero|queremos|eu|meu|meus"
    r"|minha|minhas|quero)\b|\b[jm]['’]|\b(?:mein|unser)\w*"
    r"|(?<![ؠ-ي])(?:أنا|انا|نحن"
    r"|أريد|اريد|سأقتل"
    r"|سوف)(?![ؠ-ي])",
    re.IGNORECASE,
)


def _vn_plain(text: str) -> str:
    """Strip Arabic harakat/tatweel and Latin accents; keep every non-Latin base letter intact."""
    text = _VN_AR_MARKS.sub("", unicodedata.normalize("NFC", text))
    out: list[str] = []
    for ch in unicodedata.normalize("NFD", text):
        if unicodedata.combining(ch) and out and out[-1].isascii():
            continue  # accent on a Latin base letter
        out.append(ch)
    return unicodedata.normalize("NFC", "".join(out)).replace("’", "'")


def _vn_forms(key: str, lang: str) -> set[str]:
    """Plain (accent-free) surface forms of name ``key`` in ``lang``."""
    forms = {_vn_plain(normalize_text(f)) for f in _BIBLE_NAMES[key][lang].split("|")}
    # Arabic forms are stored without the article; a message article is stripped before the check.
    return {f.removeprefix("ال") for f in forms} if lang == "ar" else forms


def _vn_alt(terms: set[str]) -> str:
    return "|".join(re.escape(t) for t in sorted(terms, key=len, reverse=True))


def _vn_pairs(lang: str, *, completed_only: bool) -> set[tuple[str, str]]:
    """All (killer form, victim form) pairs of the curated events of ``lang``."""
    return {
        (k, v)
        for killer, victim, done in _BIBLE_KILLING_EVENTS
        if done or not completed_only
        for k in _vn_forms(killer, lang)
        for v in _vn_forms(victim, lang)
    }


# Chapter[:verse] after a book. normalize_text() maps digits to letters (1->i 3->e 4->a 5->s
# 7->t 0->o), so "17" arrives as "it": the number slot accepts those letters too.
_VN_NUM = r"[oieast2689]{1,3}"
_VN_REF_TAIL = rf"(?:\s+{_VN_NUM}(?:[:.,]{_VN_NUM})?)?"

# Question words and book-slot prepositions per language (accent-free).
_VN_LANG = {
    "en": {"q": r"(?:why|how|when)", "in": r"in\s+(?:the\s+book\s+of\s+)?"},
    "it": {
        "q": r"(?:perche|come|quando)",
        "in": r"(?:in|nel|nella|nel\s+libro\s+(?:di|del|della)\s+)\s*",
    },
    "es": {"q": r"(?:por\s+que|como|cuando)", "in": r"(?:en|en\s+el\s+libro\s+de(?:l)?)\s+"},
    "pt": {"q": r"(?:por\s+que|como|quando)", "in": r"(?:em|no\s+livro\s+(?:de|do))\s+"},
    "fr": {
        "q": r"(?:pourquoi|comment|quand)",
        "in": r"(?:dans|en)\s+(?:le\s+livre\s+d(?:e\s+la|e|u)\s+)?",
    },
    "de": {"q": r"(?:warum|wieso|weshalb|wie|wann)", "in": r"(?:in|im\s+buch)\s+"},
}
_VN_EN_VERB = r"(?:kill|murder|slay|slaughter|stab)"  # no "shoot": no curated event is one
_NUMBERED_PREFIX_RE = re.compile(r"^(?:i{1,3}|[1-3ea])\.?\s+")


def _vn_book_alt(lang: str) -> str:
    names = {normalize_text(n).strip() for n in _registry_book_names(lang)}
    names = {n for n in names if len(_NUMBERED_PREFIX_RE.sub("", n)) >= 3}
    if lang == "ar":  # allow the definite article to be present or absent
        names |= {n.removeprefix("ال") for n in names}
    return _vn_alt({_vn_plain(n) for n in names})


# A frame is (compiled pattern, needs_completed): needs_completed=True for "did X kill Y"
# (only completed killings), False for "wanted/tried to kill" (attempts count too), None for
# commandment frames (no killer/victim slots).
_VnFrame = tuple["re.Pattern[str]", "bool | None"]


def _vn_build_frames(lang: str) -> list[_VnFrame]:
    """Closed whole-message frames for ``lang``; each has a killer ``s`` and a victim ``o``."""
    killers = {f for k, _, _ in _BIBLE_KILLING_EVENTS for f in _vn_forms(k, lang)}
    victims = {f for _, v, _ in _BIBLE_KILLING_EVENTS for f in _vn_forms(v, lang)}
    book = _vn_book_alt(lang)
    if lang == "ar":
        # Optional proclitic (و ف ب ل) and article; stripped again in the pair check.
        pre = r"(?:[وفبل]?(?:ال)?)"
        s = rf"(?P<s>{pre}(?:{_vn_alt(killers)}))"
        o = rf"(?P<o>{pre}(?:{_vn_alt(victims)}))"
        ref = rf"(?:\s+في\s+(?:سفر\s+)?(?:ال)?(?:{book}){_VN_REF_TAIL})?"
        q = r"(?:(?:لماذا|كيف|متى)\s+)?"
        qatl = "قتل"
        ar_pats: list[_VnFrame] = [
            (re.compile(rf"{q}{qatl}\s+{s}\s+{o}{ref}"), True),
            (re.compile(rf"{q}{s}\s+{qatl}\s+{o}{ref}"), True),
            (
                re.compile(rf"(?:لماذا|كيف)\s+[أا]راد\s+{s}\s+[أا]ن\s+يقتل\s+{o}{ref}"),
                False,
            ),
            (
                re.compile(
                    r"(?:(?:ماذا\s+تعني|ما\s+معنى)\s+(?:وصية\s+)?لا\s+تقتل"
                    r"|وصية\s+لا\s+تقتل\s+ماذا\s+تعني)"
                ),
                None,
            ),
        ]
        return ar_pats

    c = _VN_LANG[lang]
    q = c["q"]
    s = rf"(?P<s>{_vn_alt(killers)})"
    o = rf"(?P<o>{_vn_alt(victims)})"
    bk = rf"(?:\s+{c['in']}(?:{book}){_VN_REF_TAIL})?"
    pre = rf"(?:{c['in']}(?:{book}){_VN_REF_TAIL},\s*)?" if lang == "en" else ""
    raw: list[tuple[str, bool | None]] = []
    if lang == "en":
        raw = [
            (rf"{pre}{q}\s+did\s+{s}\s+{_VN_EN_VERB}\s+{o}{bk}", True),
            (
                rf"{pre}{q}\s+did\s+{s}\s+(?:want|try|decide|plan)\s+to\s+{_VN_EN_VERB}\s+{o}{bk}",
                False,
            ),
            (rf"did\s+{s}\s+(?:kill|murder)\s+{o}{bk}", True),
            (rf"why\s+didn['’]t\s+{s}\s+kill\s+{o}{bk}", False),
            # Commandment: only the archaic "thou shalt not" AND an explicit "what does it mean"
            # style lead or tail; bare commandments and the modern "you shall not" read as commands.
            (
                r"(?:(?:what\s+does|what\s+did\s+jesus\s+mean\s+by|why\s+does\s+the\s+bible"
                r"\s+say|what\s+is\s+the\s+meaning\s+of)\s+(?:thou\s+shalt|thou\s+shall)\s+not"
                r"\s+(?:kill|murder)(?:\s+mean)?"
                r"|(?:thou\s+shalt|thou\s+shall)\s+not\s+(?:kill|murder)"
                r"(?:\s+mean|\s+[-\u2013\u2014]\s+what\s+does\s+it\s+mean))",
                None,
            ),
        ]
    elif lang == "it":
        want = r"(?:volle|voleva|ha\s+voluto|cerco\s+di|decise\s+di|ha\s+deciso\s+di|ha\s+cercato\s+di)"
        past = r"(?:uccise|ha\s+ucciso)"
        raw = [
            (rf"{q}\s+{s}\s+{want}\s+uccidere\s+{o}{bk}", False),
            (rf"{q}\s+{s}\s+{past}\s+{o}{bk}", True),
            (rf"{q}\s+{past}\s+{s}\s+{o}{bk}", True),
        ]
    elif lang == "es":
        want = r"(?:quiso|queria|intento|trato\s+de|decidio|planeo)"
        past = r"(?:mato|asesino|ha\s+matado)"
        raw = [
            (rf"{q}\s+{s}\s+{want}\s+matar\s+a\s+{o}{bk}", False),
            (rf"{q}\s+{s}\s+{past}\s+a\s+{o}{bk}", True),
            (rf"{q}\s+{past}\s+{s}\s+a\s+{o}{bk}", True),
        ]
    elif lang == "pt":
        want = r"(?:quis|queria|tentou|decidiu|planejou)"
        past = r"(?:matou|assassinou|tinha\s+matado)"
        raw = [
            (rf"{q}\s+{s}\s+{want}\s+matar\s+{o}{bk}", False),
            (rf"{q}\s+{s}\s+{past}\s+{o}{bk}", True),
            (rf"{q}\s+{past}\s+{s}\s+{o}{bk}", True),
        ]
    elif lang == "fr":
        raw = [
            (
                rf"{q}\s+{s}\s+(?:a-t-(?:il|elle)\s+voulu|(?:voulait|voulut)-(?:il|elle)"
                rf"|a-t-(?:il|elle)\s+(?:essaye|decide)\s+de)\s+tuer\s+{o}{bk}",
                False,
            ),
            (rf"{q}\s+{s}\s+(?:a-t-(?:il|elle)\s+tue|tua-t-(?:il|elle))\s+{o}{bk}", True),
            (
                rf"{q}\s+{s}\s+(?:a\s+voulu|voulait|a\s+essaye\s+de|a\s+decide\s+de)\s+tuer\s+{o}{bk}",
                False,
            ),
            (rf"{q}\s+{s}\s+a\s+tue\s+{o}{bk}", True),
        ]
    elif lang == "de":
        raw = [
            (
                rf"(?:warum|wieso|weshalb)\s+(?:wollte|versuchte|beschloss|plante)\s+{s}\s+{o}{bk}"
                rf"\s+toten{bk}",
                False,
            ),
            (rf"{q}\s+hat\s+{s}\s+{o}{bk}\s+getotet{bk}", True),
            (rf"{q}\s+totete\s+{s}\s+{o}{bk}", True),
        ]
    return [(re.compile(p), done) for p, done in raw]


_VN_FRAMES = {lang: _vn_build_frames(lang) for lang in _VN_LANGS}
_VN_PAIRS = {
    lang: {True: _vn_pairs(lang, completed_only=True), False: _vn_pairs(lang, completed_only=False)}
    for lang in _VN_LANGS
}
# es and pt share the infinitive "matar" (one violence pattern), so a Spanish question must be
# exempt under the pt table and vice versa: each language checks both languages' frames/events.
_VN_OWNERS = {**{lang: (lang,) for lang in _VN_LANGS}, "es": ("es", "pt"), "pt": ("pt", "es")}


def _vn_ar_variants(name: str) -> set[str]:
    """Arabic name as written plus the forms with the proclitic (و ف ب ل) / article stripped."""
    out = {name}
    if name[:1] in ("و", "ف", "ب", "ل"):
        out.add(name[1:])
    out |= {n[2:] for n in out if n.startswith("ال")}
    return out


def _vn_pair_ok(owner: str, completed_only: bool, killer: str, victim: str) -> bool:
    pairs = _VN_PAIRS[owner][completed_only]
    if owner == "ar":
        return any(
            (k, v) in pairs for k in _vn_ar_variants(killer) for v in _vn_ar_variants(victim)
        )
    return (killer, victim) in pairs


def _vn_prepare(normalized: str) -> str | None:
    """Gate + unwrap: the accent-free single-sentence body, or None if the message can't qualify."""
    stripped = normalized.strip()
    if not stripped or "\n" in stripped:
        return None
    msg = re.sub(r"\s+", " ", stripped)
    if len(msg) > _VN_MAX_LEN:
        return None
    msg = _vn_plain(msg)
    if _VN_VETO.search(msg) or _VN_MIXED_SCRIPT.search(msg):
        return None
    body = msg.lstrip(_VN_WRAP_OPEN).rstrip(_VN_WRAP_CLOSE).strip()
    if body[-1:] in ("?", ".", "\u061f"):
        body = body[:-1].rstrip(_VN_WRAP_CLOSE + " ")
    return body


def _violence_narrative_whole_message_exempt(lang: str, normalized: str) -> bool:
    """True only when the ENTIRE message is one closed-form Bible-narrative question.

    BITB-257 round 5 (strict allowlist of curated killing EVENTS; mirrors BITB-238's
    `_dh_whole_message_exempt`). ``normalized`` must already be passed through
    :func:`normalize_text`. Ordered cheapest first: length (<= 200 chars after whitespace
    collapse), single line, scripts, veto, then a fullmatch of the unwrapped body against the
    language's closed frames, and finally the (killer, victim) pair must be a curated event
    (completed events for "did X kill Y", any event for "wanted/tried to kill"). Commandment
    frames have no pair. Languages without frames (ru/zh/hi/ko) are never exempt.
    """
    owners = _VN_OWNERS.get(lang)
    body = _vn_prepare(normalized) if owners else None
    if not owners or body is None:
        return False
    for owner in owners:
        for frame, completed in _VN_FRAMES[owner]:
            m = frame.fullmatch(body)
            if not m:
                continue
            if completed is None:  # commandment: no killer/victim slots
                return True
            if _vn_pair_ok(owner, completed, m.group("s"), m.group("o")):
                return True
    return False


class MultiLanguageContentFilter:
    """
    Multi-language content filter for violence, self-harm, hate speech.

    Supports 11 languages: EN, IT, DE, ES, FR, PT, AR, RU, ZH, HI, KO

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
            r"\bhand ?grenades?\b",
            r"\bmolotovs?\b",
            r"\bieds?\b",
            r"\bnapalm\b",
            r"\bricin\b",
            r"\banthrax\b",
            r"\bsarin\b",
            r"\bdetonat",
            r"\bmass[ -]?shoot",
            r"\bschool[ -]?shoot",
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
            r"\battentat",
            r"\bgranat[ae] a mano\b",
            r"\bmolotov\b",
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
            r"\bsprengsatz",
            r"\bhandgranate",
            r"\bmolotow",
            r"\bmolotov",
            r"\battentat",
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
            r"\batentado",
            r"\btiroteo",
            r"\bgranadas? de mano\b",
            r"\bmolotov\b",
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
            r"\battentat",
            r"\bfusillade",
            r"\bgrenades? (?:à|a) main\b",
            r"\bmolotov\b",
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
            r"\batentado",
            r"\btiroteio",
            r"\bgranadas? de m[aã]o\b",
            r"\bmolotov\b",
        ],
        "ar": [
            r"قنبلة",
            r"متفجر",
            r"سلاح",
            r"أسلحة",
            # BITB-257: bare "قتل" is kept (fail safe, as on main). find_violence_matches skips
            # it only when the WHOLE message is a closed frame naming a curated Bible killing
            # event (_violence_narrative_whole_message_exempt); everything else blocks.
            r"قتل",
            r"جريمة قتل",
            r"هجوم",
            r"إرهاب",
            r"تفجير",
            r"ناسف",
        ],
        # BITB-198: conservative native patterns for ru/zh/hi/ko. Unambiguous modern
        # weapon/terror words match alone; kill/attack verbs only in first-person intent or
        # how-to phrasing, so Bible narrative ("How did David kill Goliath?") stays clean.
        # BITB-257: the en/it/de/es/fr/pt/ar kill verbs keep bare patterns but are skipped when
        # the whole message is a closed frame for a curated Bible killing event
        # (see _violence_narrative_whole_message_exempt); ru/zh/hi/ko are never exempt.
        # Words with Bible/everyday senses (massacre, attack, bare explosion, ru оружие,
        # hi हथियार) stay hard-only (HARD_VIOLENCE_PATTERNS, checked next to self-harm).
        "ru": [
            r"\bбомб",
            r"\bвзрывчат",
            r"\bвзрывн\w*\s+устройств",
            r"\bвзорв(?:ать|у|ём|ем|ёт|ет|ут)\b",
            r"\bтеракт",
            r"\bтеррорист",
            r"\bтерроризм",
            r"\bогнестрельн",
            r"\bпистолет",
            r"\bгранатом[её]т",
            r"\bкоктейл\w*\s+молотова\b",
            r"\b(?:массов\w*|школьн\w*)\s+(?:расстрел|стрельб)",
            r"(?<!\bне )\b(?:хочу|хочется|собираюсь|планирую)\s+(?:(?!себя\b|самого\b|самой\b)\w+\s+){0,2}?"
            r"(?:убить|зарезать|застрелить|задушить|отравить|взорвать|расстрелять|напасть|атаковать)\b"
            r"(?!\s+(?:себя|самого\s+себя|самой\s+себя|в\s+себе))",
            r"\bкак\s+(?:мне\s+|можно\s+|лучше\s+|быстро\s+)?"
            r"(?:убить|зарезать|застрелить|задушить|отравить|взорвать|расстрелять|напасть|атаковать)\b"
            r"(?!\s+(?:себя|в\s+себе|время|скуку|грех|гордын|страст|плоть|ветхого|похоть))",
            r"\b(?:убью|зарежу|застрелю|взорву)\s+(?:тебя|вас|его|её|ее|их)\b",
            r"\bнапад(?:у|ём|ем)\s+на\b",
        ],
        "zh": [
            r"炸弹",
            r"炸彈",
            r"炸药",
            r"炸藥",
            r"爆炸物",
            r"爆裂物",
            r"手榴弹",
            r"手榴彈",
            r"燃烧瓶",
            r"燃燒瓶",
            r"恐怖(?:分子|份子|袭击|襲擊|主义|主義|活动|活動)",
            r"恐攻",
            r"恐袭",
            r"枪击",
            r"槍擊",
            r"枪支",
            r"槍支",
            r"槍枝",
            r"手枪",
            r"手槍",
            r"步枪",
            r"步槍",
            r"我(?:真的)?(?:想|要|会|會|打算|准备|準備|计划|計劃|决定|決定)(?:要)?(?:去)?"
            r"(?:杀|殺|捅死|毒死|炸死|炸掉|炸毁|炸毀|袭击|襲擊|攻击|攻擊|枪杀|槍殺)"
            r"(?!了?(?:我)?自己)(?![^，。！？,.!?]{0,8}(?:罪|骄傲|驕傲|老我|私欲|私慾|情欲|情慾|肉体|肉體))",
            r"(?:怎么|怎麼|怎样|怎樣|如何)(?:才能|可以|能)?(?:杀|殺)(?:死|掉)?(?:人|一个人|一個人|别人|別人|某人)",
        ],
        "hi": [
            r"(?<![\u0900-\u097f])बम(?:ों|ो)?(?![\u0900-\u097f])",
            r"बमबारी",
            r"विस्फोटक",
            r"आतंकवाद",
            r"आतंकी",
            r"बंदूक",
            r"पिस्तौल",
            r"ग्रेनेड",
            _HI_NOT_SELF
            + _HI_NB
            + r"(?:मार(?:ना|\s+डालना|\s+देना)|हत्या\s+करना|हमला\s+करना|गोली\s+मारना|उड़ा\s+देना)"
            r"\s+चाहत[ाी]\s+हू[ँं]",
            _HI_NOT_SELF + _HI_NB + r"मार\s+(?:दूँ|दूं|डालूँ|डालूं)(?:गा|गी)",
            r"कैसे\s+(?:मारें|मारूँ|मारूं|मार\s+डालें|मार\s+डालूँ|मार\s+डालूं|"
            + _HI_NB
            + r"हत्या\s+करें|"
            + _HI_NB
            + r"हत्या\s+करूँ|हमला\s+करें|हमला\s+करूँ)",
            _HI_NB + r"(?:हमला|हत्या)\s+कैसे\s+कर(?:ें|ूँ|ूं)",
        ],
        "ko": [
            r"폭탄",
            r"폭발물",
            r"폭파",
            r"테러",
            r"총기\s?난사",
            r"수류탄",
            r"화염병",
            r"(?<!자신을 )(?<!나를 )(?<!저를 )(?:죽이고|공격하고|살해하고)\s?싶(?:어|다|습니다|네)(?!\s?(?:하|했|해))",
            r"죽여\s?버(?:리겠|릴|리고\s?싶)",
            r"(?:죽일|공격할)\s?(?:거|겁니다|거야|거예요|거에요)(?:야|예요|에요|다)?(?![라고])",
            r"(?:사람|누군가|남|상대)(?:을|를)?\s?죽이는\s?(?:법|방법)",
        ],
    }

    # Hard-violence terms (BITB-185 v2 / H1): explosives, bombings, terror, massacre,
    # mass shooting. Matched script-agnostically (all languages at once) on normalized
    # text. In a self-harm message these are NEVER a "method" of self-harm, so they
    # force the crisis block regardless of any second-opinion verdict. Method words
    # (gun, weapon, knife, shoot, kill, arma, Waffe ...) are deliberately excluded.
    # BITB-198: every entry here either also appears in VIOLENCE_PATTERNS[lang] or is
    # hard-only because it occurs in Bible narrative / ordinary speech (massacre, attack,
    # bare explosion/terror).
    HARD_VIOLENCE_PATTERNS = {
        "en": [
            r"\bbombs?\b",
            r"\bbomb(?:ing|ings|er|ers)\b",
            r"\bexplosive",
            r"\bdetonat",
            r"\bterror(?:ism|ists?|s)?\b",
            r"\bmassacre",
            r"\bmass[ -]?shoot",
            r"\bschool[ -]?shoot",
            r"\bshoot(?:ing)? up\b(?!\s+(?:heroin|drugs?|meth|coke|cocaine|dope))",
            r"\bblow(?:ing)? up\b",
            r"\battack",
            r"\bgrenades?\b",
            r"\bmolotovs?\b",
            r"\bieds?\b",
            r"\bnapalm\b",
            r"\bricin\b",
            r"\banthrax\b",
            r"\bsarin\b",
        ],
        "it": [
            r"\bbomb[ae]\b",
            r"\besplosiv",
            r"\besplo[dn]",
            r"\battentat",
            r"\bterror",
            r"\bstrage\b",
            r"\bmassacro",
            r"\battacc(?:o|are|hi)\b",
            r"\bgranat[ae]\b",
            r"\bmolotov\b",
        ],
        "de": [
            r"\bbombe",
            r"\bsprengstoff",
            r"\bsprengsatz",
            r"\banschlag",
            r"\bterror",
            r"\bamok",
            r"\bmassaker",
            r"\battentat",
            r"\bangriff",
            r"\bhandgranate",
            r"\bgranaten?\b",
            r"\bmolotow",
            r"\bmolotov",
        ],
        "es": [
            r"\bbomba",
            r"\bexplosiv",
            r"\batentado",
            r"\bterror",
            r"\bmasacre",
            r"\btiroteo",
            r"\bataque\b",
            r"\bgranadas? de mano\b",
            r"\bmolotov\b",
        ],
        "fr": [
            r"\bbombe",
            r"\bexplosif",
            r"\bexplos",
            r"\battentat",
            r"\bterror",
            r"\bmassacre",
            r"\bfusillade",
            r"\battaque\b",
            r"\bgrenades? (?:\u00e0|a) main\b",
            r"\bgrenades? d[\u00e9e]goupill",
            r"\bmolotov\b",
        ],
        "pt": [
            r"\bbomba",
            r"\bexplosiv",
            r"\bexplod",
            r"\batentado",
            r"\bterror",
            r"\bmassacre",
            r"\btiroteio",
            r"\bataque\b",
            r"\bgranadas? de m[a\u00e3]o\b",
            r"\bmolotov\b",
        ],
        "ar": [
            r"قنبل",
            r"متفجر",
            r"تفجير",
            r"ناسف",
            r"إرهاب",
            r"ارهاب",
            r"مجزرة",
            r"هجوم",
        ],
        "ru": [
            r"бомб",
            r"взрывчат",
            r"взрыв",
            r"взорва",
            r"теракт",
            r"террор",
            r"расстрел",
            r"нападен",
            r"\bнапасть\s+на\b",
            r"\bнапад(?:у|ём|ем|ёт|ет|ут|ёте|ете)\b",
            r"\bгранатом[её]т",
            r"\bкоктейл\w*\s+молотова\b",
        ],
        "zh": [
            r"炸弹",
            r"炸藥",
            r"炸药",
            r"爆炸",
            r"爆破",
            r"恐怖(?:分子|份子|袭击|襲擊|主义|主義|活动|活動)",
            r"恐攻",
            r"恐袭",
            r"袭击",
            r"襲擊",
            r"屠杀",
            r"屠殺",
            r"枪击",
            r"槍擊",
            r"炸彈",
            r"手榴弹",
            r"手榴彈",
            r"燃烧瓶",
            r"燃燒瓶",
        ],
        "hi": [
            r"(?<![\u0900-\u097f])बम(?:ों|ो)?(?![\u0900-\u097f])",
            r"बमबारी",
            r"विस्फोट",
            r"आतंक",
            r"नरसंहार",
            r"हमला",
            r"ग्रेनेड",
        ],
        "ko": [
            r"폭탄",
            r"폭발물",
            r"폭발시[키킬켜킨킵켰]",
            r"폭파",
            r"테러",
            r"학살",
            r"총기\s?난사",
            r"수류탄",
            r"화염병",
        ],
    }

    # False-positive exclusions for hard violence (checked as a post-filter on each match
    # because they need variable-width context). A crisis message about anxiety must not be
    # treated as a threat just because it says "anxiety attacks" / "attacco di panico".
    _HARD_VIOLENCE_EXCLUDE_BEFORE = re.compile(
        r"\b(?:panic|anxiety|heart|asthma|nervous)[\s-]*$", re.IGNORECASE
    )
    _HARD_VIOLENCE_EXCLUDE_NIGHT = re.compile(r"\bnight[\s-]*$", re.IGNORECASE)
    _HARD_VIOLENCE_EXCLUDE_AFTER = re.compile(
        r"terror(?:iz|is)(?:ed|ing|es)\b|bombard(?:ed|ing|s)?\b|bombshell|"
        r"(?:attacc\w*|attaque|ataque)\s+"
        r"(?:(?:d['\u2019]\s*|di\s+|de\s+|do\s+)"
        r"(?:ansia|panico|cuore|p[a\u00e1\u00e2]nico|ansiedad|ansiedade|nervios|"
        r"coraz[o\u00f3]n|cora\u00e7\u00e3o|panique|anxi[e\u00e9]t[e\u00e9]|angoisse|"
        r"c\u0153ur|coeur)|card[i\u00ed]a\w*)",
        re.IGNORECASE,
    )

    # Self-harm patterns by language
    SELF_HARM_PATTERNS = {
        "en": [
            r"\bsuicide\b",
            r"\bkill myself\b",
            # BITB-238: exempted help-seeking questions ("Is it a sin to kill yourself?")
            # route to the compassionate path instead of the violence block.
            r"\bkill(?:ing)?\s+yourself\b",
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
            # BITB-196: split verb, "mich und meine Familie umbringen"
            r"\bmich\s+und\s+(?:meine[rn]?|mein|alle|die)\b[^.!?\n]{0,40}?\b(?:umbringen|töten)\b",
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
            r"\bquero que eu morra\b",
        ],
        "ar": [
            r"انتحار",
            r"أقتل نفسي",
            r"إنهاء حياتي",
            r"إيذاء النفس",
            r"أريد أن أموت",
        ],
        # BITB-183: ru uses \b (Cyrillic is word-char safe); zh/hi/ko use plain
        # substrings because there are no spaces (CJK) or \b is unreliable with
        # Devanagari combining marks (matras). Patterns stay specific: never a
        # bare 死 / 죽 / मर, which occur in ordinary Bible-study questions.
        "ru": [
            r"\bсамоубийств",
            r"\bсуицид",
            r"\bпокончить с собой\b",
            r"\bпокончу с собой\b",
            r"\bубить себя\b",
            # BITB-186 known limitation (accepted): the "не" guard is a fixed-width lookbehind,
            # so a double space ("не  хочу") or an intervening word ("не очень хочу умереть")
            # defeats it. Failing toward the compassionate path is the safe direction.
            r"(?<!\bне )\bхочу умереть\b",
            r"\bхочу сдохнуть\b",
            r"\bмне незачем жить\b(?!\s+(?:во?\s+(?:грехе|страхе)|ради\s+денег|для\s+себя))",
            r"\bзакончить свою жизнь\b",
            r"\bпорезать себя\b",
            r"\bсамоповреждени",
            r"\bнет смысла жить\b",
            r"\bне хочу жить\b",
            r"\bне хочу больше жить\b",
            r"\bжить не хочу\b",
            r"(?<!\bне )\bхочется умереть\b",
            r"\bубью себя\b",
            r"\bрежу себя\b",
        ],
        "zh": [
            r"自杀",
            # BITB-200: "一个人想跳楼" (alone) is a crisis phrasing; bare "人想跳楼" is third-person.
            r"(?:(?<![不他她人])|(?<=一个人)|(?<=一個人))(?<!为什么)(?<!為什麼)(?<!为何)(?<!為何)想跳[楼樓]",
            r"跳楼自",
            r"(?<!所罗门)(?<![他她])活[着著]没意思(?![吗嗎])",
            r"(?<!所羅門)(?<![他她])活[着著]沒意思(?![吗嗎])",
            r"自殺",
            r"(?:没有|沒有|失去)[他她]活[着著][没沒]意思",
            # BITB-200: first-person question form ("我觉得这样活着没意思吗") is a plea, not exegesis.
            r"我(?:觉得|覺得)?(?:这样|這樣|真的|总是|總是|一直)?活[着著][没沒]意思",
            r"(?<!不)想死(?!亡|后(?!一了百了)|後(?!一了百了)|你|人|海|刑)",
            r"(?<!不)想去死(?!亡|后(?!一了百了)|後(?!一了百了)|你|人|海|刑)",
            r"(?<!不)想要死(?!亡|后(?!一了百了)|後(?!一了百了)|你|人|海|刑)",
            r"轻生",
            r"輕生",
            r"寻死",
            r"尋死",
            r"自尽",
            r"自盡",
            r"不想活(?!在)",
            r"活不下去",
            r"结束(?:自己的)?生命",
            r"結束(?:自己的)?生命",
            r"结束我的生命",
            r"結束我的生命",
            r"自残",
            r"自殘",
            r"割腕",
            r"伤害自己",
            r"傷害自己",
            # BITB-196: "带着全家一起死" (taking the family along)
            r"[带帶]着?(?:全家人?|一家人|家人|孩子们?|老婆|妻子|丈夫|所有人|大家)一起(?:去)?死",
        ],
        "hi": [
            r"आत्महत्या",
            r"आत्म-हत्या",
            r"मरना चाहता",
            r"मरना चाहती",
            r"अपनी जान ले(?!कर)",
            r"ख\u093c?ुद को (?:नुक\u093c?सान|चोट|मार)",
            r"ख\u093c?ुदकुशी",
            r"मर जाना चाहत",
            r"जीना नहीं चाहता",
            r"जीना नहीं चाहती",
            r"जीने का कोई मतलब नहीं",
            r"(?<!क्या )(?<!अगर )मुझे मरना है",  # BITB-200: no "तो"/"?" guards
        ],
        "ko": [
            r"(?<!혼)자살",
            r"죽고 ?싶(?!지 ?않)",
            r"목숨을 ?끊",
            r"스스로 ?목숨",
            r"(?<![문저독학])자해(?![석설])",
            r"살기 ?싫",
            r"죽어 ?버[리릴]",
            r"살 ?이유가 ?없",
            r"살고 ?싶지 ?않",
            r"죽어 ?버리고 ?싶",
            r"삶을 ?끝내",
            r"사라지고 ?싶(?!지 ?않)",
        ],
    }

    # BITB-196: third-party part of murder-suicide / elliptical phrasing (see module table)
    MURDER_SUICIDE_PATTERNS = _MURDER_SUICIDE_PATTERNS

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
            r"\bgo\s+kill\s+yourself\b",
            r"\bkill\s+yourself\b",
            r"\bgo\s+die\b",
            r"\byou\s+should\s+die\b",
            r"\bi\s+will\s+kill\s+you\b",
            r"\bi\s+want\s+to\s+kill\s+you\b",
            r"\bgo\s+fuck\s+yourself\b",
        ],
        "it": [
            r"\bvattene a fanculo\b",
            r"\bti ammazzo\b",
            _DH_START + _DH_IT_LEAD + r"muori" + _DH_IT_TAIL + _DH_END,
            r"\b(?:inutile|stupid[oa]|idiota|bastard[oa]|schifos[oa]|maledett[oa])\s*,\s*muori"
            + _DH_IT_TAIL
            + _DH_END_STRONG,
            r"\bmuori,?\s+(?:bastard|stronz|maledett|schifos)\w*",
            r"\bspero che tu muoia\b" + _DH_IT_DIE_TO,
            r"\bspero che tu muoia\b[^.!?\n]{0,60}\b(?:bastard|stronz|maledett|schifos|inutil)\w*",
        ],
        "de": [
            r"\bgeh sterben\b",
            r"\bich töte dich\b",
            r"\bverpiss dich\b",
        ],
        "es": [
            r"\bvete a la mierda\b",
            r"\bte mato\b",
            (
                r"\bmu[ée]rete\b(?!\s+de\s+(?:la\s+)?"
                r"(?:risa|envidia|amor|ganas|hambre|fr[ií]o|calor|miedo|sueño|celos|vergüenza)\b)"
            ),
        ],
        "fr": [
            r"\bva te faire foutre\b",
            r"\bje vais te tuer\b",
            _DH_START + r"crève" + _DH_END,
            r"\bcrève,?\s+(?:(?:sale|espèce\s+de)\s+)?"
            r"(?:connard|salaud|salope|ordure|charogne|enfoiré|pourriture)\w*",
            r"\bva\s+crever\b",
            r"\bque\s+tu\s+vas\s+crever" + _DH_END_STRONG,
            r"\bque tu crèves\b",
        ],
        "pt": [
            r"\bvá se foder\b",
            r"\bvou te matar\b",
            _DH_START + r"morra" + _DH_END,
            r"\bmorra,?\s+(?:(?:seu|sua|seus|suas)\s+)?"
            r"(?:desgraçad|maldit|vagabund|idiota|imbecil|otári)\w*",
            r"\bque\s+(?:voc[êe]|tu)\s+morra\b" + _DH_PT_DIE_TO,
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

        # Compile hard-violence patterns into ONE script-agnostic regex (BITB-185 v2)
        self._hard_violence_regex = re.compile(
            "|".join(p for pats in self.HARD_VIOLENCE_PATTERNS.values() for p in pats),
            re.IGNORECASE | re.UNICODE,
        )

        # Compile murder-suicide patterns into ONE script-agnostic regex (BITB-196)
        self._murder_suicide_regex = re.compile(
            "|".join(p for pats in self.MURDER_SUICIDE_PATTERNS.values() for p in pats),
            re.IGNORECASE | re.UNICODE,
        )

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

    def find_self_harm(
        self, normalized: str, preferred: str | None = None
    ) -> tuple[str, str] | None:
        """Search the self-harm patterns of every language (script-agnostic, BITB-185).

        The ``preferred`` language is tried first, then every other language.
        ``normalized`` must already be passed through :func:`normalize_text`.

        Returns:
            ``(language, matched_text)`` for the first match, or ``None``.
        """
        langs = list(self._self_harm_regex)
        if preferred in self._self_harm_regex:
            langs.remove(preferred)
            langs.insert(0, preferred)
        for lang in langs:
            match = self._self_harm_regex[lang].search(normalized)
            if match:
                return lang, match.group(0)
        return None

    def find_all_self_harm_spans(self, normalized: str) -> list[tuple[int, int]]:
        """Return the ``(start, end)`` spans of EVERY self-harm match in every language.

        Script-agnostic (BITB-185 v2). Used to tell whether a violence keyword lies
        inside a self-harm phrase ("kill" in "kill myself") or outside it.
        """
        spans: list[tuple[int, int]] = []
        for regex in self._self_harm_regex.values():
            spans.extend(m.span() for m in regex.finditer(normalized))
        return spans

    def _violence_hits(self, lang: str, normalized: str) -> list[tuple[int, int, str]]:
        """Matches of ``lang``'s violence table; none if the WHOLE message is exempt (BITB-257).

        The exemption is computed once per message and only when the table matched at all, so
        the cost stays linear in the message length.
        """
        regex = self._violence_regex.get(lang)
        if not regex:
            return []
        hits = [(m.start(), m.end(), m.group(0)) for m in regex.finditer(normalized)]
        if hits and _violence_narrative_whole_message_exempt(lang, normalized):
            return []
        return hits

    def find_violence_matches(
        self, normalized: str, languages: list[str] | None = None
    ) -> list[tuple[int, int, str]]:
        """Return ``(start, end, text)`` for every violence match.

        ``languages=None`` searches the violence patterns of ALL languages
        (script-agnostic); otherwise only the listed languages.
        """
        langs = list(self._violence_regex) if languages is None else languages
        matches: list[tuple[int, int, str]] = []
        for lang in dict.fromkeys(langs):
            matches.extend(self._violence_hits(lang, normalized))
        return matches

    def find_hard_violence_matches(self, normalized: str) -> list[tuple[int, int, str]]:
        """Return ``(start, end, text)`` for every hard-violence term (bombs, terror, ...).

        Script-agnostic: all languages are searched at once. ``normalized`` must already
        be passed through :func:`normalize_text`.
        """
        matches: list[tuple[int, int, str]] = []
        for m in self._hard_violence_regex.finditer(normalized):
            before = normalized[max(0, m.start() - 20) : m.start()]
            term = m.group(0)
            # Context exclusions apply only to the ambiguous word itself, so a real hard
            # term next to "panic"/"night" ("nervous bombing", "night terrorists") still counts.
            if term.startswith("attack") and self._HARD_VIOLENCE_EXCLUDE_BEFORE.search(before):
                continue  # "panic attack", "heart-attack"
            if self._HARD_VIOLENCE_EXCLUDE_AFTER.match(normalized, m.start()):
                continue
            if term in ("terror", "terrors") and self._HARD_VIOLENCE_EXCLUDE_NIGHT.search(before):
                continue  # "night terrors" is a sleep disorder, not terrorism
            matches.append((m.start(), m.end(), m.group(0)))
        return matches

    def find_murder_suicide_matches(self, normalized: str) -> list[tuple[int, int, str]]:
        """Return ``(start, end, text)`` for third-party targets of murder-suicide phrasing.

        BITB-196: "kill myself AND MY FAMILY", "take everyone with me". Script-agnostic;
        ``normalized`` must already be passed through :func:`normalize_text`.
        """
        return [
            (m.start(), m.end(), m.group(0))
            for m in self._murder_suicide_regex.finditer(normalized)
        ]

    @staticmethod
    def _is_directed_harm_exempt(lang: str, normalized: str, m: re.Match[str]) -> bool:
        """True when the WHOLE message is a closed-form help-seeking / theological question.

        BITB-238: "Is it a sin to kill yourself?", "Why did Jesus have to go die on the
        cross?", "Does Paul say you should die to sin daily?". Strict allowlist: only English
        rules exist (other languages return False) and the exemption applies only when the
        entire message is a single sentence free of hostile words that fully matches one
        frame. ``normalized`` must already be passed through :func:`normalize_text`.
        """
        if lang != "en":
            return False
        return _dh_whole_message_exempt(normalized)

    def find_directed_harm_violation(
        self, normalized: str, preferred: str | None = None
    ) -> tuple[str, str, str] | None:
        """Search directed-harm patterns of EVERY language, then hate speech (BITB-193).

        The ``preferred`` language is tried first. ``normalized`` must already be passed
        through :func:`normalize_text`. English help-seeking / theological phrasings
        ("Is it a sin to kill yourself?") are skipped (BITB-238); a later genuine threat
        in the same message still returns a hit.

        Returns:
            ``(violation_type, language, matched_text)`` or ``None``. Hate speech reports
            language ``"all"``.
        """
        langs = list(self._directed_harm_regex)
        if preferred in self._directed_harm_regex:
            langs.remove(preferred)
            langs.insert(0, preferred)
        for lang in langs:
            for m in self._directed_harm_regex[lang].finditer(normalized):
                # BITB-238: skip help-seeking / theological uses; a later genuine threat
                # in the same message still blocks.
                if self._is_directed_harm_exempt(lang, normalized, m):
                    continue
                return ViolationType.DIRECTED_HARM.value, lang, m.group(0)
        m = self._hate_speech_regex.search(normalized)
        if m:
            return ViolationType.HATE_SPEECH.value, "all", m.group(0)
        return None

    def find_directed_harm(self, normalized: str) -> str | None:
        """Search directed-harm patterns (every language) and hate speech (BITB-185).

        ``normalized`` must already be passed through :func:`normalize_text`.

        Returns:
            The matched text, or ``None``.
        """
        result = self.find_directed_harm_violation(normalized)
        return result[2] if result else None

    def check_multilingual(
        self, text: str, language: str = "en"
    ) -> tuple[bool, str, str | None, str | None]:
        """
        Check text for harmful content.

        Stage 1 filter: Checks ONLY directed harm and hate speech patterns.
        Violence and self-harm patterns are now handled by OpenAI Moderation (Stage 2).
        Directed harm is checked in every language regardless of ``language`` (BITB-193),
        so a French threat sent from an English UI is still blocked; ``language`` only sets
        which table is tried first.

        Args:
            text: The message to check
            language: ISO 639-1 language code (en, it, de, es, fr, pt, ar, ru, zh, hi, ko)

        Returns:
            Tuple of (blocked, confidence, violation_type, pattern_matched)
            - blocked: True if content should be blocked
            - confidence: "high" (block immediately) or "low" (may be help-seeking)
            - violation_type: Type of violation detected (or None)
            - pattern_matched: The pattern that matched (for logging)
        """
        # Normalize text to catch evasion attempts
        normalized = normalize_text(text)

        violation = self.find_directed_harm_violation(normalized, preferred=language)
        if violation:
            vtype, matched_language, pattern = violation
            text_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
            logger.warning(
                "Content safety: %s detected",
                vtype.replace("_", " "),
                extra={
                    "text_hash": text_hash,
                    "language": language,
                    "matched_language": matched_language,
                    "pattern": pattern,
                    "violation_type": vtype,
                },
            )
            return True, "high", vtype, pattern

        # Violence and self-harm patterns are retained as class attributes
        # for fallback use, but are NOT checked in Stage 1.
        # OpenAI Moderation (Stage 2) handles these with context awareness.

        # No violations detected in Stage 1
        return False, "high", None, None
