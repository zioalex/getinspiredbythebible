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
        # BITB-198: native ru/zh/hi/ko patterns. Design: weapon/explosive/terror nouns plus
        # first-person INTENT or how-to forms for killing; never a bare killing verb or noun
        # (убить, 杀, मार, 죽이), so Bible narrative ("How did David kill Goliath?", "Не убий",
        # "不可杀人") stays clean. Deliberately HARD-only (HARD_VIOLENCE_PATTERNS, used next to
        # self-harm) because they collide with Bible narrative: ru нападен/взрыв/расстрел,
        # zh 袭击/屠杀/爆炸/爆破/bare 恐怖, hi हमला/नरसंहार/bare आतंक/bare विस्फोट,
        # ko 학살/bare 폭발. Intent forms exclude self-harm objects (себя, 自己, खुद को, 자신을).
        "ru": [
            r"\bбомб",
            r"\bвзрывчат",
            r"\bвзрывн\w*\s+устройств",
            r"\bвзорв(?:ать|у|ём|ем|ут)\b",
            r"\bтеракт",
            r"\bтеррор(?:ист|изм)",
            r"\bпистолет",
            r"\bвинтовк",
            r"\bружь[её]",
            r"\bогнестрельн",
            r"\bкалашников",
            (
                r"(?:(?<=\bхочу )|(?<=\bхочется )|(?<=\bсобираюсь )|(?<=\bпланирую )"
                r"|(?<=\bнадо )|(?<=\bкак ))"
                r"(?:убить|зарезать|застрелить|отравить|взорвать|напасть\s+на)\b"
                r"(?!\s+(?:себя|в\s+себе|грех|плоть|гордын|страх|время))"
            ),
            r"\b(?:убью|зарежу|застрелю|отравлю)\b(?!\s+себя)",
            r"\bнапад(?:у|ём|ем)\b",
        ],
        "zh": [
            r"炸弹|炸彈|炸药|炸藥|爆炸物|爆裂物|雷管|手榴弹|手榴彈|燃烧瓶|燃燒瓶",
            r"恐怖(?:分子|份子|袭击|襲擊|主义|主義|活动|活動)",
            r"恐攻|恐袭|恐襲",
            r"枪支|槍支|槍枝|手枪|手槍|步枪|步槍|开枪|開槍|枪击|槍擊|枪杀|槍殺",
            (
                r"(?:我|我们|我們)(?:要|想|想要|会|會|打算|准备|準備|计划|計劃|一定要|真想)(?:去)?"
                r"(?:杀|殺|砍|捅|毒死|弄死)(?!(?:了|死|掉)?(?:我)?自己)"
            ),
            r"(?:怎么|怎样|如何|怎麼|怎樣)(?:才能|可以|能)?(?:杀|殺)(?:人|掉别人|掉別人)",
            r"杀人(?:的)?(?:方法|办法)|殺人(?:的)?(?:方法|辦法)",
        ],
        "hi": [
            r"(?<![ऀ-ॿ])बम(?:ों|ो)?(?![ऀ-ॿ])",
            r"बमबारी",
            r"विस्फोटक",
            r"आतंकवा",
            r"आतंकी",
            r"ब(?:ं|न्)दूक",
            r"पिस्तौल",
            r"पिस्टल",
            r"राइफल",
            (
                r"(?<!खुद को )(?<!ख\u093cुद को )(?<!अपने आप को )(?<!अपने को )"
                r"(?<!खुद )(?<!ख\u093cुद )(?<!आत्म-)(?<!आत्म )(?<![ऀ-ॿ])"
                r"(?:मार डाल|मार|क\u093c?त्ल कर|हत्या कर|गोली मार)(?:ना|नी) चाहत[ाीे]"
                r"(?!\s*(?:था|थी|थे))"
            ),
            (
                r"(?<!खुद को )(?<!ख\u093cुद को )(?<!अपने आप को )(?<!अपने को )"
                r"(?<!खुद )(?<!ख\u093cुद )(?<!आत्म-)(?<!आत्म )(?<![ऀ-ॿ])"
                r"(?:मार (?:डाल|दे|द)|हत्या कर|क\u093c?त्ल कर|गोली मार)"
                r"(?:ूँगा|ूंगा|ूँगी|ूंगी)"
            ),
            r"कैसे मार(?:ें|ूँ|ूं)(?![ऀ-ॿ])",
            r"(?:हत्या|क\u093c?त्ल) कैसे कर(?:ें|ूँ|ूं)(?![ऀ-ॿ])",
        ],
        "ko": [
            r"폭탄|폭발물|폭파|폭발시[키킬켜킨킵켰]|수류탄|화염병|테러",
            r"총기|권총|소총|엽총|총(?:을|으로)\s?쏘",
            (
                r"(?<!자신을)(?<!자신을 )(?<!자기를 )(?<!나를 )(?<!스스로 )(?<!스스로)"
                r"죽이고\s?싶(?!어\s?하|어\s?했|어\s?한|어\s?해)"
            ),
            (
                r"죽여\s?버리(?:겠|고\s?싶|려)|죽여\s?버릴|죽일\s?(?:거|겁|꺼|테|게)"
                r"|죽이는\s?(?:방법|법)"
            ),
            (
                r"(?<!자)살인\s?(?:방법|계획)|(?<!자)살인하고\s?싶|(?<!자)살인할\s?(?:거|겁|게)"
                r"|살해하(?:고\s?싶|겠)"
            ),
        ],
    }

    # Hard-violence terms (BITB-185 v2 / H1): explosives, bombings, terror, massacre,
    # mass shooting. Matched script-agnostically (all languages at once) on normalized
    # text. In a self-harm message these are NEVER a "method" of self-harm, so they
    # force the crisis block regardless of any second-opinion verdict. Method words
    # (gun, weapon, knife, shoot, kill, arma, Waffe ...) are deliberately excluded.
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
            r"\bнапад(?:у|ём|ем)\b",
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
        ],
        "hi": [
            r"(?<![\u0900-\u097f])बम(?:ों|ो)?(?![\u0900-\u097f])",
            r"बमबारी",
            r"विस्फोट",
            r"आतंक",
            r"नरसंहार",
            r"हमला",
        ],
        "ko": [
            r"폭탄",
            r"폭발물",
            r"폭발시[키킬켜킨킵켰]",
            r"폭파",
            r"테러",
            r"학살",
            r"총기\s?난사",
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
            r"(?<![不他她人])(?<!为什么)(?<!為什麼)(?<!为何)(?<!為何)想跳楼",
            r"跳楼自",
            r"(?<!所罗门)(?<![他她])活[着著]没意思(?![吗嗎])",
            r"(?<!所羅門)(?<![他她])活[着著]沒意思(?![吗嗎])",
            r"自殺",
            r"(?:没有|沒有|失去)[他她]活[着著][没沒]意思",
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
            r"(?<!क्या )(?<!अगर )मुझे मरना है(?! तो)(?!\s*\?)",
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

        # Compile hard-violence patterns into ONE script-agnostic regex (BITB-185 v2)
        self._hard_violence_regex = re.compile(
            "|".join(p for pats in self.HARD_VIOLENCE_PATTERNS.values() for p in pats),
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

    def find_directed_harm(self, normalized: str) -> str | None:
        """Search directed-harm patterns (every language) and hate speech (BITB-185).

        ``normalized`` must already be passed through :func:`normalize_text`.

        Returns:
            The matched text, or ``None``.
        """
        for regex in (*self._directed_harm_regex.values(), self._hate_speech_regex):
            match = regex.search(normalized)
            if match:
                return match.group(0)
        return None

    def check_multilingual(
        self, text: str, language: str = "en"
    ) -> tuple[bool, str, str | None, str | None]:
        """
        Check text for harmful content in the specified language.

        Stage 1 filter: Checks ONLY directed harm and hate speech patterns.
        Violence and self-harm patterns are now handled by OpenAI Moderation (Stage 2).

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
