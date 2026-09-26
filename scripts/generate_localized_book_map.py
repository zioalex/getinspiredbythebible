#!/usr/bin/env python3
"""Generate the Android and web localized book-name maps and verse grammar (BITB-059/113).

Two independent canonical JSON sources, two independent sets of generated targets:

``tests/fixtures/localized_book_map.json`` is the single source of truth for the
localized-book-name -> canonical-English-book-name map. This script regenerates:

  - ``android/app/src/main/kotlin/org/voxquieta/app/utils/LocalizedBookToEnglish.kt``
  - ``frontend/src/lib/localizedBookMap.generated.ts``

``tests/fixtures/verse_grammar.json`` (BITB-113) is the single source of truth for the
literal separator/range/connector grammar fragments shared by the three hand-written verse
parsers. This script regenerates:

  - ``android/app/src/main/kotlin/org/voxquieta/app/utils/VerseGrammar.kt``
  - ``frontend/src/lib/verseGrammar.generated.ts``

from it. Never hand-edit any generated file: edit the relevant JSON, then run this script.

    python scripts/generate_localized_book_map.py

--check   Regenerate every target in memory and diff against the committed files. Exits 1
          (and prints a diff for each mismatch) if any differ — i.e. a generated file was
          hand-edited, or a JSON changed without regenerating. Safe for CI; makes no
          changes on disk.

Phase 1 (BITB-059) covered the Android book-map artifact. Phase 2 added the web book-map
artifact. The backend's own book-name map (``api/utils/translation_registry.py``) is a
separate master — it carries per-translation-code, case-preserving data the flat lowercase
JSON cannot represent — and is held contradiction-free with this JSON by
``api/tests/test_localized_book_map_registry_parity.py`` rather than generation.

BITB-113 adds the verse-grammar targets above. The backend's grammar
(``api/utils/verse_parser.py``) is, likewise, not generated from ``verse_grammar.json`` —
it is held contradiction-free by ``api/tests/test_verse_grammar_parity.py`` instead. See
that test's docstring, and the BITB-113 story's "Scope Cut" section, for why (Python has no
compositional connector-word grammar to unify, and its ``\\d`` is already Unicode-aware).
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
_JSON_PATH = _REPO_ROOT / "tests" / "fixtures" / "localized_book_map.json"
_ANDROID_UTILS_DIR = (
    _REPO_ROOT
    / "android"
    / "app"
    / "src"
    / "main"
    / "kotlin"
    / "org"
    / "voxquieta"
    / "app"
    / "utils"
)
_KT_PATH = _ANDROID_UTILS_DIR / "LocalizedBookToEnglish.kt"
_TS_PATH = _REPO_ROOT / "frontend" / "src" / "lib" / "localizedBookMap.generated.ts"

_GRAMMAR_JSON_PATH = _REPO_ROOT / "tests" / "fixtures" / "verse_grammar.json"
_GRAMMAR_KT_PATH = _ANDROID_UTILS_DIR / "VerseGrammar.kt"
_GRAMMAR_TS_PATH = _REPO_ROOT / "frontend" / "src" / "lib" / "verseGrammar.generated.ts"

_KT_HEADER = """package org.voxquieta.app.utils

/**
 * Bundled fallback map of localized Bible book names (lowercased) to their canonical
 * English book names (lowercased).
 *
 * This is the Android copy of the canonical map at tests/fixtures/localized_book_map.json
 * (BITB-059), which in turn mirrors the backend source of truth
 * (api/utils/translation_registry.py). It lets verse detection and normalization work
 * offline / before the /api/v1/scripture/book-names call returns. Runtime API data is
 * merged on top of — never replaced by — this map.
 *
 * @generated from tests/fixtures/localized_book_map.json by
 * scripts/generate_localized_book_map.py — DO NOT EDIT individual entries by hand. Edit the
 * JSON and re-run the generator; LocalizedBookToEnglishTest checks content equivalence
 * against the JSON so drift fails CI.
 */
