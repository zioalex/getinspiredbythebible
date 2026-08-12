/**
 * Extracts verse references from text
 * Matches formats like: "John 3:16", "1 John 2:3", "Song of Solomon 1:1", etc.
 * Also supports localized formats: "Giovanni 3:16" (Italian), "1. Mose 1:1" (German),
 * "Плач Иеремии 3:3" (Russian), "耶利米哀歌 3:3" (Chinese), "예레미야 애가 3:3" (Korean),
 * "يوحنا 3:16" (Arabic), "यूहन्ना 3:16" (Hindi), "João 3:16" (Portuguese).
 *
 * All 11 languages are bundled in LOCALIZED_BOOK_TO_ENGLISH (generated — see
 * localizedBookMap.generated.ts) so verse links work immediately. The backend API via
 * updateBookNames() may add extra aliases at runtime.
 */

import { createVersePatternGlobal as _createVersePatternGlobal } from "./versePatterns";
import { LOCALIZED_BOOK_TO_ENGLISH } from "./localizedBookMap.generated";

export { LOCALIZED_BOOK_TO_ENGLISH };

/**
 * Merge API-provided book name mappings into LOCALIZED_BOOK_TO_ENGLISH.
 * Called once after fetching /api/v1/scripture/book-names.
 * New entries are lowercased to match the existing convention.
 */
export function updateBookNames(apiData: Record<string, string>): void {
  for (const [localized, english] of Object.entries(apiData)) {
    const key = localized.toLowerCase();
    if (!(key in LOCALIZED_BOOK_TO_ENGLISH)) {
      LOCALIZED_BOOK_TO_ENGLISH[key] = english.toLowerCase();
    }
  }
  // The set of valid book names changed — drop the cache so isKnownBook()
  // rebuilds it (including any newly added API-provided aliases).
  _cachedKnownBooks = null;
}

// ---------------------------------------------------------------------------
// Known-book allowlist
// ---------------------------------------------------------------------------

// Lazily-built set of every recognised book name (lowercased).  Populated on
// first call to isKnownBook() and invalidated by updateBookNames().
let _cachedKnownBooks: Set<string> | null = null;

/**
 * Returns the set of all recognised book names (lowercased).
 *
 * The set is the union of:
 *   - every KEY of LOCALIZED_BOOK_TO_ENGLISH   (all localized names, e.g.
 *     "hiob", "5. mose", "약한복음", "1 царств"), and
 *   - every VALUE of LOCALIZED_BOOK_TO_ENGLISH (the 66 English canonical
 *     names, e.g. "job", "genesis", "1 samuel", "song of solomon").
 *
 * Including the English values means plain English references ("John 3:16")
 * are recognised even though English book names are not stored as keys.
 */
function getKnownBooks(): Set<string> {
  if (_cachedKnownBooks !== null) {
    return _cachedKnownBooks;
  }
  const known = new Set<string>();
  for (const [localized, english] of Object.entries(
    LOCALIZED_BOOK_TO_ENGLISH,
  )) {
    known.add(localized.toLowerCase());
    known.add(english.toLowerCase());
  }
  _cachedKnownBooks = known;
  return known;
}

/**
 * Returns true when `book` is a real Bible book name in any supported language.
 *
 * Used to validate the book portion of a regex match before treating it as a
 * verse reference.  The verse regex deliberately accepts any "Word digit:digit"
 * shape (to stay language-agnostic), so this allowlist is what prevents prose
 * like "Trost der Hoffnung 5:5", clock times like "um 14:30", and greedy
 * over-matches from being marked as verses.
 */
export function isKnownBook(book: string): boolean {
  return getKnownBooks().has(book.trim().toLowerCase());
}

/**
 * Normalize a book name to its lowercase English canonical form.
 * If the name is already English (or another Western language handled by
 * fuzzy matching), it is returned as-is (lowercased).
 */
