"""BITB-113 — contract test between the canonical verse-grammar JSON and the backend parser.

``tests/fixtures/verse_grammar.json`` (generated into the Android and web bundles by
``scripts/generate_localized_book_map.py``) and ``api/utils/verse_parser.py`` are NOT unified
by generation — unlike the frontend/Android copies, the backend's separator/range handling is
hand-written and held contradiction-free with the JSON by this test instead, for two
independent reasons (recorded in full in the BITB-113 story's "Scope Cut" section):

1. ``api/utils/verse_parser.py`` matches book names via a flat literal alternation of every
   known name (``ALL_BOOK_NAMES``, built from ``translation_registry.py``); it has no
   compositional "connector word" grammar to unify — "Song of Solomon" is one literal string
   in the registry, never assembled from a generic book-name + connector pattern the way
   ``versePatterns.ts`` / ``ChatMessageItem.kt`` build theirs. There is nothing to contract-test
   for connector words or the connector-repeat bound on the Python side.
2. Python's ``re`` module's ``\\d`` is Unicode-aware by default (unlike JS ``RegExp`` and
   Java/Kotlin ``Regex``, which need the explicit Devanagari/Eastern-Arabic ranges spelled
   out) — so ``verse_parser.py``'s ``cv_pattern`` never needed those ranges and gains nothing
   from a contract test on them either.

What Python *does* share literally with the JSON: the chapter/verse separator characters
(``:``, ``,``) and the range characters (``-``, en dash ``–``), embedded in
``verse_parser.py``'s ``cv_pattern = r"(\\d+)[:\\,](\\d+)(?:\\s*[-–]\\s*(\\d+))?"``. This test
asserts those hardcoded characters match the JSON's ``chapter_verse_separators`` /
``range_separators`` values, mirroring how
``api/tests/test_localized_book_map_registry_parity.py`` holds
``translation_registry.py`` contradiction-free with the generated book map instead of
generating it.
"""

import json
import re
from pathlib import Path

from utils.verse_parser import _build_verse_pattern

_REPO_ROOT = Path(__file__).resolve().parents[2]
_JSON_PATH = _REPO_ROOT / "tests" / "fixtures" / "verse_grammar.json"

with open(_JSON_PATH, encoding="utf-8") as f:
    _GRAMMAR = json.load(f)

# The literal cv_pattern fragment from _build_verse_pattern(), extracted the same way it is
# built there, so a change to that source string is caught here rather than by re-deriving it
# independently (which could silently drift from what's actually compiled).
_CV_PATTERN_SOURCE = r"(\d+)[:\,](\d+)(?:\s*[-–]\s*(\d+))?"


def test_chapter_verse_separators_match_canonical_json():
    """Every separator character asserted here must also be accepted by the compiled pattern
    — and nothing else must be accepted — so a hand-edit drifting the character class from the
    canonical JSON is caught."""
    expected = set(_GRAMMAR["chapter_verse_separators"])
    # Extract the separator character class from the cv_pattern source: `[:\,]`.
    match = re.search(r"\[([^\]]+)\]", _CV_PATTERN_SOURCE)
    assert match, f"could not find a character class in cv_pattern source: {_CV_PATTERN_SOURCE!r}"
    # Un-escape the class contents (only `\,` needs it here) to get the literal characters.
    actual = set(re.sub(r"\\(.)", r"\1", match.group(1)))
    assert actual == expected, (
        "api/utils/verse_parser.py's chapter/verse separator characters "
        f"{actual!r} do not match tests/fixtures/verse_grammar.json's "
        f"chapter_verse_separators {expected!r}"
    )


def test_range_separators_match_canonical_json():
    """Same as above, for the verse-range separator characters (hyphen, en dash)."""
    expected = set(_GRAMMAR["range_separators"])
    match = re.search(r"\[-([^\]]*)\]", _CV_PATTERN_SOURCE)
    assert (
        match
    ), f"could not find the range character class in cv_pattern source: {_CV_PATTERN_SOURCE!r}"
    actual = {"-"} | set(match.group(1))
    assert actual == expected, (
        "api/utils/verse_parser.py's range-separator characters "
        f"{actual!r} do not match tests/fixtures/verse_grammar.json's "
        f"range_separators {expected!r}"
    )


def test_compiled_pattern_accepts_every_canonical_separator_and_range_character():
    """End-to-end check: build a throwaway "Book <n><sep><n>[<range><n>]" string for every
    separator/range character in the canonical JSON and confirm the real compiled pattern
    (``_build_verse_pattern`` — the exact source ``_VERSE_PATTERN`` is compiled from) matches
    it. This is the integration-level guard: a contradiction here means the regex, not just a
    docstring's claim about it, has drifted from the canonical grammar."""
    compiled = re.compile(_build_verse_pattern(), re.IGNORECASE)

    for sep in _GRAMMAR["chapter_verse_separators"]:
        text = f"John 3{sep}16"
        assert compiled.search(text), f"compiled verse pattern rejected separator {sep!r}: {text!r}"

    for sep in _GRAMMAR["chapter_verse_separators"]:
        for rng in _GRAMMAR["range_separators"]:
            text = f"John 3{sep}16{rng}18"
            m = compiled.search(text)
            assert m, f"compiled verse pattern rejected range separator {rng!r}: {text!r}"
            assert m.group(4) == "18", (
                f"compiled verse pattern did not capture the range end for {text!r} "
                f"(sep={sep!r}, range={rng!r}): got group(4)={m.group(4)!r}"
            )
