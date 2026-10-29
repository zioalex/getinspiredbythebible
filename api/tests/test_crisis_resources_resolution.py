"""BITB-251: country resolution, classification, payload and markdown fallback."""

from dataclasses import dataclass, field

import pytest

from utils.crisis_resources import (
    SUPPORTED_LANGUAGES,
    CrisisKind,
    StaticRegistryProvider,
    build_crisis_payload,
    build_minimal_crisis_payload,
    classify_crisis,
    normalize_country_code,
    render_markdown_fallback,
    resolve_country,
)

LANGUAGES = list(SUPPORTED_LANGUAGES)
DEFAULTS = {
    "en": "US", "it": "IT", "de": "DE", "es": "ES", "fr": "FR", "pt": "BR",
    "ar": None, "ru": "RU", "zh": "CN", "hi": "IN", "ko": "KR",
}  # fmt: skip


@dataclass
class _Outcome:
    allowed: bool = True
    compassionate: bool = False
    reason: str = "clean"
    categories: dict = field(default_factory=dict)
    is_help_seeking: bool = False


# ---------------------------------------------------------------------------
# normalize_country_code
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        ("it", "IT"), ("IT", "IT"), (" de ", "DE"), ("XX", None), ("xx", None), ("T1", None),
        ("", None), (None, None), ("ITA", None), ("1", None), ("en-US", None), ("I1", None),
    ],
)  # fmt: skip
def test_normalize_country_code(value, expected):
    assert normalize_country_code(value) == expected


# ---------------------------------------------------------------------------
# resolve_country precedence, across all 11 languages
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("language", LANGUAGES)
class TestResolveCountry:
    def test_override_beats_ip_and_locale(self, language):
        assert resolve_country("FR", "BR", language, region_override=True) == ("BR", "override")

    def test_ip_beats_locale_when_not_override(self, language):
        assert resolve_country("FR", "BR", language) == ("FR", "ip")

    def test_override_flag_without_region_falls_to_ip(self, language):
        assert resolve_country("FR", None, language, region_override=True) == ("FR", "ip")

    def test_locale_used_when_no_ip(self, language):
        assert resolve_country(None, "AT", language) == ("AT", "locale")

    @pytest.mark.parametrize("bogus", ["XX", "T1", "", "ZZZ", "1", None])
    def test_unusable_ip_is_ignored(self, language, bogus):
        assert resolve_country(bogus, "AT", language) == ("AT", "locale")

    def test_language_default_when_nothing_else(self, language):
        expected = DEFAULTS[language]
        assert resolve_country(None, None, language) == (
            (expected, "language_default") if expected else (None, "none")
        )

    def test_xx_ip_with_no_region_uses_language_default(self, language):
        expected = DEFAULTS[language]
        assert resolve_country("XX", None, language) == (
            (expected, "language_default") if expected else (None, "none")
        )

    def test_lowercase_codes_are_normalized(self, language):
        assert resolve_country("it", None, language) == ("IT", "ip")
        assert resolve_country(None, "ch", language) == ("CH", "locale")


def test_regional_language_tag_uses_primary_subtag_default():
    assert resolve_country(None, None, "pt-BR") == ("BR", "language_default")
    assert resolve_country(None, None, "zh_CN") == ("CN", "language_default")


def test_unknown_language_without_region_is_none():
    assert resolve_country(None, None, "xx") == (None, "none")
    assert resolve_country(None, None, None) == ("US", "language_default")  # None -> en


def test_uk_alias_maps_to_gb():
    assert resolve_country("UK", None, "en") == ("GB", "ip")
    assert resolve_country(None, "UK", "en") == ("GB", "locale")


def test_unregistered_country_is_kept_so_no_wrong_local_numbers_are_shown():
    country, source = resolve_country("NZ", "US", "en")
    assert (country, source) == ("NZ", "ip")
    payload = build_crisis_payload(CrisisKind.SELF_HARM, country, source, "en")
    assert payload["country"] == "NZ"
    assert payload["emergency"] is None
    assert payload["lines"] == []
    assert payload["international_url"] == "https://findahelpline.com"


