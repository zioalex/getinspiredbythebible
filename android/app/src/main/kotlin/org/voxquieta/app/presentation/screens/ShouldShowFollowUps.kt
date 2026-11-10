package org.voxquieta.app.presentation.screens

import org.voxquieta.app.BuildConfig
import org.voxquieta.app.domain.models.Message

/**
 * BITB-149 — whether the suggested follow-up question chips should render
 * beneath a given message in the Chat screen's message list.
 *
 * Pure (Compose-free) structural check so the rule is unit-testable on the
 * JVM, in line with the repository convention of placing screen-level
 * structural predicates in their own small file under
 * `app/src/test/.../screens/` (see e.g. [ChatTopBarPolicy], [onExamplePromptTapped]).
 *
 * Chips render only under the LATEST assistant message, and only when the
 * app isn't mid-response, the session hasn't hit its limit, and the backend
 * actually sent suggestions for this turn.
 *
 * [enabled] is the Android rollout gate for the parent story BITB-080
 * (the backend streams `follow_ups` to all clients; each client gates its
 * own rendering). It defaults ON via the compile-time
 * [BuildConfig.CHAT_FOLLOW_UPS_ENABLED] flag — the default flipped to true
 * in BITB-278, with `-PchatFollowUpsEnabled=false` as the per-build kill
 * switch — and mirrors the same flag the ViewModel gates state exposure
 * on, so the chips cannot render while the gate is off even if state ever
 * leaked. With the gate on, the BITB-149 contract is unchanged
 * (last-message-only, tap-to-send).
 */
internal fun shouldShowFollowUps(
    index: Int,
    lastIndex: Int,
    role: Message.Role,
    isLoading: Boolean,
    isSessionLimitReached: Boolean,
    followUps: List<String>,
    enabled: Boolean = BuildConfig.CHAT_FOLLOW_UPS_ENABLED,
): Boolean = enabled &&
    index == lastIndex &&
    role == Message.Role.ASSISTANT &&
    !isLoading &&
    !isSessionLimitReached &&
    followUps.isNotEmpty()
