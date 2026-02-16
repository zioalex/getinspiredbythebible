/**
 * Extracts verse references from text
 * Matches formats like: "John 3:16", "1 John 2:3", "Song of Solomon 1:1", etc.
 * Also supports localized formats: "Giovanni 3:16" (Italian), "1. Mose 1:1" (German)
 */
export function extractVerseReferences(text: string): Set<string> {
  // Pattern to match verse references in multiple languages
  // Supports:
  // - English: "John 3:16", "1 John 2:3", "Song of Solomon 1:1"
  // - Italian: "Giovanni 3:16", "Salmi 23:1"
  // - German: "1. Mose 1:1", "Römer 8:28", "Johannes 3:16"
  // Uses Unicode letter classes to match accented characters
  const versePattern =
    /(?<![A-Za-zÀ-ÿ])((?:\d+\.?\s+[\p{L}][\p{L}]*(?:\s+[\p{L}][\p{L}]*)?|[\p{L}][\p{L}]*(?:\s+(?:of|dei|des|der)\s+[\p{L}][\p{L}]*)+|[\p{L}][\p{L}]*))\s+(\d+):(\d+)(?:-\d+)?/gu;

  const references = new Set<string>();
  const matches = Array.from(text.matchAll(versePattern));

  for (const match of matches) {
    const book = match[1].trim();
    const chapter = match[2];
    const verse = match[3];
    // Store in a normalized format for matching
    references.add(`${book.toLowerCase()} ${chapter}:${verse}`);
  }

  return references;
}

/**
 * Checks if a verse matches any of the given references
 * Handles fuzzy matching for book names (e.g., "Psalm" vs "Psalms")
 */
export function isVerseReferenced(
  verse: { book: string; chapter: number; verse: number; reference: string },
  references: Set<string>,
): boolean {
  // Normalize the verse reference for comparison
  const normalizedRef = verse.reference.toLowerCase();

  // Check if this verse's reference is mentioned
  if (references.has(normalizedRef)) {
    return true;
  }

  // Also check using book/chapter/verse fields for more accurate matching
  const altRef = `${verse.book.toLowerCase()} ${verse.chapter}:${verse.verse}`;
  if (references.has(altRef)) {
    return true;
  }

  // Check if any referenced verse matches this one (partial match)
  for (const ref of Array.from(references)) {
    // Check if references are similar (handles "Psalm" vs "Psalms", etc.)
    const refParts = ref.match(/(.+)\s+(\d+):(\d+)/);
    if (refParts) {
      const refBook = refParts[1].toLowerCase();
      const refChapter = refParts[2];
      const refVerse = refParts[3];

      // Fuzzy book name matching
      const verseBook = verse.book.toLowerCase();
      const bookMatches =
        verseBook === refBook ||
        verseBook.startsWith(refBook) ||
        refBook.startsWith(verseBook) ||
        verseBook.replace(/s$/, "") === refBook.replace(/s$/, ""); // Handle Psalm/Psalms

      if (
        bookMatches &&
        verse.chapter === parseInt(refChapter) &&
        verse.verse === parseInt(refVerse)
      ) {
        return true;
      }
    }
  }

  return false;
}
