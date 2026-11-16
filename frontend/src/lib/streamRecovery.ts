/**
 * BITB-320: helpers for recovering a chat turn whose stream ended without a
 * `completion` event.
 */

// A complete trailer comment, or an unterminated one cut off by the dropped
// connection (runs to the end of the text).
const TRAILER_RE = /<!--\s*(?:VERSES|FOLLOWUPS)\s*:[\s\S]*?(?:-->|$)/gi;

/** Remove any `<!-- VERSES/FOLLOWUPS: ... -->` trailer so it never renders. */
export function stripTrailer(text: string): string {
  return text.replace(TRAILER_RE, "").trimEnd();
}

/** Delay before the single silent finalize retry. */
export const FINALIZE_RETRY_DELAY_MS = 1500;

/** Longest assistant_text the finalize endpoint accepts. */
export const MAX_FINALIZE_ASSISTANT_CHARS = 8000;
