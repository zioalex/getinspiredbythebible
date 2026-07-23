/**
 * Shared verse regex builder.
 *
 * Auto-generates multi-word book-name alternates from the known
 * LOCALIZED_BOOK_TO_ENGLISH map so that every language's multi-word books
 * are matched without manually maintaining a hand-written list.
 *
 * Exported:
 *   CONJUNCTIONS                 — Set of words that must never be treated as book names
 *   getMultiWordAlternation()    — lazy accessor for the multi-word alternation string
 *   createVersePattern()         — single-match RegExp (/u)
 *   createVersePatternGlobal()   — global RegExp (/gu) — fresh instance each call
 *                                  (JavaScript /g regex has mutable lastIndex state)
 *
 * Circular-import note:
 *   verseExtraction.ts exports LOCALIZED_BOOK_TO_ENGLISH and imports from this
 *   module.  To break the init-time circular dependency, this module accesses
 *   LOCALIZED_BOOK_TO_ENGLISH lazily (only inside the exported factory functions,
 *   never at module top-level).  The getMultiWordAlternation() helper caches the
 *   computed alternation string on first call so there is no repeated work.
 */

import { LOCALIZED_BOOK_TO_ENGLISH } from "./verseExtraction";

// ---------------------------------------------------------------------------
// CONJUNCTIONS
// ---------------------------------------------------------------------------

/** Words that look like book names but are actually conjunctions. */
export const CONJUNCTIONS = new Set(["e", "and", "und", "y", "et", "o", "a"]);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Returns true when `key` is a number-prefixed book name like "1 царств",
 * "2 samuel", "1 أخبار الأيام", etc.  These are handled by the \d+ branch
 * in the regex and must NOT appear in the multi-word alternation.
 */
function isNumberPrefixed(key: string): boolean {
  return /^\d/.test(key);
}

/**
 * Escape a string for use inside a RegExp alternation.
 * Replaces literal spaces with `\s+` so that "Плач Иеремии" matches both
 * single-space and multi-space variants (e.g. markup artefacts).
 */
function escapeForRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/ /g, "\\s+");
}

// ---------------------------------------------------------------------------
// Lazy-cached multi-word alternation
// ---------------------------------------------------------------------------

// These are populated on first call.
// They MUST NOT be initialised at module-load time because this module and
// verseExtraction.ts form a circular import pair — LOCALIZED_BOOK_TO_ENGLISH
// is undefined if accessed before verseExtraction.ts finishes loading.
let _cachedMultiWordAlternation: string | null = null;
let _cachedCjkAlternation: string | null = null;
let _cachedHangulAlternation: string | null = null;
let _cachedDevanagariAlternation: string | null = null;
let _cachedPatternSource: string | null = null;

// When non-null, server-provided multi-word names take precedence over
// the locally-derived list.  Set via updateMultiWordNames().
let _serverMultiWordNames: string[] | null = null;

/**
 * Returns the alternation string for multi-word book names (lazy, cached).
 * Exported so that the test suite can inspect it directly.
 *
 * On first call, reads LOCALIZED_BOOK_TO_ENGLISH (which is always fully
 * initialised by then, as modules are loaded before any test code runs),
 * filters out number-prefixed keys, sorts longest-first, and joins with "|".
 */
