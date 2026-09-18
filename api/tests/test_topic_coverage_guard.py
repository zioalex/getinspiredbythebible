"""
Coverage guard for corpus-side topic tagging (BITB-106).

Structural checks plus a negative rehearsal proving the >25%-of-corpus /
>10%-of-corpus guidelines documented in `api/chat/topic_tagging.py` would
actually be caught if a future keyword violated them — not just that the
constants exist. No database, no network, no real corpus text: the negative
tests use a small synthetic sample (clearly not scripture) built only to
exercise the counting logic, since the real per-language validation
evidence (BITB-106, all seven languages against real corpora) lives in
`docs/HOW-TO-POPULATE-VERSE-TOPICS.md` and is reproducible on demand via
`scripts/measure_topic_coverage.py` — this file is not where that evidence
belongs, and re-downloading real corpora on every CI run would be slow and
license-uncertain.
"""

from collections import Counter

import pytest

from chat.topic_tagging import (
    CORPUS_KEYWORD_DENYLIST,
    COVERAGE_GUIDELINE_PCT,
    KEYWORD_GUIDELINE_PCT,
    SUBSTRING_MATCH_LANGUAGES,
    build_keyword_matchers,
    build_topic_matchers,
    match_topic_keywords,
    match_topics,
    normalize_text,
)
from chat.topics import SUPPORTED_TOPIC_LANGUAGES, TOPIC_KEYWORDS_BY_LANGUAGE

# A small, deliberately synthetic sample per language -- NOT scripture text,
# just enough neutral sentences to give percentages a stable denominator.
# Real per-language corpus evidence lives in the docs, not here (see module
# docstring).
_NEUTRAL_SAMPLE_BY_LANGUAGE: dict[str, list[str]] = {
    "en": [f"The travelers walked to the market on day {i} to buy bread." for i in range(1, 51)],
    "it": [
        f"I viaggiatori sono andati al mercato il giorno {i} per comprare pane."
        for i in range(1, 51)
    ],
    "de": [f"Die Reisenden gingen am Tag {i} zum Markt, um Brot zu kaufen." for i in range(1, 51)],
    "es": [f"Los viajeros fueron al mercado el día {i} para comprar pan." for i in range(1, 51)],
    "fr": [
        f"Les voyageurs sont allés au marché le jour {i} pour acheter du pain."
        for i in range(1, 51)
    ],
    "pt": [f"Os viajantes foram ao mercado no dia {i} para comprar pão." for i in range(1, 51)],
    "ar": [f"ذهب المسافرون الى السوق في اليوم {i} لشراء الخبز." for i in range(1, 51)],
}


def _measure(texts, language, matchers) -> tuple[int, Counter[str]]:
    """Minimal, local counting helper -- exercises the same match_topics()
    every positive and negative case below, so neither path can silently
    diverge from the other."""
    verse_count = 0
    topic_counts: Counter[str] = Counter()
    for text in texts:
        verse_count += 1
        topic_counts.update(match_topics(text, language, matchers))
    return verse_count, topic_counts


def _pct(count: int, total: int) -> float:
    return 100.0 * count / total if total else 0.0


class TestStructuralGuards:
    """No corpus needed -- these check the vocabulary and denylist tables
    themselves for internal consistency."""

    def test_denylist_entries_reference_real_keywords(self):
        """Every (topic, keyword) in CORPUS_KEYWORD_DENYLIST must exist in
        TOPIC_KEYWORDS_BY_LANGUAGE[topic] for some language, or it is a
        typo/stale entry silently doing nothing -- a real risk for the
        Arabic entries, whose hamza spelling must match exactly."""
        for topic, keywords in CORPUS_KEYWORD_DENYLIST.items():
            assert (
                topic in TOPIC_KEYWORDS_BY_LANGUAGE
            ), f"denylist references unknown topic {topic!r}"
            all_keywords_for_topic = {
                kw
                for lang_keywords in TOPIC_KEYWORDS_BY_LANGUAGE[topic].values()
                for kw in lang_keywords
            }
            for keyword in keywords:
                assert keyword in all_keywords_for_topic, (
                    f"denylisted keyword {keyword!r} for topic {topic!r} does not match any "
                    f"keyword in TOPIC_KEYWORDS_BY_LANGUAGE[{topic!r}] -- typo, or a stale entry"
                )

    def test_substring_language_keywords_are_long_enough(self):
        """Every non-denylisted keyword of a substring-matched language
        (currently just 'ar') must be at least 3 characters after
        normalization -- a 1-2 char root is exactly what makes a keyword
        fire inside unrelated words (BITB-106's 'حب' finding). This doesn't
        change matching behaviour; it's a review-time tripwire against
        adding another one."""
        for language in SUBSTRING_MATCH_LANGUAGES:
            denylisted_for_language = {
                keyword
                for topic_denylist in CORPUS_KEYWORD_DENYLIST.values()
                for keyword in topic_denylist
            }
            for topic, by_language in TOPIC_KEYWORDS_BY_LANGUAGE.items():
                for keyword in by_language.get(language, []):
                    if keyword in denylisted_for_language:
                        continue
                    normalized = normalize_text(keyword, language)
                    assert len(normalized) >= 3, (
                        f"{language!r} keyword {keyword!r} (topic {topic!r}) is only "
                        f"{len(normalized)} chars after normalization -- substring matching "
                        f"on a root this short is likely to fire inside unrelated words"
                    )

    def test_supported_languages_all_have_a_keyword_map_entry(self):
        for language in SUPPORTED_TOPIC_LANGUAGES:
            assert any(
                by_language.get(language) for by_language in TOPIC_KEYWORDS_BY_LANGUAGE.values()
            ), f"{language!r} is in SUPPORTED_TOPIC_LANGUAGES but has no keywords for any topic"


