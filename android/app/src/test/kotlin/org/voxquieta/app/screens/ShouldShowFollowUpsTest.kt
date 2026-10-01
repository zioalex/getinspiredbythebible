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
 */
class ShouldShowFollowUpsTest {

    // Baseline "all conditions satisfied" arguments — each test below flips
    // exactly one of them to false and asserts the result flips to false too.
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
            ),
        )
    }
}
