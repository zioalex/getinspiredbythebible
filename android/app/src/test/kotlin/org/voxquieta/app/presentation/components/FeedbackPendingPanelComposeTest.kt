package org.voxquieta.app.presentation.components

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.hasSetTextAction
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performTextInput
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.voxquieta.app.testing.ComposeTestHarness

/**
 * Robolectric tests for [FeedbackPendingPanel] — the stateless content of the
 * feedback popover. Mounted DIRECTLY (no Popup, no rethink timer) per the
 * `COMPOSE_TESTS.md` guidance, so every assertion is deterministic. The popover
 * positioning and keyboard focus are verified by manual / instrumented QA.
 */
class FeedbackPendingPanelComposeTest : ComposeTestHarness() {

    private val maintainerNotice = "Your message will be shared with the app's maintainer."

    private fun noticeAbsent(): Boolean =
        composeRule.onAllNodesWithText(maintainerNotice, useUnmergedTree = false)
            .fetchSemanticsNodes(atLeastOneRootRequired = false).isEmpty()

    @Test
    fun `comment field is shown immediately`() {
        setContentThemed {
            FeedbackPendingPanel(
                rating = "negative",
                comment = "",
                commentOpen = false,
                progress = { 1f },
                onCommentFocus = {},
                onCommentChange = {},
                onUndo = {},
                onSend = {},
            )
        }
        // The comment field is present without any extra "Add a comment" step.
        composeRule.onNode(hasSetTextAction()).assertIsDisplayed()
        composeRule.onNodeWithText("Send").assertIsDisplayed()
    }

    @Test
    fun `negative rating shows the maintainer-sharing notice`() {
        setContentThemed {
            FeedbackPendingPanel(
                rating = "negative",
                comment = "",
                commentOpen = false,
                progress = { 1f },
                onCommentFocus = {},
                onCommentChange = {},
                onUndo = {},
                onSend = {},
            )
        }
        composeRule.onNodeWithText(maintainerNotice).assertIsDisplayed()
    }

    @Test
    fun `positive rating hides the maintainer notice`() {
        setContentThemed {
            FeedbackPendingPanel(
                rating = "positive",
                comment = "",
                commentOpen = false,
                progress = { 1f },
                onCommentFocus = {},
                onCommentChange = {},
                onUndo = {},
                onSend = {},
            )
        }
        assertTrue("maintainer notice must not appear for thumbs-up", noticeAbsent())
    }

    @Test
    fun `tapping Undo invokes onUndo`() {
        var undone = false
        setContentThemed {
            FeedbackPendingPanel(
                rating = "negative",
                comment = "",
                commentOpen = false,
                progress = { 1f },
                onCommentFocus = {},
                onCommentChange = {},
                onUndo = { undone = true },
                onSend = {},
            )
        }
        composeRule.onNodeWithText("Undo").performClick()
        assertTrue("Undo must invoke onUndo", undone)
    }

    @Test
    fun `typing a comment and tapping Send forwards the text`() {
        var sentComment: String? = null
        setContentThemed {
            var comment by remember { mutableStateOf("") }
            FeedbackPendingPanel(
                rating = "negative",
                comment = comment,
                commentOpen = false,
                progress = { 1f },
                onCommentFocus = {},
                onCommentChange = { comment = it },
                onUndo = {},
                onSend = { sentComment = comment },
            )
        }
        composeRule.onNode(hasSetTextAction()).performTextInput("Off-topic verse")
        composeRule.onNodeWithText("Send").performClick()
        assertEquals("Off-topic verse", sentComment)
    }

    @Test
    fun `progress bar exposes the sending content description`() {
        setContentThemed {
            FeedbackPendingPanel(
                rating = "positive",
                comment = "",
                commentOpen = false,
                progress = { 0.5f },
                onCommentFocus = {},
                onCommentChange = {},
                onUndo = {},
                onSend = {},
            )
        }
        composeRule.onNodeWithContentDescription("Sending feedback…").assertIsDisplayed()
    }
}
