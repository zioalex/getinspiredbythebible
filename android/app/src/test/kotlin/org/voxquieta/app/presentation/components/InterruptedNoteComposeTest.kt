package org.voxquieta.app.presentation.components

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertHeightIsAtLeast
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.unit.dp
import org.junit.Assert.assertEquals
import org.junit.Test
import org.voxquieta.app.domain.models.Message
import org.voxquieta.app.presentation.viewmodels.ChapterSheetState
import org.voxquieta.app.testing.ComposeTestHarness

/**
 * BITB-320: the "This response was interrupted" note and Continue button under an assistant
 * reply whose stream dropped. Runs in the `*ComposeTest` Robolectric lane.
 */
class InterruptedNoteComposeTest : ComposeTestHarness() {

    @Test
    fun `note and Continue render and tapping Continue fires once`() {
        var taps = 0
        setContentThemed { InterruptedNote(onContinue = { taps++ }) }

        composeRule.onNodeWithText("This response was interrupted").assertIsDisplayed()
        composeRule.onNodeWithText("Continue").assertIsDisplayed().assertHeightIsAtLeast(48.dp).performClick()

        assertEquals(1, taps)
    }

    @Test
    fun `without a handler only the note shows`() {
        setContentThemed { InterruptedNote(onContinue = null) }

        composeRule.onNodeWithText("This response was interrupted").assertIsDisplayed()
        composeRule.onNodeWithText("Continue").assertDoesNotExist()
    }

    @Test
    fun `interrupted assistant message shows the note, an ordinary one does not`() {
        setContentThemed {
            ChatMessageItem(
                message = Message(
                    id = "m1",
                    role = Message.Role.ASSISTANT,
                    content = "Partial answer",
                    isInterrupted = true,
                ),
                chapterSheetState = ChapterSheetState.Idle,
                preferredTranslation = null,
                onLoadChapter = { _, _, _ -> },
                onDismissSheet = {},
                onContinue = {},
            )
        }

        composeRule.onNodeWithText("This response was interrupted").assertIsDisplayed()
        composeRule.onNodeWithText("Continue").assertIsDisplayed()
    }

    @Test
    fun `ordinary assistant message has no interrupted note`() {
        setContentThemed {
            ChatMessageItem(
                message = Message(id = "m2", role = Message.Role.ASSISTANT, content = "Complete answer."),
                chapterSheetState = ChapterSheetState.Idle,
                preferredTranslation = null,
                onLoadChapter = { _, _, _ -> },
                onDismissSheet = {},
                onContinue = {},
            )
        }

        composeRule.onNodeWithText("This response was interrupted").assertDoesNotExist()
    }
}
