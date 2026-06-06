package org.voxquieta.app.presentation.components

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Test
import org.voxquieta.app.testing.ComposeTestHarness

/**
 * Robolectric-backed tests for [FeedbackControls] state / locking behaviour.
 *
 * The pending affordance now renders in a [androidx.compose.ui.window.Popup]
 * (see [FeedbackPendingPanel]), whose content is unreliable to assert under
 * Robolectric (see `COMPOSE_TESTS.md`). So the popover *content* — Undo, the
 * maintainer notice, and the comment → Send path — is covered directly in
 * [FeedbackPendingPanelComposeTest]. These tests only assert facts that render
 * inline: the locked "Thanks" state, and that tapping the thumbs does not send
 * before the rethink window elapses.
 *
 * [autoAdvance] is disabled so the 10s timer never fires mid-test; each
 * [performClick] is followed by [settle] so the tap gesture + recomposition land.
 */
class FeedbackControlsComposeTest : ComposeTestHarness() {

    private val helpful = "This was helpful"
    private val notHelpful = "This was not helpful"

    @Before
    fun freezeClock() {
        // Keep the rethink countdown from auto-firing during waitForIdle.
        composeRule.mainClock.autoAdvance = false
    }

    /** Advance just enough for a gesture + recomposition to settle, never the 10s timer. */
    private fun settle() = composeRule.mainClock.advanceTimeBy(SETTLE_MS)

    @Test
    fun `tapping a thumb does not send immediately`() {
        var submitted: Pair<String, String>? = null
        setContentThemed {
            FeedbackControls(feedbackGiven = null, onSubmit = { r, c -> submitted = r to c })
        }

        composeRule.onNodeWithContentDescription(notHelpful).performClick()
        settle()

        assertNull("rating must not be sent before the rethink window elapses", submitted)
    }

    @Test
    fun `re-tapping the same thumb cancels and sends nothing`() {
        var submitted: Pair<String, String>? = null
        setContentThemed {
            FeedbackControls(feedbackGiven = null, onSubmit = { r, c -> submitted = r to c })
        }

        val up = composeRule.onNodeWithContentDescription(helpful)
        up.performClick()
        settle()
        up.performClick() // re-tapping the pending thumb = undo
        settle()

        assertNull("re-tapping the same thumb must cancel without sending", submitted)
    }

    @Test
    fun `given feedback shows thanks and disables the thumbs`() {
        setContentThemed {
            FeedbackControls(feedbackGiven = "positive", onSubmit = { _, _ -> })
        }

        composeRule.onNodeWithText("Thanks for your feedback!").assertIsDisplayed()
        composeRule.onNodeWithContentDescription(helpful).assertIsNotEnabled()
        composeRule.onNodeWithContentDescription(notHelpful).assertIsNotEnabled()
    }

    private companion object {
        /** Well under FEEDBACK_RETHINK_MS so the auto-commit never fires mid-test. */
        const val SETTLE_MS = 200L
    }
}
