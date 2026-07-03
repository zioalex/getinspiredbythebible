/**
 * String-level verse linkifier — the web analog of the Android
 * `injectVerseLinks` (ChatMessageItem.kt).
 *
 * The web used to highlight verses via per-element React-Markdown renderers,
 * which only ran inside the `p` renderer's string children.  References inside
 * list items (and headings, table cells, …) were therefore never linked.  This
 * rewrites every reference in the raw markdown into a `verse://` link *before*
 * rendering, so a single `a` renderer can make them clickable no matter where
 * they appear — the same general approach Android uses.
 *
 * The shared verse pattern + `isKnownBook` allowlist (with the rewind-on-reject
 * behaviour) are reused, so comma separators and greedy-over-match handling come
 * for free.
 */

import { createVersePatternGlobal } from "./versePatterns";
import { isKnownBook } from "./verseExtraction";

/** URL scheme used for in-app verse links (mirrors Android's `verse://`). */
export const VERSE_SCHEME = "verse://";

/**
 * Regions copied verbatim — never linkified — so we respect markdown structure:
 *   - fenced code blocks  ```…```
 *   - inline code         `…`
 *   - HTML comments       <!-- … -->   (the `VERSES:` citation marker)
 *   - existing links      [text](url)
 * Fenced code is listed before inline code so a ``` fence wins over a single `.
 */
const PROTECTED_REGION_SOURCE =
  "```[\\s\\S]*?```|`[^`]*`|<!--[\\s\\S]*?-->|\\[[^\\]]*\\]\\([^)]*\\)";

/**
 * Parse a `verse://<book>/<chapter>/<verse>` href back into its parts.
 * Returns null for any other href (external links, etc.).
 */
export function parseVerseHref(
  href: string | undefined,
): { book: string; chapter: number; verse: number } | null {
  if (!href || !href.startsWith(VERSE_SCHEME)) return null;
  const parts = href.slice(VERSE_SCHEME.length).split("/");
  if (parts.length < 3) return null;
  let book: string;
  try {
    book = decodeURIComponent(parts[0]);
  } catch {
    return null;
  }
  const chapter = parseInt(parts[1], 10);
  const verse = parseInt(parts[2], 10);
  if (!book.trim() || Number.isNaN(chapter) || Number.isNaN(verse)) return null;
  return { book: book.trim(), chapter, verse };
}

/**
 * Wrap every recognised verse reference in a plain (unprotected) markdown
 * segment as a `verse://` link, keeping the original display text.
 */
function linkifyPlainSegment(text: string): string {
  const pattern = createVersePatternGlobal();

  let out = "";
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(text)) !== null) {
    const book = match[1].trim();

    // Reject non-books and rewind so a valid reference hidden inside a greedy
    // over-match ("you of Psalm 56:9") is still recovered.  Mirrors
    // extractVerseReferences()/highlightText().
    if (!isKnownBook(book)) {
      pattern.lastIndex = match.index + 1;
      continue;
    }

    const chapter = match[2];
    const verse = match[3];
    // Keep the reference exactly as written for the display text (e.g. the
    // German "13,1-2"), but encode a canonical target in the href.
    const href = `${VERSE_SCHEME}${encodeURIComponent(book)}/${chapter}/${verse}`;
    out += text.slice(lastIndex, match.index);
    out += `[${match[0]}](${href})`;
    lastIndex = match.index + match[0].length;
  }

  out += text.slice(lastIndex);
  return out;
}

/**
 * Rewrite recognised verse references in `markdown` as `verse://` links,
 * leaving code, HTML comments, and existing links untouched.
 */
export function linkifyVerses(markdown: string): string {
  const regions = new RegExp(PROTECTED_REGION_SOURCE, "g");

  let out = "";
  let lastIndex = 0;
  let region: RegExpExecArray | null;

  while ((region = regions.exec(markdown)) !== null) {
    // Linkify the plain gap before this protected region …
    out += linkifyPlainSegment(markdown.slice(lastIndex, region.index));
    // … then copy the protected region verbatim.
    out += region[0];
    lastIndex = region.index + region[0].length;
    // Guard against a zero-length match (shouldn't happen with these patterns).
    if (regions.lastIndex === region.index) regions.lastIndex++;
  }

  out += linkifyPlainSegment(markdown.slice(lastIndex));
  return out;
}
