/** Whether the web client renders verse links from the server's authoritative
 * `citations` spans (BITB-109) instead of always re-detecting them with the
 * client-side regex. A build-time kill switch, same pattern as
 * NEXT_PUBLIC_API_URL — flip in the environment, no backend coordination
 * needed since the backend already sends `citations` unconditionally and
 * additively (older/flag-off clients simply ignore the field). */
export function citationSpansEnabled(): boolean {
  return process.env.NEXT_PUBLIC_CITATION_SPANS_ENABLED === "true";
}

/** Whether the web client renders the BITB-080 suggested follow-up
 *  question chips. A build-time kill switch, same pattern as
 *  NEXT_PUBLIC_CITATION_SPANS_ENABLED. Off by default: the backend's
 *  `chat_follow_ups_enabled` (CHAT_FOLLOW_UPS_ENABLED) is being flipped for
 *  *all* clients first, so each client gates its own rendering -- web here,
 *  Android behind its own default-off flag. Older/flag-off clients simply
 *  ignore the additive `follow_ups` field on the completion event. */
export function followUpsEnabled(): boolean {
  return process.env.NEXT_PUBLIC_FOLLOW_UPS_ENABLED === "true";
}
