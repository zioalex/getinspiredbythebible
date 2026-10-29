package org.voxquieta.app.presentation.components

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import org.junit.Assert.assertEquals
import org.junit.Test
import org.voxquieta.app.domain.models.Message
import org.voxquieta.app.presentation.screens.shouldShowFollowUps
import org.voxquieta.app.testing.ComposeTestHarness

/**
 * Robolectric-backed Compose UI tests for [FollowUpChips] (BITB-149).
 *
 * Runs under the `testDebugCompose` task / `android-compose-tests.yml` lane.
 */
class FollowUpChipsComposeTest : ComposeTestHarness() {

    @Test
    fun `renders a chip for each suggestion`() {
        setContentThemed {
            FollowUpChips(
                suggestions = listOf("Question A", "Question B"),
                onSelect = {},
            )
        }

        composeRule.onNodeWithText("Question A").assertIsDisplayed()
        composeRule.onNodeWithText("Question B").assertIsDisplayed()
    }

    @Test
    fun `group content description is present when suggestions are non-empty`() {
        setContentThemed {
            FollowUpChips(
                suggestions = listOf("Question A", "Question B"),
                onSelect = {},
            )
        }

        composeRule
            .onNodeWithContentDescription("Suggested follow-up questions")
            .assertIsDisplayed()
    }

    @Test
    fun `renders nothing when suggestions are empty`() {
        setContentThemed {
            FollowUpChips(
                suggestions = emptyList(),
                onSelect = {},
            )
        }

        composeRule
            .onNodeWithContentDescription("Suggested follow-up questions")
            .assertDoesNotExist()
    }

    @Test
    fun `tapping a chip fires onSelect exactly once on the first tap`() {
        var tapped: String? = null
        var tapCount = 0

        setContentThemed {
            FollowUpChips(
                suggestions = listOf("Question A"),
                onSelect = {
                    tapped = it
                    tapCount++
                },
            )
        }

        composeRule.onNodeWithText("Question A").performClick()

        assertEquals(1, tapCount)
        assertEquals("Question A", tapped)
    }

    // ── BITB-080: default-off rollout gate (rendering through the screen predicate) ──

    @Test
    fun `no chips render when the rollout gate is off even with follow-ups present`() {
        setContentThemed {
            if (shouldShowFollowUps(
                    index = 0,
                    lastIndex = 0,
                    role = Message.Role.ASSISTANT,
                    isLoading = false,
                    isSessionLimitReached = false,
                    followUps = listOf("Question A", "Question B"),
                    enabled = false,
                )
            ) {
                FollowUpChips(
                    suggestions = listOf("Question A", "Question B"),
                    onSelect = {},
                )
            }
        }

        // Android stays dark: no chips, no empty row, no TalkBack group.
        composeRule.onNodeWithText("Question A").assertDoesNotExist()
        composeRule.onNodeWithText("Question B").assertDoesNotExist()
        composeRule
            .onNodeWithContentDescription("Suggested follow-up questions")
            .assertDoesNotExist()
    }

    @Test
    fun `chips render with TalkBack group label when the gate flips on`() {
        setContentThemed {
            if (shouldShowFollowUps(
                    index = 0,
                    lastIndex = 0,
                    role = Message.Role.ASSISTANT,
                    isLoading = false,
                    isSessionLimitReached = false,
                    followUps = listOf("Question A"),
                    enabled = true,
                )
            ) {
                FollowUpChips(
                    suggestions = listOf("Question A"),
                    onSelect = {},
                )
            }
        }

        composeRule.onNodeWithText("Question A").assertIsDisplayed()
        composeRule
            .onNodeWithContentDescription("Suggested follow-up questions")
            .assertIsDisplayed()
    }
}
