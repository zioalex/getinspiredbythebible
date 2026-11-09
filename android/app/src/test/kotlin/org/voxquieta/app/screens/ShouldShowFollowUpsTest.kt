package org.voxquieta.app.screens

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.voxquieta.app.domain.models.Message
import org.voxquieta.app.presentation.screens.shouldShowFollowUps

/**
 * Unit tests for the [shouldShowFollowUps] helper which encodes the visibility
 * rule for the BITB-149 follow-up question chips in the Chat screen's message
 * list: they render only under the LAST message, only when it's an assistant
 * message, only when the app isn't loading/session-limited, and only when the
 * backend actually sent suggestions for this turn.
 *
 * The Android rollout gate (parent story BITB-080) is covered too: with the
 * flag OFF nothing renders even when `follow_ups` arrived in the stream;
 * with the flag ON (the default since BITB-278) the existing behavior is
 * unchanged.
 */
class ShouldShowFollowUpsTest {

    // Baseline "all conditions satisfied" arguments — each test below flips
    // exactly one of them to false and asserts the result flips to false too.
    // `enabled = true` matches the default-on rollout state (BITB-278).
    private val lastIndex = 4
    private val followUps = listOf("What does this mean?", "Tell me more")

    @Test
    fun `true when last index, assistant role, not loading, not session-limited, and follow-ups present`() {
        assertTrue(
            shouldShowFollowUps(
                index = lastIndex,
                lastIndex = lastIndex,
                role = Message.Role.ASSISTANT,
                isLoading = false,
                isSessionLimitReached = false,
                followUps = followUps,
                enabled = true,
            ),
        )
    }

    @Test
    fun `false when index is not the last index`() {
        assertFalse(
            shouldShowFollowUps(
                index = lastIndex - 1,
                lastIndex = lastIndex,
                role = Message.Role.ASSISTANT,
                isLoading = false,
                isSessionLimitReached = false,
                followUps = followUps,
                enabled = true,
            ),
        )
    }

    @Test
    fun `false when role is USER`() {
        assertFalse(
            shouldShowFollowUps(
                index = lastIndex,
                lastIndex = lastIndex,
                role = Message.Role.USER,
                isLoading = false,
                isSessionLimitReached = false,
                followUps = followUps,
                enabled = true,
            ),
        )
    }

    @Test
    fun `false when isLoading is true`() {
        assertFalse(
            shouldShowFollowUps(
                index = lastIndex,
                lastIndex = lastIndex,
                role = Message.Role.ASSISTANT,
                isLoading = true,
                isSessionLimitReached = false,
                followUps = followUps,
                enabled = true,
            ),
        )
    }

    @Test
    fun `false when isSessionLimitReached is true`() {
        assertFalse(
            shouldShowFollowUps(
                index = lastIndex,
                lastIndex = lastIndex,
                role = Message.Role.ASSISTANT,
                isLoading = false,
                isSessionLimitReached = true,
                followUps = followUps,
                enabled = true,
            ),
        )
    }

    @Test
    fun `false when followUps is empty`() {
        assertFalse(
            shouldShowFollowUps(
                index = lastIndex,
                lastIndex = lastIndex,
                role = Message.Role.ASSISTANT,
                isLoading = false,
                isSessionLimitReached = false,
                followUps = emptyList(),
                enabled = true,
            ),
        )
    }

    // ── BITB-080 rollout gate ─────────────────────────────────────────────────

    @Test
    fun `false when the rollout gate is off even with follow-ups present in the stream`() {
        assertFalse(
            shouldShowFollowUps(
                index = lastIndex,
                lastIndex = lastIndex,
                role = Message.Role.ASSISTANT,
                isLoading = false,
                isSessionLimitReached = false,
                followUps = followUps,
                enabled = false,
            ),
        )
    }

    @Test
    fun `default gate mirrors the compile-time BuildConfig flag (default on)`() {
        // The default value comes from BuildConfig.CHAT_FOLLOW_UPS_ENABLED,
        // which is true since the BITB-278 rollout flip unless the build
        // passes -PchatFollowUpsEnabled=false. Unit tests run against the
        // debug BuildConfig, so the default must be ON here.
        assertTrue(
            shouldShowFollowUps(
                index = lastIndex,
                lastIndex = lastIndex,
                role = Message.Role.ASSISTANT,
                isLoading = false,
                isSessionLimitReached = false,
                followUps = followUps,
            ),
        )
    }
}
