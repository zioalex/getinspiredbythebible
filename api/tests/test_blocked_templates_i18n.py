"""BITB-197: every blocked-response template exists in all 11 languages (no English fallback)."""

import re

import pytest

from chat.prompts import _BLOCKED_RESPONSE_TEMPLATES, get_blocked_response

LANGUAGES = ["en", "it", "de", "es", "fr", "pt", "ar", "ru", "zh", "hi", "ko"]
CATEGORIES = [
    "self_harm_blocked",
    "violence_or_threat",
    "hate_speech",
    "directed_harm",
    "sexual_content",
    "generic",
]
# One representative ContentSafetyCheckResult.reason per category.
REASONS = {
    "self_harm_blocked": "self_harm",
    "violence_or_threat": "violence",
    "hate_speech": "hate",
    "directed_harm": "directed_harm",
    "sexual_content": "sexual",
    "generic": "something_unmapped",
}
SCRIPT_RANGES = {
    "ar": r"[؀-ۿ]",
    "ru": r"[Ѐ-ӿ]",
    "zh": r"[一-鿿]",
    "hi": r"[ऀ-ॿ]",
    "ko": r"[가-힯]",
}


@pytest.mark.parametrize("category", CATEGORIES)
@pytest.mark.parametrize("language", LANGUAGES)
def test_template_exists_for_every_language(category, language):
    assert language in _BLOCKED_RESPONSE_TEMPLATES[category]


@pytest.mark.parametrize("category", CATEGORIES)
@pytest.mark.parametrize("language", [lang for lang in LANGUAGES if lang != "en"])
def test_template_is_not_the_english_text(category, language):
    en = _BLOCKED_RESPONSE_TEMPLATES[category]["en"]
    assert _BLOCKED_RESPONSE_TEMPLATES[category][language] != en
    assert get_blocked_response(REASONS[category], language) != get_blocked_response(
        REASONS[category], "en"
    )


@pytest.mark.parametrize("category", CATEGORIES)
@pytest.mark.parametrize("language", list(SCRIPT_RANGES))
def test_non_latin_templates_use_native_script(category, language):
    text = _BLOCKED_RESPONSE_TEMPLATES[category][language]
    native = re.findall(SCRIPT_RANGES[language], text)
    # Mostly native script; allow Latin only for URLs / hotline numbers.
    assert len(native) >= 20


@pytest.mark.parametrize("category", CATEGORIES)
@pytest.mark.parametrize("language", LANGUAGES)
def test_get_blocked_response_routes_to_localized_template(category, language):
    assert (
        get_blocked_response(REASONS[category], language)
        == _BLOCKED_RESPONSE_TEMPLATES[category][language]
    )


def test_unknown_language_still_falls_back_to_english():
    assert (
        get_blocked_response("violence", "xx")
        == _BLOCKED_RESPONSE_TEMPLATES["violence_or_threat"]["en"]
    )
