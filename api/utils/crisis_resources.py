"""
Crisis resources (BITB-251): deterministic hotline card for threats to self or others.

Single source of truth for the emergency / crisis numbers shown when the content-safety
pipeline detects someone threatening to hurt themselves or someone else. The data lives
in ``crisis_resources.json`` (next to this file); every entry carries an official
``source_url`` plus ``verified_on`` / ``verified_by`` so a human re-verification pass is
auditable (see ``docs/HOW-TO-VERIFY-CRISIS-RESOURCES.md``).

The chat path never calls a network service: it reads a ``CrisisResourceProvider``. The
only implementation today is :class:`StaticRegistryProvider`; a licensed feed (e.g.
ThroughLine) can be swapped in later without touching the chat path.

Nothing here logs or stores message text or the user's country.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

REGISTRY_PATH = Path(__file__).with_name("crisis_resources.json")

# Languages the app supports (UI + markdown fallback text).
SUPPORTED_LANGUAGES = ("en", "it", "de", "es", "fr", "pt", "ar", "ru", "zh", "hi", "ko")

# Cloudflare reports XX for "unknown" and T1 for Tor; neither is a usable country.
_IGNORED_COUNTRY_CODES = frozenset({"XX", "T1"})
_COUNTRY_RE = re.compile(r"^[A-Za-z]{2}$")

CountrySource = str  # "override" | "ip" | "locale" | "language_default" | "none"


class CrisisKind(str, Enum):
    """Why the card is shown."""

    SELF_HARM = "self_harm"
    THREAT_TO_OTHERS = "threat_to_others"


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


class _OutcomeLike(Protocol):
    allowed: bool
    compassionate: bool
    is_help_seeking: bool
    reason: str
    categories: dict[str, int]


def classify_crisis(outcome: _OutcomeLike) -> CrisisKind | None:
    """Map a content-safety outcome to a crisis kind, or ``None`` for no card.

    * allowed + compassionate / help-seeking            -> self_harm
    * blocked, self-harm category (incl. the ambiguous
      murder-suicide reason, OpenAI self-harm)           -> self_harm
    * blocked, violence_or_threat category               -> threat_to_others
    * blocked Azure ``harmful_intent_detected``          -> by category severities
    * directed_harm / hate / sexual / generic            -> None
    """
    # Lazy import: chat.prompts is imported by chat.service, which imports this module.
    from chat.prompts import _map_reason_to_category

    if outcome.allowed:
        return CrisisKind.SELF_HARM if (outcome.compassionate or outcome.is_help_seeking) else None

    reason = (outcome.reason or "").lower()
    category = _map_reason_to_category(reason)
    if category == "self_harm_blocked":
        return CrisisKind.SELF_HARM
    if category == "violence_or_threat":
        return CrisisKind.THREAT_TO_OTHERS
    if "harmful_intent_detected" in reason:
        # Imported here to keep this module importable without the full settings stack
        # in isolated tooling (scripts/check_crisis_resources.py).
        from config import settings

        threshold = settings.azure_content_safety_threshold
        categories = outcome.categories or {}
        if categories.get("self_harm", 0) >= threshold:
            return CrisisKind.SELF_HARM
        if categories.get("violence", 0) >= threshold:
            return CrisisKind.THREAT_TO_OTHERS
    return None


# ---------------------------------------------------------------------------
# Country resolution
# ---------------------------------------------------------------------------


def normalize_country_code(value: str | None) -> str | None:
    """Return an upper-cased ISO 3166-1 alpha-2 code, or ``None`` if unusable.

    ``XX`` (unknown) and ``T1`` (Tor) are treated as absent.
    """
    if not value or not isinstance(value, str):
        return None
    candidate = value.strip()
    if not _COUNTRY_RE.match(candidate):
        return None
    candidate = candidate.upper()
    if candidate in _IGNORED_COUNTRY_CODES:
        return None
    return candidate


def _primary_language(language: str | None) -> str:
    return (language or "en").replace("_", "-").split("-", 1)[0].lower()


def resolve_country(
    cf_country: str | None,
    client_region: str | None,
    language: str | None,
    region_override: bool = False,
    provider: CrisisResourceProvider | None = None,
) -> tuple[str | None, CountrySource]:
    """Pick the country whose numbers to show, and say where it came from.

    Precedence: user-picked override (``region_override`` + ``client_region``) ->
    ``CF-IPCountry`` -> client locale region -> per-language default -> none.
    """
    provider = provider or get_provider()
    region = normalize_country_code(client_region)
    if region:
        region = provider.canonical_country(region)

    if region_override and region:
        return region, "override"

    ip_country = normalize_country_code(cf_country)
    if ip_country:
        return provider.canonical_country(ip_country), "ip"

    if region:
        return region, "locale"

    default = provider.language_default(_primary_language(language))
    if default:
        return default, "language_default"

    return None, "none"


# ---------------------------------------------------------------------------
# Registry + provider
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EmergencyEntry:
    number: str
    threat_to_others_number: str | None
    source_url: str
    verified_on: date | None
    verified_by: str | None

    def number_for(self, kind: CrisisKind) -> str:
        if kind is CrisisKind.THREAT_TO_OTHERS and self.threat_to_others_number:
            return self.threat_to_others_number
        return self.number


@dataclass(frozen=True)
class CrisisLine:
    id: str
    name: dict[str, str]
    phone: str | None
    sms: str | None
    hours: dict[str, str] | None
    url: str | None
    source_url: str
    verified_on: date | None
    verified_by: str | None


class CrisisResourceProvider(Protocol):
    """Source of crisis data. The chat path depends only on this interface."""

    @property
    def international_url(self) -> str: ...

    def available_countries(self) -> list[str]: ...

    def canonical_country(self, country: str) -> str: ...

    def language_default(self, language: str) -> str | None: ...

    def get_emergency(self, country: str) -> EmergencyEntry | None: ...

    def get_lines(self, country: str) -> list[CrisisLine]: ...


def _parse_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


@lru_cache(maxsize=1)
def load_registry() -> dict[str, Any]:
    """Load the JSON registry once per process."""
    with REGISTRY_PATH.open(encoding="utf-8") as fh:
        data: dict[str, Any] = json.load(fh)
    return data


class StaticRegistryProvider:
    """Provider backed by the bundled ``crisis_resources.json``."""

    def __init__(self, registry: dict[str, Any] | None = None):
        self._registry = registry if registry is not None else load_registry()

    @property
    def international_url(self) -> str:
        return str(self._registry["international_url"])

    def available_countries(self) -> list[str]:
        codes = set(self._registry.get("emergency", {})) | set(self._registry.get("lines", {}))
        return sorted(codes)

    def canonical_country(self, country: str) -> str:
        return str(self._registry.get("region_aliases", {}).get(country, country))

    def language_default(self, language: str) -> str | None:
        value = self._registry.get("language_defaults", {}).get(language)
        return str(value) if value else None

    def get_emergency(self, country: str) -> EmergencyEntry | None:
        raw = self._registry.get("emergency", {}).get(country)
        if not raw:
            return None
        return EmergencyEntry(
            number=raw["number"],
            threat_to_others_number=raw.get("threat_to_others_number"),
            source_url=raw["source_url"],
            verified_on=_parse_date(raw.get("verified_on")),
            verified_by=raw.get("verified_by"),
        )

    def get_lines(self, country: str) -> list[CrisisLine]:
        return [
            CrisisLine(
                id=raw["id"],
                name=raw["name"],
                phone=raw.get("phone"),
                sms=raw.get("sms"),
                hours=raw.get("hours"),
                url=raw.get("url"),
                source_url=raw["source_url"],
                verified_on=_parse_date(raw.get("verified_on")),
                verified_by=raw.get("verified_by"),
            )
            for raw in self._registry.get("lines", {}).get(country, [])
        ]


@lru_cache(maxsize=1)
def get_provider() -> CrisisResourceProvider:
    """Process-wide default provider (swap here to use a licensed feed)."""
    return StaticRegistryProvider()


# ---------------------------------------------------------------------------
# Payload
# ---------------------------------------------------------------------------

_DEFAULT_INTERNATIONAL_URL = "https://findahelpline.com"


def _localized(values: dict[str, str] | None, language: str) -> str | None:
    if not values:
        return None
    return values.get(language) or values.get("en")


def build_crisis_payload(
    kind: CrisisKind,
    country: str | None,
    country_source: CountrySource,
    language: str | None,
    provider: CrisisResourceProvider | None = None,
) -> dict[str, Any]:
    """Build the ``crisis_resources`` wire payload (see BITB-251 contract)."""
    provider = provider or get_provider()
    lang = _primary_language(language)

    emergency_payload: dict[str, str] | None = None
    lines_payload: list[dict[str, Any]] = []
    if country:
        emergency = provider.get_emergency(country)
        if emergency:
            emergency_payload = {"number": emergency.number_for(kind)}
        for line in provider.get_lines(country):
            lines_payload.append(
                {
                    "name": _localized(line.name, lang) or "",
                    "phone": line.phone,
                    "sms": line.sms,
                    "hours": _localized(line.hours, lang),
                    "url": line.url,
                    "verified": line.verified_on is not None,
                }
            )

    return {
        "kind": kind.value,
        "country": country,
        "country_source": country_source,
        "emergency": emergency_payload,
        "lines": lines_payload,
        "international_url": provider.international_url,
        "available_countries": provider.available_countries(),
    }


def build_minimal_crisis_payload(kind: CrisisKind) -> dict[str, Any]:
    """Last-resort payload when the registry cannot be loaded: international link only."""
    return {
        "kind": kind.value,
        "country": None,
        "country_source": "none",
        "emergency": None,
        "lines": [],
        "international_url": _DEFAULT_INTERNATIONAL_URL,
        "available_countries": [],
    }


# ---------------------------------------------------------------------------
# Markdown fallback for clients that do not render the card
# ---------------------------------------------------------------------------

_FALLBACK_STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "heading_self_harm": "Please reach out for immediate support right now:",
        "heading_threat": "If anyone is in immediate danger, please call emergency services now:",
        "emergency": "Emergency",
        "local_emergency": "your local emergency number",
        "text": "text",
        "international": "International",
    },
    "it": {
        "heading_self_harm": "Ti chiedo di contattare subito qualcuno che possa aiutarti:",
        "heading_threat": "Se qualcuno è in pericolo immediato, chiama subito i servizi di emergenza:",
        "emergency": "Emergenza",
        "local_emergency": "il numero di emergenza locale",
        "text": "SMS",
        "international": "Internazionale",
    },
    "de": {
        "heading_self_harm": "Bitte wende dich sofort an jemanden, der helfen kann:",
        "heading_threat": "Wenn jemand in akuter Gefahr ist, ruf bitte sofort den Notruf an:",
        "emergency": "Notruf",
        "local_emergency": "die örtliche Notrufnummer",
        "text": "SMS",
        "international": "International",
    },
    "es": {
        "heading_self_harm": "Por favor, contacta ahora mismo con alguien que pueda ayudarte:",
        "heading_threat": "Si alguien está en peligro inmediato, llama ya a los servicios de emergencia:",
        "emergency": "Emergencias",
        "local_emergency": "tu número de emergencias local",
        "text": "SMS",
        "international": "Internacional",
    },
    "fr": {
        "heading_self_harm": "Je t'encourage à contacter immédiatement quelqu'un qui peut t'aider :",
        "heading_threat": "Si quelqu'un est en danger immédiat, appelle tout de suite les secours :",
        "emergency": "Urgences",
        "local_emergency": "ton numéro d'urgence local",
        "text": "SMS",
        "international": "International",
    },
    "pt": {
        "heading_self_harm": "Por favor, entre em contato agora com alguém que possa ajudar:",
        "heading_threat": "Se alguém está em perigo imediato, ligue agora para os serviços de emergência:",
        "emergency": "Emergência",
        "local_emergency": "o número de emergência local",
        "text": "SMS",
        "international": "Internacional",
    },
    "ar": {
        "heading_self_harm": "أرجو أن تتواصل الآن مع شخص يستطيع مساعدتك:",
        "heading_threat": "إذا كان أي شخص في خطر داهم، فاتصل بخدمات الطوارئ فوراً:",
        "emergency": "الطوارئ",
        "local_emergency": "رقم الطوارئ المحلي",
        "text": "رسالة نصية",
        "international": "دولي",
    },
    "ru": {
        "heading_self_harm": "Пожалуйста, прямо сейчас обратись к тому, кто может помочь:",
        "heading_threat": "Если кому-то грозит непосредственная опасность, немедленно позвони в экстренные службы:",
        "emergency": "Экстренная помощь",
        "local_emergency": "местный номер экстренных служб",
        "text": "SMS",
        "international": "В других странах",
    },
    "zh": {
        "heading_self_harm": "请现在就联系可以帮助你的人：",
        "heading_threat": "如果有人面临紧急危险，请立即拨打紧急服务电话：",
        "emergency": "紧急电话",
        "local_emergency": "当地的紧急求助电话",
        "text": "短信",
        "international": "国际",
    },
    "hi": {
        "heading_self_harm": "कृपया अभी किसी ऐसे व्यक्ति से संपर्क करें जो मदद कर सके:",
        "heading_threat": "यदि कोई तत्काल खतरे में है, तो कृपया अभी आपातकालीन सेवाओं को कॉल करें:",
        "emergency": "आपातकाल",
        "local_emergency": "आपका स्थानीय आपातकालीन नंबर",
        "text": "एसएमएस",
        "international": "अंतरराष्ट्रीय",
    },
    "ko": {
        "heading_self_harm": "지금 바로 도움을 줄 수 있는 사람에게 연락해 주세요:",
        "heading_threat": "누군가 즉각적인 위험에 처해 있다면 지금 바로 응급 서비스에 전화해 주세요:",
        "emergency": "응급",
        "local_emergency": "현지 응급 전화번호",
        "text": "문자",
        "international": "국제",
    },
}


def render_markdown_fallback(payload: dict[str, Any], language: str | None) -> str:
    """Render the payload as localized markdown for clients without the crisis card."""
    lang = _primary_language(language)
    strings = _FALLBACK_STRINGS.get(lang, _FALLBACK_STRINGS["en"])
    heading_key = (
        "heading_threat"
        if payload.get("kind") == CrisisKind.THREAT_TO_OTHERS
        else "heading_self_harm"
    )

    rows: list[str] = []
    emergency = payload.get("emergency")
    if emergency and emergency.get("number"):
        rows.append(f"- **{strings['emergency']}:** **{emergency['number']}**")
    else:
        rows.append(f"- **{strings['emergency']}:** {strings['local_emergency']}")

    for line in payload.get("lines", []):
        parts: list[str] = []
        if line.get("phone"):
            parts.append(f"**{line['phone']}**")
        if line.get("sms"):
            parts.append(f"{strings['text']} **{line['sms']}**")
        contact = ", ".join(parts)
        row = f"- **{line['name']}:** {contact}" if contact else f"- **{line['name']}**"
        if line.get("hours"):
            row += f" ({line['hours']})"
        if line.get("url"):
            row += f" - {line['url']}"
        rows.append(row)

    rows.append(f"- **{strings['international']}:** {payload['international_url']}")
    return f"{strings[heading_key]}\n" + "\n".join(rows)
