"""
Corpus-side topic tagging (BITB-044).

Matches verse text against the per-language topic keyword map
(``TOPIC_KEYWORDS_BY_LANGUAGE`` in ``api/chat/topics.py``) to decide which of
the 13 boosting topics a verse belongs to. Used by
``scripts/populate_verse_topics.py`` to seed the ``verse_topics`` junction
table; not used on the query path.

Why this is a separate module from ``detect_topics()``: that function runs
once per short user message, so a loose match barely matters — an extra
boost term at worst. Run the same loose matching against ~31k verses per
translation and it produces systematic noise (e.g. the French "guidance"
keyword "but" appearing inside unrelated English words, or generic words
like "rest" tagging a large fraction of a translation as "peace"). This
module adds two things ``detect_topics()`` doesn't need: per-language
matching (so a French keyword never fires on English text) and word-boundary
matching with a small bounded-inflection allowance instead of bare substring
containment.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping

from chat.topics import TOPIC_KEYWORDS_BY_LANGUAGE

# Keywords at least this long (after normalization) get a bounded suffix
# allowance so common inflections (English "trusted", German "sorgen") match
# without the map having to spell out every form. Chosen empirically: at 5+
# it catches real inflections (trust->trusted, forgive->forgiveth, guide->
# guided) while staying below false hits like peace->peaceable (+4) and
# grace->graceless (+4). See test_topic_tagging.py for the specific guard
# cases (e.g. "rest"+"ore"->"restoreth" must NOT tag as "peace").
SUFFIX_MIN_STEM_LEN = 5
SUFFIX_MAX_CHARS = 3

# Arabic clitics (و "and", ب "with", ل "for", ال "the", ...) attach directly
# to the following word with no space, so a \w boundary would miss most real
# occurrences. Arabic keywords are matched as plain (normalized) substrings
# instead of word-bounded patterns.
SUBSTRING_MATCH_LANGUAGES = frozenset({"ar"})

# A topic tagging more than this share of a translation's verses has stopped
# discriminating (BITB-044's guideline; confirmed on real corpora under
# BITB-106 — see CORPUS_KEYWORD_DENYLIST below).
COVERAGE_GUIDELINE_PCT = 25.0

# A second, narrower guideline for a single keyword. A topic can stay under
# COVERAGE_GUIDELINE_PCT while one keyword inside it is still mostly noise
# (BITB-106's Arabic findings below are all well under 25% by topic but a
# large majority of hits wrong at the keyword level — see the interior-match
# examples below). Set with ~3x headroom over the highest keyword measured
# across all seven validated languages (Arabic "حب" at 3.44%) — high enough
# that normal keyword variance doesn't trip it, low enough to catch another
# keyword behaving the way "حب" did.
KEYWORD_GUIDELINE_PCT = 10.0

# Keywords excluded from CORPUS tagging only (api/chat/topics.py's
# detect_topics() keeps the full vocabulary for query-time matching, where
# false positives are cheap). Structure: {topic: {keyword, ...}}.
#
# Validated against real corpora for all seven supported languages under
# BITB-106 (2026-09-18) via `scripts/measure_topic_coverage.py`, which uses
# this exact matching code — see that script's docstring for the
# calibration proof. Corpora: en/KJV (31,100v, in-repo), de/Luther 1912
# (31,102v, in-repo), it/Riveduta-OSIS (31,102v), es/Reina-Valera (31,102v),
# fr/fr_apee (30,975v — a stand-in for production's `ls1910`, which is not
# reachable from every environment), pt/Almeida-Atualizada (31,104v),
# ar/Smith-Van-Dyke (31,102v). No topic on any of the seven breaches
# COVERAGE_GUIDELINE_PCT — highest was ar "love" at 3.78%, comfortably under
# 25%. The word-boundary + bounded-suffix matching above is doing its job:
# the generic words a naive substring scan would have over-matched on
# ("way", "rest", "made", ...) are exactly what those rules exclude.
#
# Arabic is the one language matched by substring (see
# SUBSTRING_MATCH_LANGUAGES above), and substring matching on short roots
# fires inside unrelated words even while staying under the 25% *topic*
# guideline — a second, keyword-level failure mode COVERAGE_GUIDELINE_PCT
# alone cannot see. Measured on the real corpus (Smith & Van Dyke, 31,102
# verses): of the 1,071 verses "حب" (love, 2 chars) matched, the large
# majority are a different word entirely, not the intended standalone "حب"
# or "محبة" — "صاحبه" ("his companion", tens of occurrences), "رحبعام" (the
# proper name Rehoboam), "حبرون" (the place name Hebron), "فحبلت" ("she
# conceived", 17 occurrences exactly). Every entry below is kept out of
# corpus tagging for that reason, not for breaching the 25% topic guideline:
CORPUS_KEYWORD_DENYLIST: dict[str, set[str]] = {
    "love": {"حب"},
    # "حب" (love): 1,071 verses (3.44% of the corpus) — see the worked
    # example above. "محبة" (108 verses, no such issue — it is not a
    # substring of any unrelated word found here) still carries this topic.
    "hope": {"أمل", "يأس"},
    # "أمل" (hope): 397 verses (1.28%) — mostly "كامل" ("complete"), "حامل"
    # ("bearer/pregnant"), "عامل" ("worker"), "الارامل" ("the widows").
    # "يأس" (despair): 74 verses (0.24%) — mostly "قياس"/"القياس" ("measure"),
    # "رياسه" ("rulership"), the name "ابياساف" (Abiasaph). "وعد" (promise)
    # still carries this topic.
    "forgiveness": {"عفو"},
    # "عفو" (pardon): 15 verses (0.05%) — mostly verb forms of a different
    # root ("يعفو"/"تعفو"/"اعفو", "they/you double/forgive-in-a-different-
    # sense"). "مغفرة" / "رحمة" / "مصالحة" still carry this topic.
    "anxiety": {"قلق"},
    # "قلق" (anxiety): 26 verses (0.08%) — includes "اللقلق" ("the stork")
    # and verb forms of an unrelated root ("تتقلقل"/"يتقلقل", "it totters").
}
# Not denylisted despite a nonzero interior rate, because the interior hits
# are legitimate Arabic verbal derivations of the same root — exactly what
# substring matching exists to catch, not noise: "فرح" (joy, 41% interior:
# "يفرح", "افرحوا"), "فزع" (fear, 52%: "افزعتني"), "عطف" (love, 74%:
# "يتعطف", "استعطف"), "غضب" (anger, 3%), "سلام" (peace, 4%), "محبة" (love,
# 0%), "حكمة" (guidance, 0%), "إيمان" (trust, 0%).
#
# Follow-up filed as BITB-156: bare substring matching cannot separate
# "legitimate derivation" from "unrelated word containing the same three
# letters" in general — a clitic/affix-aware matcher would recover the
# denylisted keywords' recall without the noise (measured: "حب" 1,071 -> 793,
# "أمل" 397 -> 158, "يأس" 74 -> 13 under a clitic-anchored pattern — better,
# not sufficient, and a bigger change than this story should carry).

_ARABIC_TASHKEEL_RE = re.compile("[" "ؐ-ؚ" "ً-ٟ" "ٰ" "ۖ-ۭ" "ـ" "]")
_ARABIC_ALEF_RE = re.compile("[أإآٱ]")
_ARABIC_YEH_RE = re.compile("ى")
_ARABIC_TEH_MARBUTA_RE = re.compile("ة")

_SEPARATOR_RE = re.compile(r"(\s+|['’´]|-)")


def normalize_text(text: str, language: str) -> str:
    """NFC-normalize and casefold ``text``; for Arabic also strip tashkeel
    (vowel marks) / tatweel and fold alef/yeh/teh-marbuta variants so
    orthographic spelling differences don't cause missed matches.

    Deliberately does NOT strip Latin diacritics — keywords carry them
    (e.g. "ängstlich", "préoccupation") and stripping both sides risks
    collisions between otherwise-unrelated words. Known limitation: a verse
    spelled without diacritics where the map has them (or vice versa) will
    not match.
    """
    normalized = unicodedata.normalize("NFC", text).casefold()
    if language == "ar":
        normalized = _ARABIC_TASHKEEL_RE.sub("", normalized)
        normalized = _ARABIC_ALEF_RE.sub("ا", normalized)
        normalized = _ARABIC_YEH_RE.sub("ي", normalized)
        normalized = _ARABIC_TEH_MARBUTA_RE.sub("ه", normalized)
    return normalized


def _keyword_core_pattern(normalized_keyword: str, language: str) -> tuple[str, bool]:
    """Build the un-anchored regex core for one already-normalized keyword.

    Returns (pattern, is_single_token). Multi-word / hyphenated / apostrophe
    keywords never get the suffix allowance — it only makes sense for a bare
    stem, and appending it after a closing token would attach to the wrong
    place.
    """
    if language in SUBSTRING_MATCH_LANGUAGES:
        return re.escape(normalized_keyword), False

    tokens = _SEPARATOR_RE.split(normalized_keyword)
    parts: list[str] = []
    for token in tokens:
        if token == "":
            continue
        if token.isspace():
            parts.append(r"\s+")
        elif token in ("'", "’", "´"):
            parts.append(r"['’´]")
        elif token == "-":
            parts.append(r"[-\s]?")
        else:
            parts.append(re.escape(token))

    is_single_token = len(tokens) == 1
    core = "".join(parts)
    if is_single_token and len(normalized_keyword) >= SUFFIX_MIN_STEM_LEN:
        core += rf"[^\W\d_]{{0,{SUFFIX_MAX_CHARS}}}"
    return core, is_single_token


def _keyword_pattern(keyword: str, language: str) -> re.Pattern[str]:
    """Compile the full anchored (or, for Arabic, unanchored) pattern for one
    keyword in one language."""
    normalized = normalize_text(keyword, language)
    core, _ = _keyword_core_pattern(normalized, language)
    if language in SUBSTRING_MATCH_LANGUAGES:
        pattern = core
    else:
        pattern = rf"(?<!\w){core}(?!\w)"
    return re.compile(pattern)


def build_keyword_matchers(
    language: str,
    *,
    denylist: Mapping[str, set[str]] | None = None,
    keyword_map: Mapping[str, Mapping[str, list[str]]] | None = None,
) -> dict[str, dict[str, re.Pattern[str]]]:
    """Return ``{topic: {keyword: compiled_pattern}}`` for one language.

    ``denylist`` (default ``CORPUS_KEYWORD_DENYLIST``) drops specific
    keywords from corpus matching without touching the query-side map in
    ``api/chat/topics.py``. Pass ``denylist={}`` to disable filtering (e.g.
    to measure what the denylist is suppressing).

    ``keyword_map`` (default ``TOPIC_KEYWORDS_BY_LANGUAGE``) is the
    injection point the coverage guard's negative test uses to rehearse an
    over-firing keyword without editing the real vocabulary — see
    ``api/tests/test_topic_coverage_guard.py``.
    """
    if denylist is None:
        denylist = CORPUS_KEYWORD_DENYLIST
    if keyword_map is None:
        keyword_map = TOPIC_KEYWORDS_BY_LANGUAGE
    matchers: dict[str, dict[str, re.Pattern[str]]] = {}
    for topic, by_language in keyword_map.items():
        excluded = denylist.get(topic, set())
        topic_matchers: dict[str, re.Pattern[str]] = {}
        for keyword in by_language.get(language, []):
            if keyword in excluded:
                continue
            topic_matchers[keyword] = _keyword_pattern(keyword, language)
        matchers[topic] = topic_matchers
    return matchers


def build_topic_matchers(
    language: str,
    *,
    denylist: Mapping[str, set[str]] | None = None,
    keyword_map: Mapping[str, Mapping[str, list[str]]] | None = None,
) -> dict[str, re.Pattern[str]]:
    """Return ``{topic: compiled_alternation_pattern}`` for one language —
    one regex scan per topic per verse, rather than one scan per keyword.

    Keywords are combined longest-first; this only affects which keyword
    ``match_topic_keywords`` reports as the hit when several would match the
    same span, not whether the topic matches at all.
    """
    keyword_matchers = build_keyword_matchers(language, denylist=denylist, keyword_map=keyword_map)
    topic_patterns: dict[str, re.Pattern[str]] = {}
    for topic, kw_map in keyword_matchers.items():
        if not kw_map:
            continue
        ordered = sorted(kw_map.items(), key=lambda item: len(item[0]), reverse=True)
        combined = "|".join(f"(?:{pattern.pattern})" for _, pattern in ordered)
        topic_patterns[topic] = re.compile(combined)
    return topic_patterns


def match_topics(text: str, language: str, matchers: Mapping[str, re.Pattern[str]]) -> list[str]:
    """Return the sorted list of topics whose pattern matches ``text``.

    ``matchers`` is normally the output of ``build_topic_matchers(language)``
    — passed in explicitly so callers (the population script) build matchers
    once per language and reuse them across ~31k verses.
    """
    normalized = normalize_text(text, language)
    return sorted(topic for topic, pattern in matchers.items() if pattern.search(normalized))


def match_topic_keywords(
    text: str,
    language: str,
    keyword_matchers: Mapping[str, Mapping[str, re.Pattern[str]]],
) -> dict[str, list[str]]:
    """Return ``{topic: [matching_keyword, ...]}`` for ``text``, used by the
    population script's ``--verbose`` keyword-attribution report."""
    normalized = normalize_text(text, language)
    result: dict[str, list[str]] = {}
    for topic, kw_map in keyword_matchers.items():
        hits = [keyword for keyword, pattern in kw_map.items() if pattern.search(normalized)]
        if hits:
            result[topic] = hits
    return result