function normalizeBookName(book: string): string {
  const lower = book.toLowerCase();
  return LOCALIZED_BOOK_TO_ENGLISH[lower] ?? lower;
}

/**
 * Extracts verse references from text, normalizing all book names to their
 * lowercase English canonical form so that `isVerseReferenced` can match
 * them against the English `verse.reference` returned by the backend.
 *
 * Supported formats:
 * - English:  "John 3:16", "1 John 2:3", "Song of Solomon 1:1"
 * - Italian:  "Giovanni 3:16", "Salmi 23:1"
 * - German:   "1. Mose 1:1", "Römer 8:28", "Johannes 3:16"
 * - Russian:  "Иоанна 3:16", "Псалтири 23:1", "Бытия 1:1", "Плач Иеремии 3:3"
 * - Chinese:  "约翰福音 3:16", "诗篇 23:1", "耶利米哀歌 3:3"
 * - Korean:   "요한복음 3:16", "시편 23:1", "예레미야 애가 3:3"
 */
/**
 * Normalize Devanagari digits (०-९, U+0966-U+096F) to ASCII digits (0-9).
 * Returns the string unchanged if no Devanagari digits are present.
 */
function normalizeDevanagariDigits(s: string): string {
  return s.replace(/[\u0966-\u096F]/g, (ch) =>
    String(ch.charCodeAt(0) - 0x0966),
  );
}

/**
 * Normalize Eastern Arabic digits (٠-٩, U+0660-U+0669) to ASCII digits (0-9).
 */
function normalizeEasternArabicDigits(s: string): string {
  return s.replace(/[\u0660-\u0669]/g, (ch) =>
    String(ch.charCodeAt(0) - 0x0660),
  );
}

/**
 * Normalize non-ASCII digit systems to ASCII.
 * Handles Devanagari (०-९) and Eastern Arabic (٠-٩) numerals.
 */
export function normalizeDigits(s: string): string {
  return normalizeEasternArabicDigits(normalizeDevanagariDigits(s));
}

/**
 * Strip Arabic tashkeel (diacritics U+064B–U+065F, U+0670) and tatweel
 * (kashida U+0640) from text so that vowelised forms like يُوحَنَّا
 * match the canonical يوحنا in the lookup table.
 *
 * Also normalizes French guillemets «» (U+00AB/U+00BB) to CJK guillemets
 * 《》 (U+300A/U+300B) so the existing bracket handling covers Arabic «…».
 */
function normalizeArabicText(text: string): string {
  return text
    .replace(/[\u064B-\u065F\u0670\u0640]/g, "")
    .replace(/\u00AB/g, "\u300A")
    .replace(/\u00BB/g, "\u300B");
}

export function extractVerseReferences(text: string): Set<string> {
  // Preprocess: strip Arabic tashkeel/tatweel and normalize guillemets.
  text = normalizeArabicText(text);

  // Use the shared verse pattern (auto-generated from LOCALIZED_BOOK_TO_ENGLISH).
  // Imported from versePatterns — the circular reference is safe because
  // versePatterns only accesses LOCALIZED_BOOK_TO_ENGLISH at module init time,
  // which completes before extractVerseReferences is ever called.
  const versePattern = _createVersePatternGlobal();

  const references = new Set<string>();

  // Iterate with exec() (not matchAll) so we can rewind the scanner on a
  // rejected match — see the isKnownBook branch below.
  let match: RegExpExecArray | null;
  while ((match = versePattern.exec(text)) !== null) {
    const book = match[1].trim();

    // Skip anything whose "book" is not a real Bible book in any supported
    // language.  This rejects conjunctions ("e 51:17", "und 3:16"), prose that
    // happens to contain numbers ("Trost der Hoffnung 5:5"), clock times
    // ("um 14:30") and greedy over-matches — none of which are verses.
    //
    // Rewind on rejection: a greedy alternative can swallow the words *before*
    // a real reference (e.g. "you of Psalm 56:9" → book "you of Psalm"), so a
    // rejected match may still hide a valid reference inside it.  Reset the
    // scanner to one character past the start of the rejected match so the
    // embedded reference ("Psalm 56:9") is still extracted.  `lastIndex` only
    // ever advances, so this cannot loop forever.
    if (!isKnownBook(book)) {
      versePattern.lastIndex = match.index + 1;
      continue;
    }

    // Normalize Devanagari (३→3) and Eastern Arabic (٣→3) digits
    const chapter = normalizeDigits(match[2]);
    const verse = normalizeDigits(match[3]);
    // Range end (e.g. the "18" in "3:16-18"), if present — see versePatterns.ts
    // group 4. isVerseReferenced() parses this suffix to test every verse in
    // [start, end], so omitting it here would silently drop range verses
    // after the first from citation matching.
    const verseEnd = match[4] ? normalizeDigits(match[4]) : null;

    // Normalize the book name to English before storing, so that
    // isVerseReferenced() can match against English verse.reference values.
    const normalizedBook = normalizeBookName(book);
    const reference = verseEnd
      ? `${normalizedBook} ${chapter}:${verse}-${verseEnd}`
      : `${normalizedBook} ${chapter}:${verse}`;
    references.add(reference);
  }

  return references;
}

