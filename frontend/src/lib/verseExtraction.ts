/**
 * Extracts verse references from text
 * Matches formats like: "John 3:16", "1 John 2:3", "Song of Solomon 1:1", etc.
 * Also supports localized formats: "Giovanni 3:16" (Italian), "1. Mose 1:1" (German),
 * "Плач Иеремии 3:3" (Russian), "耶利米哀歌 3:3" (Chinese), "예레미야 애가 3:3" (Korean).
 */
export function extractVerseReferences(text: string): Set<string> {
  // Pattern to match verse references in multiple languages.
  //
  // Alternatives (tried in order):
  //  1. Explicit multi-word non-English book names that have no connector word
  //     (Russian: Плач Иеремии, Песня Песней; Korean: 예레미야 애가; Arabic: مراثي إرميا)
  //  2. Multi-word books joined by a connector word (Song of Solomon, Cantico dei Cantici…)
  //  3. Numbered-prefix books (1 John, 2 Kings, 1. Mose, 2. Könige…)
  //  4. Chinese/CJK single-token books (耶利米哀歌, 创世记…)
  //  5. Any single Unicode word >=2 chars (covers all remaining single-word book names)
  //
  // The Unicode-aware lookbehind (?<!\p{L}) prevents matching mid-word.
  // Enumerating multi-word non-Latin names (alternatives 1) is necessary because a
  // purely greedy pattern cannot distinguish "Читайте Бытие" (sentence + book) from
  // "Плач Иеремии" (two-word book name) without a known-word list.
  const versePattern =
    /(?<!\p{L})(Плач\s+Иеремии|Песня\s+Песней|예레미야\s+애가|مراثي\s+إرميا|[\p{L}]{2,}(?:\s+(?:of|dei|des|der|van|de|af)\s+[\p{L}]+)+|\d+\.?\s*[\p{L}]{2,}(?:\s+[\p{L}]+)?|[\p{Script=Han}]+|[\p{L}]{2,})\s+(\d+):(\d+)(?:-\d+)?/gu;

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
