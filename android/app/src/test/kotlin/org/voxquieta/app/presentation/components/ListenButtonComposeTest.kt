package org.voxquieta.app.presentation.components

import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.SemanticsMatcher
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.hasAnyAncestor
import androidx.compose.ui.test.hasContentDescription
import androidx.compose.ui.test.hasTestTag
import androidx.compose.ui.test.assert
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import org.junit.Assert.assertEquals
import org.junit.Test
import org.voxquieta.app.domain.models.Message
import org.voxquieta.app.presentation.viewmodels.ChapterSheetState
import org.voxquieta.app.testing.ComposeTestHarness

/**
 * Robolectric-backed Compose UI tests for the Listen / Pause / Resume control on [ChatMessageItem]
 * (BITB-119, BITB-205). Runs under the `testDebugCompose` task / `android-compose-tests.yml` lane.
 */
class ListenButtonComposeTest : ComposeTestHarness() {

    private val listen = "Listen to this answer"
    private val pause = "Pause reading"
    private val resume = "Resume reading"

    private fun assistant(
        content: String = "Here is an answer.",
        streaming: Boolean = false,
        error: Boolean = false,
    ) = Message(
        id = "assistant-1",
        role = Message.Role.ASSISTANT,
        content = content,
        isStreaming = streaming,
        isError = error,
    )

    private fun mount(
        message: Message,
        showListen: Boolean = true,
        isSpeaking: Boolean = false,
        isPaused: Boolean = false,
        onToggleListen: (() -> Unit)? = {},
    ) = setContentThemed {
        ChatMessageItem(
            message = message,
            chapterSheetState = ChapterSheetState.Idle,
            preferredTranslation = null,
            onLoadChapter = { _, _, _ -> },
            onDismissSheet = {},
            showListen = showListen,
            isSpeaking = isSpeaking,
            isPaused = isPaused,
            onToggleListen = onToggleListen,
        )
    }

    @Test
    fun `listen button is displayed on a finished assistant answer`() {
        mount(assistant())
        composeRule.onNodeWithContentDescription(listen).assertIsDisplayed()
    }

    @Test
    fun `listen button is hidden when showListen is false`() {
        mount(assistant(), showListen = false)
        composeRule.onNodeWithTag("listen_button").assertDoesNotExist()
    }

    @Test
    fun `listen button is hidden while the answer is still streaming`() {
        mount(assistant(content = "Partial", streaming = true))
        composeRule.onNodeWithTag("listen_button").assertDoesNotExist()
    }

    @Test
    fun `listen button is hidden for an empty answer`() {
        mount(assistant(content = ""))
        composeRule.onNodeWithTag("listen_button").assertDoesNotExist()
    }

    @Test
    fun `listen button is hidden on user messages`() {
        mount(Message(id = "u", role = Message.Role.USER, content = "My question"))
        composeRule.onNodeWithTag("listen_button").assertDoesNotExist()
    }

    @Test
    fun `idle state shows Listen with the not-reading state description`() {
        mount(assistant(), isSpeaking = false)
        composeRule.onNodeWithTag("listen_button")
            .assert(SemanticsMatcher.expectValue(SemanticsProperties.StateDescription, "Not reading aloud"))
        composeRule.onNodeWithContentDescription(listen).assertIsDisplayed()
    }

    @Test
    fun `speaking state shows Pause with the reading state description`() {
        mount(assistant(), isSpeaking = true)
        composeRule.onNodeWithContentDescription(pause).assertIsDisplayed()
        composeRule.onNodeWithTag("listen_button")
            .assert(SemanticsMatcher.expectValue(SemanticsProperties.StateDescription, "Reading aloud"))
    }

    @Test
    fun `paused state shows Resume with the paused state description`() {
        mount(assistant(), isPaused = true)
        composeRule.onNodeWithContentDescription(resume).assertIsDisplayed()
        composeRule.onNodeWithTag("listen_button")
            .assert(SemanticsMatcher.expectValue(SemanticsProperties.StateDescription, "Reading paused"))
    }

    @Test
    fun `listen copy and share render in the side rail, not the feedback row`() {
        setContentThemed {
            ChatMessageItem(
                message = assistant().copy(messageId = "srv-1"),
                chapterSheetState = ChapterSheetState.Idle,
                preferredTranslation = null,
                onLoadChapter = { _, _, _ -> },
                onDismissSheet = {},
                onFeedback = { _, _, _, _ -> },
                showListen = true,
                onToggleListen = {},
            )
        }
        composeRule.onNodeWithTag("message_action_rail").assertIsDisplayed()
        composeRule.onNode(hasAnyAncestor(hasTestTag("message_action_rail")) and hasTestTag("listen_button"))
            .assertIsDisplayed()
        composeRule.onNode(
            hasAnyAncestor(hasTestTag("message_action_rail")) and hasContentDescription("Copy message"),
        ).assertIsDisplayed()
        composeRule.onNode(
            hasAnyAncestor(hasTestTag("message_action_rail")) and hasContentDescription("Share message"),
        ).assertIsDisplayed()
        // The thumbs row is still there below the answer, outside the rail.
        composeRule.onNode(
            hasContentDescription("This was helpful") and !hasAnyAncestor(hasTestTag("message_action_rail")),
        ).assertIsDisplayed()
        composeRule.onNode(
            hasContentDescription("Copy message") and !hasAnyAncestor(hasTestTag("message_action_rail")),
        ).assertDoesNotExist()
    }

    @Test
    fun `no rail while streaming`() {
        mount(assistant(content = "Partial", streaming = true))
        composeRule.onNodeWithTag("message_action_rail").assertDoesNotExist()
    }

    @Test
    fun `no rail for user messages`() {
        mount(Message(id = "u", role = Message.Role.USER, content = "My question"))
        composeRule.onNodeWithTag("message_action_rail").assertDoesNotExist()
    }

    @Test
    fun `tapping the button invokes the toggle callback`() {
        var taps = 0
        mount(assistant(), onToggleListen = { taps++ })
        composeRule.onNodeWithTag("listen_button").performClick()
        assertEquals(1, taps)
    }

    @Test
    fun `listen button is hidden when no toggle callback is wired`() {
        mount(assistant(), onToggleListen = null)
        composeRule.onNodeWithTag("listen_button").assertDoesNotExist()
    }
}
