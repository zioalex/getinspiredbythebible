/**
 * BITB-320: helpers for recovering a chat turn whose stream ended without a
 * `completion` event.
 */

// Shared trailer rule (same on backend `_UNTERMINATED_TRAILER` and Android `stripAnswerTrailer`):
// (a) remove complete `<!-- VERSES|FOLLOWUPS: ... -->` comments; (b) remove an unterminated
// `<!--...` tail to the end of the text whatever follows the opener; (c) remove a dangling
// `<!-`, `<!` or `<` at the very end; then right-trim.
const COMPLETE_TRAILER_RE =
  /<!--\s*(?:VERSES|FOLLOWUPS)\s*:(?:(?!-->)[\s\S])*-->/gi;
const UNTERMINATED_TRAILER_RE = /\s*(?:<!--(?:(?!-->)[\s\S])*|<(?:!-?)?)$/;

/** Remove any `<!-- VERSES/FOLLOWUPS: ... -->` trailer (or a cut-off one) so it never renders. */
export function stripTrailer(text: string): string {
  return text
    .replace(COMPLETE_TRAILER_RE, "")
    .replace(UNTERMINATED_TRAILER_RE, "")
    .trimEnd();
}

/** Delay before the single silent finalize retry. */
export const FINALIZE_RETRY_DELAY_MS = 1500;

/** Longest assistant_text the finalize endpoint accepts. */
export const MAX_FINALIZE_ASSISTANT_CHARS = 8000;