export function getMultiWordAlternation(): string {
  if (_cachedMultiWordAlternation !== null) {
    return _cachedMultiWordAlternation;
  }

  let multiWordNames: string[];

  if (_serverMultiWordNames !== null) {
    // Server-provided names are already sorted longest-first.
    multiWordNames = _serverMultiWordNames;
  } else {
    // Collect all multi-word localized book names.
    // A "multi-word" key is one that contains a space AND is NOT number-prefixed.
    // Number-prefixed Latin/Cyrillic/Arabic books (e.g. "1 samuel", "1 царств",
    // "1 أخبار الأيام") are handled by the numbered-prefix \d+ branch in the regex.
    // BUT number-prefixed Han/Hangul/Devanagari books (e.g. "1 शमूएल", "1 요한") must
    // be listed explicitly here, because the numbered-prefix branch excludes those
    // scripts to prevent greedy over-matching of surrounding non-Latin context text.
    const NON_LATIN_SCRIPT_RE =
      /[\p{Script=Han}\p{Script=Hangul}\p{Script=Devanagari}]/u;
    multiWordNames = Object.keys(LOCALIZED_BOOK_TO_ENGLISH).filter((key) => {
      if (!key.includes(" ")) return false;
      if (isNumberPrefixed(key)) return NON_LATIN_SCRIPT_RE.test(key);
      return true;
    });

    // Sort longest-first so that longer alternates (e.g. "деяния апостолов")
    // are tried before shorter ones (e.g. "деяния") — prevents partial matches.
    multiWordNames.sort((a, b) => b.length - a.length);
  }

  _cachedMultiWordAlternation = multiWordNames.map(escapeForRegex).join("|");
  return _cachedMultiWordAlternation;
}

// ---------------------------------------------------------------------------
// Lazy-cached CJK book name alternation
// ---------------------------------------------------------------------------

// Regex to test if a string is entirely CJK Han characters.
const CJK_ONLY_RE = /^[\p{Script=Han}]+$/u;

/**
 * Returns an alternation string of all known CJK (Chinese) book names from
 * LOCALIZED_BOOK_TO_ENGLISH, sorted longest-first.
 *
 * This replaces the generic `[\p{Script=Han}]{2,}` pattern which was too
 * greedy — it consumed preceding CJK context text (e.g. 请阅读约翰福音
 * instead of just 约翰福音).  An explicit alternation matches only known
 * book names and avoids this problem.
 */
function getCjkAlternation(): string {
  if (_cachedCjkAlternation !== null) {
    return _cachedCjkAlternation;
  }

  const cjkNames = Object.keys(LOCALIZED_BOOK_TO_ENGLISH).filter(
    (key) => CJK_ONLY_RE.test(key) && key.length >= 2,
  );

  // Longest first to prevent partial matches (e.g. 约翰福音 before 约翰).
  cjkNames.sort((a, b) => b.length - a.length);

  _cachedCjkAlternation = cjkNames.join("|");
  return _cachedCjkAlternation;
}

// ---------------------------------------------------------------------------
// Lazy-cached Hangul (Korean) book name alternation
// ---------------------------------------------------------------------------

// Regex to test if a string is entirely Hangul syllable characters.
const HANGUL_ONLY_RE = /^[\p{Script=Hangul}]+$/u;

/**
 * Returns an alternation string of all known Hangul (Korean) book names from
 * LOCALIZED_BOOK_TO_ENGLISH, sorted longest-first.
 *
 * Like getCjkAlternation() for Chinese, this prevents the generic
 * [\p{L}\p{M}]{2,} pattern from greedily matching surrounding Korean context
 * text.  An explicit alternation matches only known book names.
 */
function getHangulAlternation(): string {
  if (_cachedHangulAlternation !== null) {
    return _cachedHangulAlternation;
  }

  const hangulNames = Object.keys(LOCALIZED_BOOK_TO_ENGLISH).filter(
    (key) => HANGUL_ONLY_RE.test(key) && key.length >= 2,
  );

  // Longest first to prevent partial matches (e.g. 요한계시록 before 요한복음).
  hangulNames.sort((a, b) => b.length - a.length);

  _cachedHangulAlternation = hangulNames.join("|");
  return _cachedHangulAlternation;
}

// ---------------------------------------------------------------------------
// Lazy-cached Devanagari (Hindi) book name alternation
// ---------------------------------------------------------------------------

// Regex to test if a string is entirely Devanagari script (including combining marks).
const DEVANAGARI_ONLY_RE = /^[\p{Script=Devanagari}]+$/u;

/**
 * Returns an alternation string of all known Devanagari (Hindi) book names from
 * LOCALIZED_BOOK_TO_ENGLISH, sorted longest-first.
 *
 * Like CJK and Hangul alternation, this prevents the generic fallback pattern
 * from greedily matching surrounding Devanagari text.
 */
