/**
 * Consumer for the backend's authoritative `citations` spans (BITB-086),
 * with the regex linkifier (`linkifyVerses`) kept as the per-gap fallback.
 *
 * Design: `citations` is trusted for the text it actually covers, but it is
 * never assumed exhaustive (a11y for the documented vocalized-Arabic gap —
 * see BITB-086/BITB-109) and never assumed correct (offsets are
 * self-verified against `text`, with an `occurrence`-based recovery path).
 * Any stretch of the message a valid span doesn't claim — including the
 * entire message when `citations` is `[]`, and anything after a dropped
 * span — is run back through the regex path exactly as before. This is
 * what makes an empty `citations` array degrade to the pre-existing
 * behaviour instead of suppressing it.
 */

import {
  linkifyVerses,
  VERSE_SCHEME,
  PROTECTED_REGION_SOURCE,
} from "./linkifyVerses";

export interface CitationSpan {
  text: string;
  start: number;
  end: number;
  occurrence: number;
  book: string;
  chapter: number;
  verse: number;
  verse_end?: number | null;
}

interface ResolvedSpan {
  start: number;
  end: number;
  span: CitationSpan;
}

function overlapsAny(
  start: number,
  end: number,
  ranges: Array<[number, number]>,
): boolean {
  return ranges.some(([rs, re]) => start < re && end > rs);
}

function computeProtectedRanges(markdown: string): Array<[number, number]> {
  const regions = new RegExp(PROTECTED_REGION_SOURCE, "g");
  const ranges: Array<[number, number]> = [];
  let region: RegExpExecArray | null;
  while ((region = regions.exec(markdown)) !== null) {
    ranges.push([region.index, region.index + region[0].length]);
    // Guard against a zero-length match (shouldn't happen with these patterns).
    if (regions.lastIndex === region.index) regions.lastIndex++;
  }
  return ranges;
}

/**
 * Validate one span against `markdown`, recovering via its `occurrence`
 * index when the offsets don't self-verify. Mirrors the backend's own
 * occurrence counting (`extract_citation_spans`): protected-region matches
 * are never counted and never returned, so a client search stays in sync
 * with what the server counted.
 */
function resolveSpan(
  markdown: string,
  span: CitationSpan,
  protectedRanges: Array<[number, number]>,
): ResolvedSpan | null {
  if (!span.text) return null;

  const { start, end } = span;
  if (
    Number.isInteger(start) &&
    Number.isInteger(end) &&
    start >= 0 &&
    end >= start &&
    end <= markdown.length &&
    markdown.slice(start, end) === span.text &&
    !overlapsAny(start, end, protectedRanges)
  ) {
    return { start, end, span };
  }

  let fromIndex = 0;
  let seen = 0;
  for (;;) {
    const idx = markdown.indexOf(span.text, fromIndex);
    if (idx === -1) return null;
    const idxEnd = idx + span.text.length;
    if (!overlapsAny(idx, idxEnd, protectedRanges)) {
      if (seen === span.occurrence) return { start: idx, end: idxEnd, span };
      seen++;
    }
    fromIndex = idx + 1;
  }
}

/**
 * Render `markdown` to verse-linked markdown, preferring the server's
 * `citations` spans and falling back to the regex linkifier for anything
 * they don't (validly) cover.
 *
 * `citations === undefined` means the field is absent entirely (older
 * cached responses, or the flag off) — that's the one case where the
 * regex path runs over the whole message unchanged.
 */
export function linkifyWithCitations(
  markdown: string,
  citations: CitationSpan[] | undefined,
): string {
  if (citations === undefined) return linkifyVerses(markdown);

  const protectedRanges = computeProtectedRanges(markdown);

  const resolved = citations
    .map((span) => resolveSpan(markdown, span, protectedRanges))
    .filter((r): r is ResolvedSpan => r !== null)
    .sort((a, b) => a.start - b.start || a.end - b.end);

  const kept: ResolvedSpan[] = [];
  let cursor = 0;
  for (const r of resolved) {
    if (r.start >= cursor) {
      kept.push(r);
      cursor = r.end;
    }
  }

  let out = "";
  let lastIndex = 0;
  for (const r of kept) {
    out += linkifyVerses(markdown.slice(lastIndex, r.start));
    const display = markdown.slice(r.start, r.end);
    const href = `${VERSE_SCHEME}${encodeURIComponent(r.span.book)}/${r.span.chapter}/${r.span.verse}`;
    out += `[${display}](${href})`;
    lastIndex = r.end;
  }
  out += linkifyVerses(markdown.slice(lastIndex));
  return out;
}
