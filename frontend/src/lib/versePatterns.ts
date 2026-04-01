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
    multiWordNames = Object.keys(LOCALIZED_BOOK_TO_ENGLISH).filter(
      (key) => key.includes(" ") && !isNumberPrefixed(key),
    );

    // Sort longest-first so that longer alternates (e.g. "деяния апостолов")
    // are tried before shorter ones (e.g. "деяния") — prevents partial matches.
    multiWordNames.sort((a, b) => b.length - a.length);
  }

  _cachedMultiWordAlternation = multiWordNames.map(escapeForRegex).join("|");
  return _cachedMultiWordAlternation;
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
 *  4. Chinese/CJK single-token books (耶利米哀歌, 创世记…)
 *  5. Any single Unicode word ≥2 chars (covers all remaining single-word books)
 *
 * The Unicode-aware lookbehind (?<!\p{L}) prevents matching mid-word.
 */
function buildPatternSource(): string {
  if (_cachedPatternSource !== null) {
    return _cachedPatternSource;
  }

  const multiWordAlt = getMultiWordAlternation();
  const multiWordPart = multiWordAlt ? `${multiWordAlt}|` : "";

  // [\p{L}\p{M}]  — letter + combining mark (handles Devanagari, Arabic, Hebrew, etc.)
  // [\p{Script=Han}]  — CJK ideographs (Chinese, Japanese Kanji)
  // Connector words: Western (of, dei, des, der, van, de, af, dos, da, del)
  //                  + Hindi (के/ke) + Arabic (ال as a standalone word)
  _cachedPatternSource =
    `(?<!\\p{L})(${multiWordPart}` +
    `[\\p{L}\\p{M}]{2,}(?:\\s+(?:of|dei|des|der|van|de|af|dos|da|del|के|ال)\\s+[\\p{L}\\p{M}]+)+` +
    `|\\d+(?:\\.|-[\\p{L}\\p{M}]{1,2})?\\s*[\\p{L}\\p{M}]{2,}(?:\\s+[\\p{L}\\p{M}]+)*` +
    `|[\\p{Script=Han}]{2,}` +
    `|[\\p{L}\\p{M}]{2,})\\s+(\\d+):(\\d+)(?:-\\d+)?`;

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
  _cachedPatternSource = null;
}
