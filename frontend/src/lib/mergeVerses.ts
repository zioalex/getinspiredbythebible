import type { Verse } from "./api";

/**
 * Normalize a verse reference for dedup comparison: lowercase, trimmed, with
 * internal whitespace collapsed. Intentionally lightweight — this only keys
 * dedup between the pool and backend-resolved citations, both of which use the
 * same canonical "Book chapter:verse" form from the server.
 */
function normalizeRef(reference: string): string {
  return reference.toLowerCase().trim().replace(/\s+/g, " ");
}

/**
 * Merge backend-resolved cited verses into the semantic-search verse pool.
 *
 * The "Cited" tab is the intersection of the verse pool with the verses the
 * answer actually cited. On follow-up questions the cited verses are often
 * absent from the (query-driven) pool, so the backend now resolves them and
 * sends them as `resolved_verses`. Merging them into the pool lets the existing
 * intersection filter surface them without any change to the filter itself.
 *
 * Dedupes by normalized reference, preferring the existing pool entry (which
 * may carry a richer score) and preserving pool order; extras are appended.
 */
export function mergeVerses(pool: Verse[], extra?: Verse[]): Verse[] {
  if (!extra || extra.length === 0) {
    return pool;
  }

  const seen = new Set(pool.map((verse) => normalizeRef(verse.reference)));
  const merged = [...pool];

  for (const verse of extra) {
    const key = normalizeRef(verse.reference);
    if (!seen.has(key)) {
      seen.add(key);
      merged.push(verse);
    }
  }

  return merged;
}