function getDevanagariAlternation(): string {
  if (_cachedDevanagariAlternation !== null) {
    return _cachedDevanagariAlternation;
  }

  const devanagariNames = Object.keys(LOCALIZED_BOOK_TO_ENGLISH).filter(
    (key) => DEVANAGARI_ONLY_RE.test(key) && key.length >= 2,
  );

  devanagariNames.sort((a, b) => b.length - a.length);

  _cachedDevanagariAlternation = devanagariNames.join("|");
  return _cachedDevanagariAlternation;
}

// ---------------------------------------------------------------------------
// Regex pattern string builder
// ---------------------------------------------------------------------------

/**
 * Full verse-reference regex pattern (without flags).
 *
 * Alternatives (tried in order):
 *  1. Multi-word localized book names auto-generated from LOCALIZED_BOOK_TO_ENGLISH
 *     (e.g. Russian: Плач Иеремии, Песня Песней; plus any names loaded via API)
 *  2. Multi-word books joined by a connector word (Song of Solomon, Cantique des Cantiques…)
 *  3. Numbered-prefix books (1 John, 2 Kings, 1. Mose, 2. Könige, 1 أخبار الأيام…)
 *     Han/Hangul/Devanagari characters are excluded from this branch — all legitimate
 *     CJK/Korean/Hindi numbered books are already covered by branches 1, 4, and 5.
 *  4. Chinese/CJK book names — explicit alternation of known names from the map.
 *     Unlike the generic [\p{Script=Han}]{2,} that was used before, an explicit
 *     alternation prevents greedy over-matching of surrounding CJK context text.
 *  5. Korean/Hangul book names — explicit alternation, same rationale as CJK.
 *  6. Any single Unicode word ≥2 chars (covers all remaining single-word books)
 *
 * Start boundary: (?:(?<!\p{L})|(?<=\p{Script=Han})|(?<=\p{Script=Hangul}))
 * allows matching after CJK/Hangul characters (which are \p{L}) while still
 * preventing mid-word matches in Latin/Cyrillic/Arabic text.
 *
 * Bracket support:
 *   - Chinese guillemets: 《 (U+300A) / 》 (U+300B)
 *   - Korean corner brackets: 「 (U+300C) / 」 (U+300D) and 『 (U+300E) / 』 (U+300F)
 *
 * Space between book name and chapter number:
 *   - After a CJK Han or Hangul character → \s* (zero or more spaces), so both
 *     约翰福音 10:28 / 요한복음 3:16 and 约翰福音10:28 / 요한복음3:16 are accepted.
 *   - After any other character → \s+ (one or more spaces required), which
 *     preserves John 3:16 behaviour and prevents false positives like John3:16.
 */