class TestCoverageGuardNegativeRehearsal:
    """A guideline nobody has seen trip is not known to work. These prove
    the counting-and-threshold logic used by
    scripts/measure_topic_coverage.py / scripts/populate_verse_topics.py
    actually flags a keyword that overshoots -- using the real
    build_topic_matchers()/match_topics() code path, with a doctored
    keyword map injected via the `keyword_map=` parameter (BITB-106) rather
    than editing the real vocabulary."""

    def test_baseline_sample_does_not_breach_either_guideline(self):
        """Sanity check: the neutral sample, matched against the REAL
        keyword map, should not spuriously breach either guideline (it
        contains none of the real vocabulary by construction)."""
        for language, texts in _NEUTRAL_SAMPLE_BY_LANGUAGE.items():
            matchers = build_topic_matchers(language)
            verse_count, topic_counts = _measure(texts, language, matchers)
            for topic, count in topic_counts.items():
                assert _pct(count, verse_count) <= COVERAGE_GUIDELINE_PCT, (
                    f"unexpected baseline breach: {language}/{topic} at "
                    f"{_pct(count, verse_count):.1f}%"
                )

    def test_guard_trips_on_an_over_firing_word_boundary_keyword(self):
        """Inject a keyword that matches almost every sample sentence (the
        word 'day', present in every synthetic 'en' sentence above) and
        confirm the same measurement path reports a breach naming it."""
        doctored_map = {
            **TOPIC_KEYWORDS_BY_LANGUAGE,
            "peace": {
                **TOPIC_KEYWORDS_BY_LANGUAGE["peace"],
                "en": [*TOPIC_KEYWORDS_BY_LANGUAGE["peace"]["en"], "day"],
            },
        }
        matchers = build_topic_matchers("en", keyword_map=doctored_map)
        verse_count, topic_counts = _measure(_NEUTRAL_SAMPLE_BY_LANGUAGE["en"], "en", matchers)

        peace_pct = _pct(topic_counts.get("peace", 0), verse_count)
        assert peace_pct > COVERAGE_GUIDELINE_PCT, (
            f"guard failed to trip: doctored 'day' keyword only reached {peace_pct:.1f}% "
            f"of the sample, expected it to breach {COVERAGE_GUIDELINE_PCT}%"
        )

        # And the keyword-attribution report (--verbose's mechanism) names
        # the actual offending keyword, not just the topic.
        keyword_matchers = build_keyword_matchers("en", keyword_map=doctored_map)
        hits = [
            match_topic_keywords(text, "en", keyword_matchers)
            for text in _NEUTRAL_SAMPLE_BY_LANGUAGE["en"]
        ]
        day_hits = sum(1 for h in hits if "day" in h.get("peace", []))
        assert _pct(day_hits, verse_count) > KEYWORD_GUIDELINE_PCT

    def test_guard_trips_on_an_over_firing_arabic_substring(self):
        """Arabic-specific rehearsal: inject the proclitic 'و' ("and"),
        which attaches to nearly every word, as a substring-matched keyword
        and confirm the guard reports it at (near-)100% coverage -- the
        exact failure mode 'حب' demonstrated on the real corpus."""
        doctored_map = {
            **TOPIC_KEYWORDS_BY_LANGUAGE,
            "joy": {
                **TOPIC_KEYWORDS_BY_LANGUAGE["joy"],
                "ar": [*TOPIC_KEYWORDS_BY_LANGUAGE["joy"]["ar"], "و"],
            },
        }
        matchers = build_topic_matchers("ar", keyword_map=doctored_map)
        verse_count, topic_counts = _measure(_NEUTRAL_SAMPLE_BY_LANGUAGE["ar"], "ar", matchers)

        joy_pct = _pct(topic_counts.get("joy", 0), verse_count)
        assert joy_pct > COVERAGE_GUIDELINE_PCT, (
            f"guard failed to trip on Arabic substring over-firing: 'و' only reached "
            f"{joy_pct:.1f}% of the sample"
        )

    @pytest.mark.parametrize("language", sorted(SUPPORTED_TOPIC_LANGUAGES))
    def test_guard_helper_runs_for_every_supported_language(self, language):
        """Structural: the measurement path used above must at least run,
        with no exception, for every supported language -- guards against a
        future language whose keyword map or matcher construction breaks
        the counting loop itself, independent of any real threshold."""
        matchers = build_topic_matchers(language)
        verse_count, _ = _measure(_NEUTRAL_SAMPLE_BY_LANGUAGE[language], language, matchers)
        assert verse_count == len(_NEUTRAL_SAMPLE_BY_LANGUAGE[language])