/**
 * Checks if a verse matches any of the given references
 * Handles fuzzy matching for book names (e.g., "Psalm" vs "Psalms")
 * Also handles non-Latin book names (Hindi, Korean, Arabic, Chinese, Russian)
 * by normalizing them to their lowercase English canonical form before lookup.
 */
export function isVerseReferenced(
  verse: { book: string; chapter: number; verse: number; reference?: string },
  references: Set<string>,
): boolean {
  // Normalize the verse reference for comparison (handle undefined)
  const normalizedRef = verse.reference?.toLowerCase();

  // Check if this verse's reference is mentioned (only if reference exists)
  if (normalizedRef && references.has(normalizedRef)) {
    return true;
  }

  // Also check using book/chapter/verse fields for more accurate matching.
  // Normalize the book name to English so that non-Latin scripts (Hindi,
  // Korean, Arabic, Chinese, Russian) resolve to the same English key that
  // the backend puts in the `references` Set (e.g. "Philippians 4:7").
  const normalizedBook = normalizeBookName(verse.book);
  const altRef = `${normalizedBook} ${verse.chapter}:${verse.verse}`;
  if (references.has(altRef)) {
    return true;
  }

  // Check if any referenced verse matches this one (partial match)
  for (const ref of Array.from(references)) {
    // Check if references are similar (handles "Psalm" vs "Psalms", etc.)
    // The optional trailing group captures the END of a verse range, since the
    // backend emits cited ranges as "John 3:16-18" (hyphen) or "Psalms 23:1–6"
    // (en-dash). Every verse within [start, end] must count as referenced.
    const refParts = ref.match(/(.+)\s+(\d+):(\d+)(?:\s*[-–]\s*(\d+))?/);
    if (refParts) {
      const refBook = refParts[1].toLowerCase();
      const refChapter = parseInt(refParts[2], 10);
      const refVerseStart = parseInt(refParts[3], 10);
      const refVerseEnd = refParts[4]
        ? parseInt(refParts[4], 10)
        : refVerseStart;

      // Fuzzy book name matching — use the already-normalized English form so
      // non-Latin scripts are compared on equal footing.
      const verseBook = normalizedBook;
      const bookMatches =
        verseBook === refBook ||
        verseBook.startsWith(refBook) ||
        refBook.startsWith(verseBook) ||
        verseBook.replace(/s$/, "") === refBook.replace(/s$/, ""); // Handle Psalm/Psalms

      if (
        bookMatches &&
        verse.chapter === refChapter &&
        verse.verse >= refVerseStart &&
        verse.verse <= refVerseEnd
      ) {
        return true;
      }
    }
  }

  return false;
}