# ---------------------------------------------------------------------------
# classify_crisis
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "outcome,expected",
    [
        (_Outcome(allowed=True, compassionate=True, reason="possible_help_seeking"), "self_harm"),
        (_Outcome(allowed=True, is_help_seeking=True, reason="help_seeking_detected"), "self_harm"),
        (_Outcome(allowed=True, reason="clean"), None),
        (_Outcome(allowed=True, reason="disabled"), None),
        (_Outcome(allowed=False, reason="self_harm_instructions_detected"), "self_harm"),
        (_Outcome(allowed=False, reason="self_harm_with_violence (fallback)", is_help_seeking=True), "self_harm"),
        (_Outcome(allowed=False, reason="keyword_violation:self_harm (fallback)"), "self_harm"),
        (_Outcome(allowed=False, reason="violence_or_threat_detected"), "threat_to_others"),
        (_Outcome(allowed=False, reason="keyword_violation:violence (fallback)"), "threat_to_others"),
        (_Outcome(allowed=False, reason="harmful_intent_detected", categories={"self_harm": 4, "violence": 0}), "self_harm"),
        (_Outcome(allowed=False, reason="harmful_intent_detected", categories={"self_harm": 0, "violence": 6}), "threat_to_others"),
        (_Outcome(allowed=False, reason="harmful_intent_detected", categories={"hate": 6}), None),
        (_Outcome(allowed=False, reason="harmful_intent_detected", categories={"self_harm": 2, "violence": 3}), None),
        (_Outcome(allowed=False, reason="keyword_violation:directed_harm (fallback)"), None),
        (_Outcome(allowed=False, reason="keyword_violation:hate_speech (fallback)"), None),
        (_Outcome(allowed=False, reason="sexual_content_detected"), None),
        (_Outcome(allowed=False, reason="something_unmapped"), None),
    ],
)  # fmt: skip
def test_classify_crisis(outcome, expected):
    result = classify_crisis(outcome)
    assert (result.value if result else None) == expected


# ---------------------------------------------------------------------------
# build_crisis_payload
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("language", LANGUAGES)
def test_payload_shape_for_every_language(language):
    payload = build_crisis_payload(CrisisKind.SELF_HARM, "IT", "ip", language)
    assert set(payload) == {
        "kind", "country", "country_source", "emergency", "lines",
        "international_url", "available_countries",
    }  # fmt: skip
    assert payload["kind"] == "self_harm"
    assert payload["country"] == "IT"
    assert payload["country_source"] == "ip"
    assert payload["emergency"] == {"number": "112"}
    assert payload["international_url"] == "https://findahelpline.com"
    assert "IT" in payload["available_countries"]
    line = payload["lines"][0]
    assert set(line) == {"name", "phone", "sms", "hours", "url", "verified"}
    assert line["phone"] == "+39 02 2327 2327"
    assert line["name"] and line["hours"]


def test_payload_localizes_name_and_hours_with_english_fallback():
    it = build_crisis_payload(CrisisKind.SELF_HARM, "IT", "ip", "it")["lines"][0]
    en = build_crisis_payload(CrisisKind.SELF_HARM, "IT", "ip", "en")["lines"][0]
    assert it["hours"] == "Tutti i giorni, 10-24"
    assert en["hours"] == "Every day, 10:00-24:00"
    # CA has a French name; Korean falls back to English.
    ca_fr = build_crisis_payload(CrisisKind.SELF_HARM, "CA", "ip", "fr")["lines"][0]["name"]
    ca_ko = build_crisis_payload(CrisisKind.SELF_HARM, "CA", "ip", "ko")["lines"][0]["name"]
    assert "crise" in ca_fr
    assert ca_ko == "988 Suicide Crisis Helpline"


def test_threat_kind_uses_police_number_where_registry_distinguishes():
    assert build_crisis_payload(CrisisKind.THREAT_TO_OTHERS, "DE", "ip", "de")["emergency"] == {
        "number": "110"
    }
    assert build_crisis_payload(CrisisKind.SELF_HARM, "DE", "ip", "de")["emergency"] == {
        "number": "112"
    }


