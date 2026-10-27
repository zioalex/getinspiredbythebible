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
            # BITB-238: help-seeking forms ("Is it a sin to kill yourself?") are no longer
            # blocked as directed harm at Stage 1; they reach the compassionate path here.
            r"\bkill(?:ing)?\s+(?:yourself|oneself)\b",
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
            r"\bgo kill yourself\b",
            r"\bi will kill you\b",
            r"\bi want to kill you\b",
            r"\bgo fuck yourself\b",
        ],
        "it": [
            r"\bvattene a fanculo\b",
            r"\bti ammazzo\b",
            _DH_START + r"muori" + _DH_END,
            r"\bmuori,?\s+(?:bastard|stronz|maledett|schifos)\w*",
            r"\bspero che tu muoia\b",
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
            r"\bcrève,?\s+(?:connard|salaud|salope|ordure)\w*",
            r"\bva\s+crever\b",
            r"\bque tu crèves\b",
        ],
        "pt": [
            r"\bvá se foder\b",
            r"\bvou te matar\b",
            _DH_START + r"morra" + _DH_END,
            r"\bmorra,?\s+(?:desgraçad|maldit|vagabund|idiota)\w*",
            r"\bque\s+(?:voc[êe]|tu)\s+morra\b",
        ],
    }

    # BITB-238: English phrases that are directed harm only as a threat, not as a question
    # ("Is it a sin to kill yourself?") or theology ("you should die to sin daily").
    # Evaluated by find_directed_harm_violation with the sentence-local context below.
    DIRECTED_HARM_CONTEXTUAL_EN = [
        r"\bkill\s+yourself\b",
        r"\bgo\s+die\b",
        r"\byou\s+should\s+die\b",
    ]

    # Text before the phrase (current sentence only) that makes it a threat: always blocks.
    _DH_THREAT_BEFORE = re.compile(
        r"(?:why\s+(?:don['\u2019]?t|do\s+not|won['\u2019]?t)\s+you"
        r"|you\s+(?:should|need\s+to|must|ought\s+to|had\s+better|better|can|could)"
        r"|i\s+(?:hope|wish|want)\s+you(?:\s+to)?"
        r"|just|please|go(?:\s+and)?)\s+(?:(?:just|go(?:\s+and)?)\s+)*$",
        re.IGNORECASE,
    )
    # Help-seeking context before "kill yourself": "what happens if you ..." is always exempt
    # (routes to compassion); "is it a sin/wrong/ok to ..." only when in question form.
    _DH_HELP_IF_BEFORE = re.compile(
        r"\b(?:if|when|whether|after|before)\s+(?:you|one|someone|a\s+person|people|they)\s+$",
        re.IGNORECASE,
    )
    _DH_HELP_KEYWORD_BEFORE = re.compile(
        r"\b(?:sin|wrong|ok|okay|allowed|forgiv\w*|unforgivable|permissible|hell|heaven)\b"
        r"[^.!?\n]{0,25}\bto\s+$",
        re.IGNORECASE,
    )
    # "you should die" is theology only as a complete "to sin/self/the flesh" or "daily" clause:
    # the phrase must end the sentence (a "..." ellipsis does not count) or be followed by a
    # scriptural-attribution clause. "you should die daily you idiot" / "... in a fire" block.
    _DH_THEOLOGY_AFTER_SHOULD_DIE = re.compile(
        r"\s+(?:(?:to|unto)\s+(?:sin|self|yourself|the\s+flesh|the\s+world)(?:\s+daily)?|daily)"
        r"\s*(?:\?|!|\.(?!\.)|$|[,;]\s+(?:according|as|because|since)\b)",
        re.IGNORECASE,
    )
    # "go die" is theology only with a theological subject right before it
    # ("Why did Jesus have to go die on the cross?", "Jesus had to go die for our sins").
    _DH_THEOLOGY_BEFORE = re.compile(
        r"\b(?:jesus|christ|he|the\s+son|the\s+lord|god|messiah)\s+"
        r"(?:(?:had|has|have|did|does|do|was|were|going|needed|need|got|to|really|actually|not)\s+){0,4}$",
        re.IGNORECASE,
    )
    # "kill yourself" followed by an instruction is a threat even inside a "question".
    _DH_DO_IT_AFTER = re.compile(r"\W*(?:so\s+)?(?:do|go\s+do)\s+it\b", re.IGNORECASE)

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

        self._directed_harm_contextual_regex = re.compile(
            "|".join(self.DIRECTED_HARM_CONTEXTUAL_EN), re.IGNORECASE | re.UNICODE
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
            regex = self._violence_regex.get(lang)
            if regex:
                matches.extend((m.start(), m.end(), m.group(0)) for m in regex.finditer(normalized))
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

    def find_directed_harm_violation(
        self, normalized: str, preferred: str | None = None
    ) -> tuple[str, str, str] | None:
        """Search directed-harm patterns of EVERY language, then hate speech (BITB-193).

        The ``preferred`` language is tried first. ``normalized`` must already be passed
        through :func:`normalize_text`.

        Returns:
            ``(violation_type, language, matched_text)`` or ``None``. Hate speech reports
            language ``"all"``.
        """
        langs = list(self._directed_harm_regex)
        if preferred in self._directed_harm_regex:
            langs.remove(preferred)
            langs.insert(0, preferred)
        for lang in langs:
            m = self._directed_harm_regex[lang].search(normalized)
            if m:
                return ViolationType.DIRECTED_HARM.value, lang, m.group(0)
        for m in self._directed_harm_contextual_regex.finditer(normalized):
            if not self._is_exempt_contextual_match(normalized, m):
                return ViolationType.DIRECTED_HARM.value, "en", m.group(0)
        m = self._hate_speech_regex.search(normalized)
        if m:
            return ViolationType.HATE_SPEECH.value, "all", m.group(0)
        return None

    def _is_exempt_contextual_match(self, normalized: str, m: re.Match) -> bool:
        """True when a contextual English phrase is a question/theology, not a threat (BITB-238)."""
        phrase = re.sub(r"\s+", " ", m.group(0).lower())
        cut = max(normalized.rfind(c, 0, m.start()) for c in ".!?\n")
        # Cap the lookbehind slice so the $-anchored regexes cannot backtrack over huge input.
        before = normalized[max(cut + 1, m.start() - 80) : m.start()]
        if self._DH_THREAT_BEFORE.search(before):
            return False
        after = normalized[m.end() :]
        if phrase == "kill yourself":
            if self._DH_DO_IT_AFTER.match(after):
                return False
            if self._DH_HELP_IF_BEFORE.search(before):
                return True
            return bool(self._DH_HELP_KEYWORD_BEFORE.search(before)) and self._is_question(
                before, after
            )
        if phrase == "go die":
            return bool(self._DH_THEOLOGY_BEFORE.search(before))
        if phrase == "you should die":
            return bool(self._DH_THEOLOGY_AFTER_SHOULD_DIE.match(after))
        return False

    @staticmethod
    def _is_question(before: str, after: str) -> bool:
        """True when the sentence containing the phrase is in question form."""
        if re.match(
            r"\s*(?:is|are|isn['\u2019]?t|does|do|did|will|would|can|could|should|may|what|why|"
            r"how|who|whether)\b",
            before,
            re.IGNORECASE,
        ):
            return True
        end = re.search(r"[.!?\n]", after)
        return bool(end and end.group(0) == "?")

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
