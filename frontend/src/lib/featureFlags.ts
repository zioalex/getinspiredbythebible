/** Whether the web client renders verse links from the server's authoritative
 * `citations` spans (BITB-109) instead of always re-detecting them with the
 * client-side regex. A build-time kill switch, same pattern as
 * NEXT_PUBLIC_API_URL — flip in the environment, no backend coordination
 * needed since the backend already sends `citations` unconditionally and
 * additively (older/flag-off clients simply ignore the field). */
export function citationSpansEnabled(): boolean {
  return process.env.NEXT_PUBLIC_CITATION_SPANS_ENABLED === "true";
}