internal val LOCALIZED_BOOK_TO_ENGLISH: Map<String, String> = mapOf(
"""

_KT_FOOTER = ")\n"

_TS_HEADER = """/**
 * Bundled fallback map of localized Bible book names (lowercased) to their canonical
 * English book names (lowercased).
 *
 * Canonical source: tests/fixtures/localized_book_map.json (BITB-059). The Android copy
 * (android/.../utils/LocalizedBookToEnglish.kt) is generated from the same file. The
 * backend's own map (api/utils/translation_registry.py) is a separate master, held
 * contradiction-free by api/tests/test_localized_book_map_registry_parity.py.
 *
 * Runtime API data from /api/v1/scripture/book-names is merged on top of — never
 * replaces — this map, via updateBookNames() in verseExtraction.ts.
 *
 * @generated from tests/fixtures/localized_book_map.json by
 * scripts/generate_localized_book_map.py — DO NOT EDIT individual entries by hand. Edit
 * the JSON and re-run the generator.
 */
// prettier-ignore
export const LOCALIZED_BOOK_TO_ENGLISH: Record<string, string> = {
"""

_TS_FOOTER = "};\n"


def _load_book_map() -> dict[str, str]:
    payload = json.loads(_JSON_PATH.read_text(encoding="utf-8"))
    return payload["book_map"]


def _load_verse_grammar() -> dict:
    return json.loads(_GRAMMAR_JSON_PATH.read_text(encoding="utf-8"))


def _kt_string_literal(value: str) -> str:
    # The book-name map never contains characters that need escaping beyond the
    # standard Kotlin string escapes; guard against surprises rather than silently
    # emitting invalid Kotlin.
    if '"' in value or "\\" in value or "\n" in value:
        raise ValueError(f"value requires escaping the generator does not support: {value!r}")
    return f'"{value}"'


def render_kotlin(book_map: dict[str, str]) -> str:
    lines = [_KT_HEADER]
    for key, value in book_map.items():
        lines.append(f"    {_kt_string_literal(key)} to {_kt_string_literal(value)},\n")
    lines.append(_KT_FOOTER)
    return "".join(lines)


def _ts_string_literal(value: str) -> str:
    # json.dumps produces a valid TS/JS string literal for every key/value in the map;
    # ensure_ascii=False keeps the non-Latin book names human-readable in the source.
    return json.dumps(value, ensure_ascii=False)


def render_typescript(book_map: dict[str, str]) -> str:
    lines = [_TS_HEADER]
    for key, value in book_map.items():
        lines.append(f"  {_ts_string_literal(key)}: {_ts_string_literal(value)},\n")
    lines.append(_TS_FOOTER)
    return "".join(lines)


# ---------------------------------------------------------------------------
# Verse grammar (BITB-113) — separator/range/connector fragments literally
# shared by the three hand-written verse parsers.
# ---------------------------------------------------------------------------

_GRAMMAR_TS_HEADER = """/**
 * Literal separator/range/connector grammar fragments shared by the verse-reference
 * parsers (BITB-113).
 *
 * Canonical source: tests/fixtures/verse_grammar.json. The Android copy
 * (android/.../utils/VerseGrammar.kt) is generated from the same file. The backend
 * (api/utils/verse_parser.py) is a separate master for its own separator/range characters,
 * held contradiction-free by api/tests/test_verse_grammar_parity.py — Python has no
 * compositional connector-word grammar to unify (see that test's docstring) and its `\\d`
 * is already Unicode-aware, so it does not need the connector words or non-ASCII digit
 * ranges below.
 *
 * versePatterns.ts composes these into its own regex fragments (escaping/joining as
 * needed) — this file exports plain strings/values only, never a compiled RegExp.
 *
 * CONNECTOR_REPEAT_MAX is the shared UPPER bound only (the ReDoS-safety cap from
 * BITB-108/114/117: an unbounded connector-repeat quantifier let adversarial input drive
 * superlinear regex backtracking). The *lower* bound on the connector-repeat quantifier is
 * NOT generated here and legitimately differs between versePatterns.ts (which uses a
 * minimum of 1 in its dedicated "word CONNECTOR word" fallback branch — single-word books
 * are matched by a separate branch) and ChatMessageItem.kt (whose BOOK_NAME is one pattern
 * shared by single- and multi-word books, so its connector group must allow a minimum of
 * 0). See docs/BACKLOG_STORIES/BITB-113-verse-parser-grammar-unification.md for the full
 * investigation of that discrepancy.
 *
 * @generated from tests/fixtures/verse_grammar.json by
 * scripts/generate_localized_book_map.py — DO NOT EDIT individual entries by hand. Edit
 * the JSON and re-run the generator.
 */
"""

_GRAMMAR_KT_HEADER = """package org.voxquieta.app.utils

/**
 * Literal separator/range/connector grammar fragments shared by the verse-reference
 * parsers (BITB-113).
 *
 * Canonical source: tests/fixtures/verse_grammar.json. The web copy
 * (frontend/src/lib/verseGrammar.generated.ts) is generated from the same file. The
 * backend (api/utils/verse_parser.py) is a separate master for its own separator/range
 * characters, held contradiction-free by api/tests/test_verse_grammar_parity.py — Python
 * has no compositional connector-word grammar to unify (see that test's docstring) and its
 * `\\d` is already Unicode-aware, so it does not need the connector words or non-ASCII
 * digit ranges below.
 *
 * ChatMessageItem.kt composes these into its own regex fragments — this object exposes
 * plain constants only, never a compiled Regex.
 *
 * [CONNECTOR_REPEAT_MAX] is the shared UPPER bound only (the ReDoS-safety cap from
 * BITB-108/114/117: an unbounded connector-repeat quantifier let adversarial input drive
 * superlinear regex backtracking). The *lower* bound on the connector-repeat quantifier is
 * NOT generated here and legitimately differs between ChatMessageItem.kt's BOOK_NAME
 * (minimum 0 — one pattern shared by single- and multi-word books) and versePatterns.ts
 * (minimum 1 in its dedicated "word CONNECTOR word" fallback branch — single-word books
 * are matched by a separate branch there). See
 * docs/BACKLOG_STORIES/BITB-113-verse-parser-grammar-unification.md for the full
 * investigation of that discrepancy.
 *
 * @generated from tests/fixtures/verse_grammar.json by
 * scripts/generate_localized_book_map.py — DO NOT EDIT individual entries by hand. Edit
 * the JSON and re-run the generator; VerseGrammarTest checks content equivalence against
 * the JSON so drift fails CI.
 */
internal object VerseGrammar {
"""

_GRAMMAR_KT_FOOTER = "}\n"


def render_grammar_typescript(grammar: dict) -> str:
    lines = [_GRAMMAR_TS_HEADER, "\n"]

    connector_words = grammar["connector_words"]
    lines.append("export const CONNECTOR_WORDS: string[] = [\n")
    for word in connector_words:
        lines.append(f"  {_ts_string_literal(word)},\n")
    lines.append("];\n\n")

    lines.append(f"export const CONNECTOR_REPEAT_MAX = {grammar['connector_repeat_max']};\n\n")

    cv_seps = grammar["chapter_verse_separators"]
    lines.append(
        "export const CHAPTER_VERSE_SEPARATORS: string[] = ["
        + ", ".join(_ts_string_literal(s) for s in cv_seps)
        + "];\n\n"
    )

    range_seps = grammar["range_separators"]
    lines.append(
        "export const RANGE_SEPARATORS: string[] = ["
        + ", ".join(_ts_string_literal(s) for s in range_seps)
        + "];\n\n"
    )

    lines.append("export interface NonAsciiDigitRange {\n")
    lines.append("  label: string;\n")
    lines.append("  start: string;\n")
    lines.append("  end: string;\n")
    lines.append("}\n\n")
    lines.append("export const NON_ASCII_DIGIT_RANGES: NonAsciiDigitRange[] = [\n")
    for r in grammar["non_ascii_digit_ranges"]:
        lines.append(
            "  { label: "
            f"{_ts_string_literal(r['label'])}, start: {_ts_string_literal(r['start'])}, "
            f"end: {_ts_string_literal(r['end'])} }},\n"
        )
    lines.append("];\n\n")

    lines.append("export interface CjkBracketPair {\n")
    lines.append("  label: string;\n")
    lines.append("  open: string;\n")
    lines.append("  close: string;\n")
    lines.append("}\n\n")
    lines.append("export const CJK_BRACKET_PAIRS: CjkBracketPair[] = [\n")
    for pair in grammar["cjk_bracket_pairs"]:
        lines.append(
            "  { label: "
            f"{_ts_string_literal(pair['label'])}, open: {_ts_string_literal(pair['open'])}, "
            f"close: {_ts_string_literal(pair['close'])} }},\n"
        )
    lines.append("];\n")

    return "".join(lines)


def render_grammar_kotlin(grammar: dict) -> str:
    lines = [_GRAMMAR_KT_HEADER]

    connector_words = grammar["connector_words"]
    lines.append(
        '    /** Connector words joined between two book-name words (e.g. "of" in "Song of Solomon"). */\n'
    )
    lines.append("    val CONNECTOR_WORDS: List<String> = listOf(\n")
    for word in connector_words:
        lines.append(f"        {_kt_string_literal(word)},\n")
    lines.append("    )\n\n")

    lines.append(
        "    /** Upper bound for repeated connector-word groups (ReDoS-safety bound, BITB-108/114/117). */\n"
    )
    lines.append(f"    const val CONNECTOR_REPEAT_MAX: Int = {grammar['connector_repeat_max']}\n\n")

    cv_seps = grammar["chapter_verse_separators"]
    lines.append("    /** Chapter/verse separator characters (colon, comma). */\n")
    lines.append(
        "    val CHAPTER_VERSE_SEPARATORS: List<Char> = listOf("
        + ", ".join(_kt_char_literal(s) for s in cv_seps)
        + ")\n\n"
    )

    range_seps = grammar["range_separators"]
    lines.append("    /** Verse-range separator characters (hyphen, en dash). */\n")
    lines.append(
        "    val RANGE_SEPARATORS: List<Char> = listOf("
        + ", ".join(_kt_char_literal(s) for s in range_seps)
        + ")\n\n"
    )

    lines.append(
        "    /** Non-ASCII digit range: [start, end] Unicode codepoints, with a language label. */\n"
    )
    lines.append("    data class DigitRange(val label: String, val start: Char, val end: Char)\n\n")
    lines.append(
        "    /** Non-ASCII digit ranges the chapter/verse number class must also match. */\n"
    )
    lines.append("    val NON_ASCII_DIGIT_RANGES: List<DigitRange> = listOf(\n")
    for r in grammar["non_ascii_digit_ranges"]:
        lines.append(
            f"        DigitRange({_kt_string_literal(r['label'])}, "
            f"{_kt_char_literal(r['start'])}, {_kt_char_literal(r['end'])}),\n"
        )
    lines.append("    )\n\n")

    lines.append(
        "    /** CJK/Korean bracket pair that may wrap a book name in a citation, with a label. */\n"
    )
    lines.append(
        "    data class BracketPair(val label: String, val open: Char, val close: Char)\n\n"
    )
    lines.append("    /** CJK/Korean bracket pairs that may wrap a book name in a citation. */\n")
    lines.append("    val CJK_BRACKET_PAIRS: List<BracketPair> = listOf(\n")
    for pair in grammar["cjk_bracket_pairs"]:
        lines.append(
            f"        BracketPair({_kt_string_literal(pair['label'])}, "
            f"{_kt_char_literal(pair['open'])}, {_kt_char_literal(pair['close'])}),\n"
        )
    lines.append("    )\n")

    lines.append(_GRAMMAR_KT_FOOTER)
    return "".join(lines)


def _kt_char_literal(value: str) -> str:
    if len(value) != 1:
        raise ValueError(f"expected a single Unicode codepoint, got {value!r}")
    if value in ("'", "\\"):
        raise ValueError(f"value requires escaping the generator does not support: {value!r}")
    return f"'{value}'"


# Two independent generation groups, each keyed to its own canonical JSON — the book-name
# map (BITB-059) and the verse grammar (BITB-113). Add a new (path, renderer, label) tuple
# to the relevant group for a future platform target, or a new group for a future JSON.
_BOOK_MAP_TARGETS = [
    (_KT_PATH, render_kotlin, "LocalizedBookToEnglish.kt"),
    (_TS_PATH, render_typescript, "localizedBookMap.generated.ts"),
]

_GRAMMAR_TARGETS = [
    (_GRAMMAR_KT_PATH, render_grammar_kotlin, "VerseGrammar.kt"),
    (_GRAMMAR_TS_PATH, render_grammar_typescript, "verseGrammar.generated.ts"),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify the committed generated files match their JSON; do not write anything.",
    )
    args = parser.parse_args()

    book_map = _load_book_map()
    grammar = _load_verse_grammar()

    # (path, generated content, human label, source JSON for messages)
    resolved = [
        (path, render(book_map), label, "tests/fixtures/localized_book_map.json")
        for path, render, label in _BOOK_MAP_TARGETS
    ] + [
        (path, render(grammar), label, "tests/fixtures/verse_grammar.json")
        for path, render, label in _GRAMMAR_TARGETS
    ]

    if args.check:
        failed = False
        for path, generated, label, source in resolved:
            current = path.read_text(encoding="utf-8") if path.exists() else ""
            if current != generated:
                failed = True
                diff = difflib.unified_diff(
                    current.splitlines(keepends=True),
                    generated.splitlines(keepends=True),
                    fromfile=str(path.relative_to(_REPO_ROOT)),
                    tofile="generated",
                )
                print(
                    f"FAIL: {label} is out of sync with {source}.\n"
                    "Run `python scripts/generate_localized_book_map.py` and commit the result.\n",
                    file=sys.stderr,
                )
                sys.stderr.writelines(diff)
            else:
                print(f"OK: {label} matches {source}.")
        return 1 if failed else 0

    for path, generated, label, source in resolved:
        path.write_text(generated, encoding="utf-8")
        print(f"Wrote {label} from {source}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
