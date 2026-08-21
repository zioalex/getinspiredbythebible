package org.voxquieta.app.presentation.screens

/**
 * BITB-081 — what happens when the user taps a suggested prompt.
 *
 * Clears the composer, then sends. Deliberately takes **no** readiness or
 * session-limit flag: the tap must send on the very first tap, including on a
 * cold start before Turnstile has produced a token.
 *
 * Safety is handled elsewhere and does not belong here:
 * - `TurnstileInterceptor` waits (bounded) for a token, proceeds without one on
 *   timeout, and retries once on 403 after kicking the widget.
 * - `ChatViewModel.sendMessage` drops blank text and ignores a second call while
 *   a send is already in flight (`isLoading`), so a double tap cannot start two
 *   conversations.
 * - The session limit produces its own user-visible message inside `sendMessage`.
 *
 * Reuse this for the BITB-080 follow-up chips when they land.
 */
internal fun onExamplePromptTapped(
    prompt: String,
    clearInput: () -> Unit,
    sendMessage: (String) -> Unit,
) {
    clearInput()
    sendMessage(prompt)
}
