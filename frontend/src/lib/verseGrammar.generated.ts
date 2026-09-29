/**
 * Literal separator/range/connector grammar fragments shared by the verse-reference
 * parsers (BITB-113).
 *
 * Canonical source: tests/fixtures/verse_grammar.json. The Android copy
 * (android/.../utils/VerseGrammar.kt) is generated from the same file. The backend
 * (api/utils/verse_parser.py) is a separate master for its own separator/range characters,
 * held contradiction-free by api/tests/test_verse_grammar_parity.py — Python has no
 * compositional connector-word grammar to unify (see that test's docstring) and its `\d`
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

export const CONNECTOR_WORDS: string[] = [
  "of",
  "dei",
  "des",
  "der",
  "van",
  "de",
  "af",
  "dos",
  "da",
  "del",
  "के",
  "ال",
];

export const CONNECTOR_REPEAT_MAX = 3;

export const CHAPTER_VERSE_SEPARATORS: string[] = [":", ","];

export const RANGE_SEPARATORS: string[] = ["-", "–"];

export interface NonAsciiDigitRange {
  label: string;
  start: string;
  end: string;
}

export const NON_ASCII_DIGIT_RANGES: NonAsciiDigitRange[] = [
  { label: "Devanagari (Hindi)", start: "०", end: "९" },
  { label: "Eastern Arabic-Indic", start: "٠", end: "٩" },
];

export interface CjkBracketPair {
  label: string;
  open: string;
  close: string;
}

export const CJK_BRACKET_PAIRS: CjkBracketPair[] = [
  { label: "Chinese guillemets", open: "《", close: "》" },
  { label: "Korean corner brackets", open: "「", close: "」" },
  { label: "Korean white corner brackets", open: "『", close: "』" },
];