def test_no_country_gives_international_only():
    payload = build_crisis_payload(CrisisKind.SELF_HARM, None, "none", "ar")
    assert payload["country"] is None
    assert payload["emergency"] is None
    assert payload["lines"] == []
    assert payload["available_countries"]


def test_emergency_only_country_has_number_but_no_lines():
    payload = build_crisis_payload(CrisisKind.SELF_HARM, "EG", "ip", "ar")
    assert payload["emergency"] == {"number": "123"}
    assert payload["lines"] == []


def test_minimal_payload_matches_contract_keys():
    full = build_crisis_payload(CrisisKind.SELF_HARM, "US", "ip", "en")
    minimal = build_minimal_crisis_payload(CrisisKind.THREAT_TO_OTHERS)
    assert set(minimal) == set(full)
    assert minimal["kind"] == "threat_to_others"
    assert minimal["international_url"] == "https://findahelpline.com"


def test_provider_is_swappable():
    class _Fake:
        international_url = "https://example.test"

        def available_countries(self):
            return ["ZZ"]

        def canonical_country(self, country):
            return country

        def language_default(self, language):
            return "ZZ"

        def get_emergency(self, country):
            return None

        def get_lines(self, country):
            return []

    provider = _Fake()
    assert resolve_country(None, None, "en", provider=provider) == ("ZZ", "language_default")
    payload = build_crisis_payload(CrisisKind.SELF_HARM, "ZZ", "ip", "en", provider=provider)
    assert payload["international_url"] == "https://example.test"
    assert payload["available_countries"] == ["ZZ"]
    assert isinstance(StaticRegistryProvider(), StaticRegistryProvider)


# ---------------------------------------------------------------------------
# Markdown fallback
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("kind", list(CrisisKind))
def test_markdown_fallback_localized_for_every_language_and_kind(language, kind):
    payload = build_crisis_payload(kind, "IT", "ip", language)
    md = render_markdown_fallback(payload, language)
    assert "112" in md
    assert "+39 02 2327 2327" in md
    assert "https://findahelpline.com" in md
    if language != "en":
        assert md != render_markdown_fallback(payload, "en")


@pytest.mark.parametrize("language", LANGUAGES)
def test_markdown_fallback_without_country_says_local_emergency_number(language):
    payload = build_crisis_payload(CrisisKind.SELF_HARM, None, "none", language)
    md = render_markdown_fallback(payload, language)
    assert "https://findahelpline.com" in md
    assert "- " in md


def test_markdown_fallback_includes_sms_hours_and_url():
    md = render_markdown_fallback(
        build_crisis_payload(CrisisKind.SELF_HARM, "US", "ip", "en"), "en"
    )
    assert "**988**" in md
    assert "text **988**" in md
    assert "24/7" in md
    assert "https://988lifeline.org" in md


def test_markdown_fallback_threat_heading_differs_from_self_harm():
    sh = render_markdown_fallback(
        build_crisis_payload(CrisisKind.SELF_HARM, "US", "ip", "en"), "en"
    )
    th = render_markdown_fallback(
        build_crisis_payload(CrisisKind.THREAT_TO_OTHERS, "US", "ip", "en"), "en"
    )
    assert sh.splitlines()[0] != th.splitlines()[0]


def test_markdown_fallback_unknown_language_falls_back_to_english():
    payload = build_crisis_payload(CrisisKind.SELF_HARM, "US", "ip", "en")
    assert render_markdown_fallback(payload, "xx") == render_markdown_fallback(payload, "en")


def test_markdown_fallback_lists_arabic_and_cjk_without_mojibake():
    ar = render_markdown_fallback(
        build_crisis_payload(CrisisKind.SELF_HARM, "EG", "ip", "ar"), "ar"
    )
    assert "الطوارئ" in ar and "123" in ar
    zh = render_markdown_fallback(
        build_crisis_payload(CrisisKind.SELF_HARM, "CN", "ip", "zh"), "zh"
    )
    assert "12356" in zh and "紧急电话" in zh