function buildPatternSource(): string {
  if (_cachedPatternSource !== null) {
    return _cachedPatternSource;
  }

  const multiWordAlt = getMultiWordAlternation();
  const multiWordPart = multiWordAlt ? `${multiWordAlt}|` : "";
  const cjkAlt = getCjkAlternation();
  const cjkPart = cjkAlt ? `${cjkAlt}|` : "";
  const hangulAlt = getHangulAlternation();
  const hangulPart = hangulAlt ? `${hangulAlt}|` : "";
  const devanagariAlt = getDevanagariAlternation();
  const devanagariPart = devanagariAlt ? `${devanagariAlt}|` : "";

  // [\p{L}\p{M}]  — letter + combining mark (handles Devanagari, Arabic, Hebrew, etc.)
  // Connector words: Western (of, dei, des, der, van, de, af, dos, da, del)
  //                  + Hindi (के/ke) + Arabic (ال as a standalone word)
  // Bracket support:
  //   Chinese guillemets: \u300A (《) / \u300B (》)
  //   Korean corner brackets: \u300C (「) / \u300D (」) / \u300E (『) / \u300F (』)
  // The lookbehind includes opening brackets so they can start a match, and the
  // closing bracket class [\u300B\u300D\u300F]? after the book-name capture group
  // makes them optional.
  //
  // Chapter:verse digits: [\d\u0966-\u096F\u0660-\u0669] supports Western,
  // Devanagari (Hindi), and Eastern Arabic numerals.
  //
  // Chapter/verse separator [:,] accepts a colon (English etc.) OR a comma \u2014
  // the convention in German/French/Italian citations ("R\u00F6mer 13,1"). This
  // mirrors the backend parser (api/utils/verse_parser.py), so in-text links
  // match exactly what the backend already recognises. The isKnownBook gate
  // keeps the comma from matching prose/decimals ("habe 3,50"). The range
  // accepts a hyphen or en-dash ([-\u2013]) and captures the end verse
  // (group 4) so callers can build a full "book ch:start-end" reference
  // instead of silently truncating a range down to its start verse.
  _cachedPatternSource =
    `(?:(?<!\\p{L})|(?<=\\p{Script=Han})|(?<=\\p{Script=Hangul})|(?<=\\p{Script=Devanagari})|(?<=[\u300A\u300C\u300E]))(${multiWordPart}` +
    `[\\p{L}\\p{M}]{2,}(?:\\s+(?:of|dei|des|der|van|de|af|dos|da|del|के|ال)\\s+[\\p{L}\\p{M}]+)+` +
    `|\\d+(?:\\.|-(?![\\p{Script=Han}\\p{Script=Hangul}\\p{Script=Devanagari}])[\\p{L}\\p{M}]{1,2})?\\s*(?:(?![\\p{Script=Han}\\p{Script=Hangul}\\p{Script=Devanagari}])[\\p{L}\\p{M}]){2,}(?:\\s+(?:(?![\\p{Script=Han}\\p{Script=Hangul}\\p{Script=Devanagari}])[\\p{L}\\p{M}])+)*` +
    `|${cjkPart}` +
    `${hangulPart}` +
    `${devanagariPart}` +
    `(?:(?![\\p{Script=Han}\\p{Script=Hangul}\\p{Script=Devanagari}])[\\p{L}\\p{M}]){2,})[\u300B\u300D\u300F]?(?:(?<=[\\p{Script=Han}])\\s*|(?<=[\\p{Script=Hangul}])\\s*|(?<=[\\p{Script=Devanagari}])\\s*|(?<=[\u300B\u300D\u300F])\\s*|\\s+)([\\d\u0966-\u096F\u0660-\u0669]+)[:,]([\\d\u0966-\u096F\u0660-\u0669]+)(?:[-\u2013]([\\d\u0966-\u096F\u0660-\u0669]+))?`;

  return _cachedPatternSource;
}

// ---------------------------------------------------------------------------
// Exported factory functions
// ---------------------------------------------------------------------------

/**
 * Returns a new single-match RegExp (flags: `u`) for detecting whether a
 * string *contains* a verse reference.  Safe to cache and reuse.
 */
export function createVersePattern(): RegExp {
  return new RegExp(buildPatternSource(), "iu");
}

/**
 * Returns a new global RegExp (flags: `gu`) for iterating over *all* verse
 * references in a string via `matchAll` or a `while` loop.
 *
 * **Always call this function to get a fresh instance** — JavaScript's `/g`
 * flag makes `lastIndex` mutable state, so reusing the same instance across
 * calls causes subtle bugs.
 */
export function createVersePatternGlobal(): RegExp {
  return new RegExp(buildPatternSource(), "giu");
}

/**
 * Accept server-provided multi-word book names and invalidate the cached regex.
 * The next call to createVersePattern() or createVersePatternGlobal() will
 * rebuild the regex using the updated data.
 */
export function updateMultiWordNames(names: string[]): void {
  // Store the server-provided names (they're already sorted longest-first)
  _serverMultiWordNames = names.map((n) => n.toLowerCase());
  // Invalidate cached regex source so it rebuilds on next use
  _cachedMultiWordAlternation = null;
  _cachedHangulAlternation = null;
  _cachedDevanagariAlternation = null;
  _cachedPatternSource = null;
}
