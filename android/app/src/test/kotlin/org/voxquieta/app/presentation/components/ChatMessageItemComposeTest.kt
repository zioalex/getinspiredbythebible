package org.voxquieta.app.presentation.components

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.onNodeWithContentDescription
import org.junit.Test
import org.voxquieta.app.domain.models.Message
import org.voxquieta.app.presentation.viewmodels.ChapterSheetState
import org.voxquieta.app.testing.ComposeTestHarness
import java.util.UUID

/**
 * Robolectric-backed Compose UI tests for [ChatMessageItem] — specifically the
 * one-tap copy-user-prompt button added in BITB-047.
 *
 * Runs under the `testDebugCompose` task / `android-compose-tests.yml` lane.
 */
class ChatMessageItemComposeTest : ComposeTestHarness() {

    private fun userMessage(content: String = "My question") = Message(
        id = UUID.randomUUID().toString(),
        role = Message.Role.USER,
        content = content,
    )

    private fun assistantMessage(streaming: Boolean = false) = Message(
        id = UUID.randomUUID().toString(),
        role = Message.Role.ASSISTANT,
        content = if (streaming) "" else "Here is an answer.",
        isStreaming = streaming,
    )

    private fun mountItem(message: Message) = setContentThemed {
        ChatMessageItem(
            message = message,
            chapterSheetState = ChapterSheetState.Idle,
            preferredTranslation = null,
            onLoadChapter = { _, _, _ -> },
            onDismissSheet = {},
        )
    }

    @Test
    fun `copy button is displayed for user messages`() {
        mountItem(userMessage())
        composeRule
            .onNodeWithContentDescription("Copy message")
            .assertIsDisplayed()
    }

    @Test
    fun `copy button is absent for streaming assistant messages`() {
        mountItem(assistantMessage(streaming = true))
        composeRule
            .onNodeWithContentDescription("Copy message")
            .assertDoesNotExist()
    }
}
