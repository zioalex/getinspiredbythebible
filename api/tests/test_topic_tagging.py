"""
Unit tests for corpus-side topic tagging in api/chat/topic_tagging.py
(BITB-044).

All tests are synchronous (no DB, no LLM required). Coverage focuses on the
guards that separate this from api/chat/topics.py's detect_topics(): per-
language matching, word-boundary + bounded-suffix matching instead of bare
substring containment, and Arabic clitic handling.
"""

import re

import pytest

from chat.topic_tagging import (
    CORPUS_KEYWORD_DENYLIST,
    build_keyword_matchers,
    build_topic_matchers,
    match_topic_keywords,
    match_topics,
    normalize_text,
)
from chat.topics import SUPPORTED_TOPIC_LANGUAGES, TOPIC_KEYWORDS_BY_LANGUAGE


class TestMatchTopicsEnglish:
    def test_peace_and_fear_in_one_verse(self):
        matchers = build_topic_matchers("en")
        topics = match_topics("Peace I leave with you... neither let it be afraid", "en", matchers)
        assert "peace" in topics
        assert "fear" in topics

    def test_trust_suffix_allowance(self):
        """ "trust" (5 chars) should match inflected "trusted" via the bounded
        suffix allowance, without "trusted" being spelled out in the map."""
        matchers = build_topic_matchers("en")
        assert "trust" in match_topics("they trusted in the Lord", "en", matchers)

    def test_restoreth_does_not_match_peace(self):
        """ "rest" + "ore" + "th" must not collapse into a false "rest" hit —
        the suffix allowance is bounded (<=3 chars) and word-boundary
        anchored, so "restoreth" should not trigger the "rest" keyword."""
        matchers = build_topic_matchers("en")
        assert "peace" not in match_topics("He restoreth my soul", "en", matchers)

    def test_made_does_not_match_anger(self):
        """ "mad" + "e" must not collapse into a false "mad" hit."""
        matchers = build_topic_matchers("en")
        assert "anger" not in match_topics("And Jesus was made whole", "en", matchers)

    def test_case_insensitive(self):
        matchers = build_topic_matchers("en")
        assert "anxiety" in match_topics("I AM VERY ANXIOUS TODAY", "en", matchers)

    def test_empty_string_matches_nothing(self):
        matchers = build_topic_matchers("en")
        assert match_topics("", "en", matchers) == []

    def test_unrelated_text_matches_nothing(self):
        matchers = build_topic_matchers("en")
        assert match_topics("The quick brown fox jumps over the lazy dog", "en", matchers) == []


class TestCrossLanguageGuard:
    """The load-bearing guard: a keyword that exists in one language's list
    must not fire against text tagged with a different language, even when
    the literal spelling collides (e.g. French "but" == English "but")."""

    def test_english_but_does_not_trigger_french_guidance_keyword(self):
        en_matchers = build_topic_matchers("en")
        topics = match_topics("I have no money, but I am content", "en", en_matchers)
        assert "guidance" not in topics

    def test_french_but_triggers_guidance_in_french(self):
        fr_matchers = build_topic_matchers("fr")
        topics = match_topics("Quel est le but de ma vie ?", "fr", fr_matchers)
        assert "guidance" in topics


class TestMatchTopicsMultilingual:
    def test_italian_grief(self):
        matchers = build_topic_matchers("it")
        assert "grief" in match_topics("Sono nella tristezza e nel dolore", "it", matchers)

    def test_german_peace(self):
        matchers = build_topic_matchers("de")
        assert "peace" in match_topics("Ihr sollt Frieden haben", "de", matchers)

    def test_arabic_fear_plain(self):
        matchers = build_topic_matchers("ar")
        assert "fear" in match_topics("خوف", "ar", matchers)

    def test_arabic_fear_with_attached_clitic(self):
        """Arabic "و" (and) attaches directly to the following word with no
        space; word-boundary matching would miss this, so Arabic uses plain
        substring matching instead."""
        matchers = build_topic_matchers("ar")
        assert "fear" in match_topics("وخوف عظيم", "ar", matchers)


class TestNormalizeText:
    def test_casefolds(self):
        assert normalize_text("ANXIOUS", "en") == "anxious"

    def test_nfd_and_nfc_equivalent(self):
        import unicodedata

        nfc = "ängstlich"
        nfd = unicodedata.normalize("NFD", nfc)
        assert normalize_text(nfc, "de") == normalize_text(nfd, "de")

    def test_nfd_verse_text_still_matches_nfc_keyword(self):
        import unicodedata

        matchers = build_topic_matchers("de")
        nfd_text = unicodedata.normalize("NFD", "Er war ängstlich und besorgt")
        assert "anxiety" in match_topics(nfd_text, "de", matchers)

    def test_arabic_strips_tashkeel(self):
        with_marks = "خَوْف"  # "khawf" with vowel marks
        without_marks = "خوف"
        assert normalize_text(with_marks, "ar") == normalize_text(without_marks, "ar")

    def test_arabic_folds_alef_variants(self):
        assert normalize_text("أمل", "ar") == normalize_text("امل", "ar")


class TestBuildKeywordMatchers:
    def test_denylist_excludes_keyword(self):
        matchers = build_keyword_matchers("en", denylist={"peace": {"rest"}})
        assert "rest" not in matchers["peace"]
        assert "peace" in matchers["peace"]  # sibling keyword unaffected

    def test_default_denylist_is_module_constant(self):
        default = build_keyword_matchers("en")
        explicit = build_keyword_matchers("en", denylist=CORPUS_KEYWORD_DENYLIST)
        assert default.keys() == explicit.keys()

    def test_every_topic_present_even_if_empty_for_language(self):
        matchers = build_keyword_matchers("en")
        assert set(matchers.keys()) == set(TOPIC_KEYWORDS_BY_LANGUAGE.keys())

    def test_compiled_patterns_are_regex(self):
        matchers = build_keyword_matchers("en")
        for kw_map in matchers.values():
            for pattern in kw_map.values():
                assert isinstance(pattern, re.Pattern)


class TestMatchTopicKeywords:
    def test_attributes_matching_keyword(self):
        keyword_matchers = build_keyword_matchers("en")
        hits = match_topic_keywords("I am anxious and worried", "en", keyword_matchers)
        assert "anxiety" in hits
        assert "anxious" in hits["anxiety"]
        assert "worried" in hits["anxiety"]

    def test_no_hits_returns_empty_dict(self):
        keyword_matchers = build_keyword_matchers("en")
        assert match_topic_keywords("The quick brown fox", "en", keyword_matchers) == {}


class TestStructuralInvariants:
    """Guards against silent drift between TOPIC_KEYWORDS_BY_LANGUAGE (used
    here) and TOPIC_KEYWORD_MAP (used by detect_topics on the query path) —
    see api/chat/topics.py's _flatten()."""

    @pytest.mark.parametrize("topic", list(TOPIC_KEYWORDS_BY_LANGUAGE.keys()))
    def test_topic_has_every_supported_language_key(self, topic):
        assert set(TOPIC_KEYWORDS_BY_LANGUAGE[topic].keys()) == set(SUPPORTED_TOPIC_LANGUAGES)

    def test_all_topics_have_at_least_one_keyword_per_language(self):
        for topic, by_language in TOPIC_KEYWORDS_BY_LANGUAGE.items():
            for language in SUPPORTED_TOPIC_LANGUAGES:
                assert len(by_language[language]) > 0, f"{topic}/{language} has no keywords"
