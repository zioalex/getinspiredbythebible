package org.voxquieta.app.presentation.components

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.hasSetTextAction
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performTextInput
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.voxquieta.app.testing.ComposeTestHarness

/**
 * Robolectric-backed Compose UI tests for [FeedbackControls] (BITB-042).
 *
 * These cover the deterministic interaction surface: the pending/undo
 * affordance, the thumbs-down maintainer notice, and the inline comment →
 * Send path. The ~10s rethink timer itself is driven by coroutine [delay],
 * which the Robolectric main clock does not advance reliably, so the
 * timeout-commit timing is validated by the web unit tests and the
 * `ChatViewModel` comment-plumbing test instead. We disable [autoAdvance] so
 * the timer never fires mid-test and the assertions stay deterministic.
 *
 * With [autoAdvance] false, each [performClick] must be followed by
 * [advanceTimeByFrame] to let Compose render the resulting recomposition
 * before the next assertion runs.
 */
class FeedbackControlsComposeTest : ComposeTestHarness() {

    private val helpful = "This was helpful"
    private val notHelpful = "This was not helpful"
    private val maintainerNotice = "Your message will be shared with the app's maintainer."
    private val addComment = "Add a comment (optional)"

    @Before
    fun freezeClock() {
        // Keep the rethink countdown from auto-firing during waitForIdle.
        composeRule.mainClock.autoAdvance = false
    }

    @Test
    fun `tapping a thumb shows undo without sending immediately`() {
        var submitted: Pair<String, String>? = null
        setContentThemed {
            FeedbackControls(feedbackGiven = null, onSubmit = { r, c -> submitted = r to c })
        }

        composeRule.onNodeWithContentDescription(helpful).performClick()
        composeRule.mainClock.advanceTimeByFrame()

        composeRule.onNodeWithText("Undo").assertIsDisplayed()
        assertNull("rating must not be sent before the rethink window elapses", submitted)
    }

    @Test
    fun `thumbs-down shows the maintainer-sharing notice`() {
        setContentThemed {
            FeedbackControls(feedbackGiven = null, onSubmit = { _, _ -> })
        }

        composeRule.onNodeWithContentDescription(notHelpful).performClick()
        composeRule.mainClock.advanceTimeByFrame()

        composeRule.onNodeWithText(maintainerNotice).assertIsDisplayed()
    }

    @Test
    fun `thumbs-up does not show the maintainer notice`() {
        setContentThemed {
            FeedbackControls(feedbackGiven = null, onSubmit = { _, _ -> })
        }

        composeRule.onNodeWithContentDescription(helpful).performClick()
        composeRule.mainClock.advanceTimeByFrame()

        assertTrue(
            "maintainer notice must not appear for thumbs-up",
            composeRule.onAllNodesWithText(maintainerNotice, useUnmergedTree = false)
                .fetchSemanticsNodes(atLeastOneRootRequired = false).isEmpty(),
        )
    }

    @Test
    fun `undo cancels the pending feedback`() {
        var submitted: Pair<String, String>? = null
        setContentThemed {
            FeedbackControls(feedbackGiven = null, onSubmit = { r, c -> submitted = r to c })
        }

        composeRule.onNodeWithContentDescription(notHelpful).performClick()
        composeRule.mainClock.advanceTimeByFrame()
        composeRule.onNodeWithText(maintainerNotice).assertIsDisplayed()

        composeRule.onNodeWithText("Undo").performClick()
        composeRule.mainClock.advanceTimeByFrame()

        assertTrue(
            "maintainer notice must disappear after undo",
            composeRule.onAllNodesWithText(maintainerNotice, useUnmergedTree = false)
                .fetchSemanticsNodes(atLeastOneRootRequired = false).isEmpty(),
        )
        assertNull("undo must not send any feedback", submitted)
    }

    @Test
    fun `adding a comment and tapping Send submits rating with comment`() {
        var submitted: Pair<String, String>? = null
        setContentThemed {
            FeedbackControls(feedbackGiven = null, onSubmit = { r, c -> submitted = r to c })
        }

        composeRule.onNodeWithContentDescription(notHelpful).performClick()
        composeRule.mainClock.advanceTimeByFrame()
        composeRule.onNodeWithText(addComment).performClick()
        composeRule.mainClock.advanceTimeByFrame()
        composeRule.onNode(hasSetTextAction()).performTextInput("Off-topic verse")
        composeRule.onNodeWithText("Send").performClick()

        assertEquals("negative" to "Off-topic verse", submitted)
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
}
