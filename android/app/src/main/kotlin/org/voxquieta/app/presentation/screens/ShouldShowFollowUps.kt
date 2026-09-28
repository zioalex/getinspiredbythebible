package org.voxquieta.app.presentation.screens

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
 */
internal fun shouldShowFollowUps(
    index: Int,
    lastIndex: Int,
    role: Message.Role,
    isLoading: Boolean,
    isSessionLimitReached: Boolean,
    followUps: List<String>,
): Boolean = index == lastIndex &&
    role == Message.Role.ASSISTANT &&
    !isLoading &&
    !isSessionLimitReached &&
    followUps.isNotEmpty()
