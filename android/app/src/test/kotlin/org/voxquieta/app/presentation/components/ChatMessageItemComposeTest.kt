package org.voxquieta.app.presentation.components

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithContentDescription
import org.junit.Assert.assertTrue
import org.junit.Test
import org.robolectric.annotation.Config
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

    // --- BITB-174: bubbles adapt to the available width ---------------------------------

    private val longAnswer = "This is a long answer about the Bible that keeps going. ".repeat(40)

    private fun bubbleWidthDp(): Float {
        mountItem(
            Message(
                id = UUID.randomUUID().toString(),
                role = Message.Role.ASSISTANT,
                content = longAnswer,
            ),
        )
        val node = composeRule.onNodeWithTag("chat_bubble").fetchSemanticsNode()
        val density = node.layoutInfo.density.density
        val widthPx = node.size.width
        return widthPx / density
    }

    @Test
    @Config(qualifiers = "w360dp-h640dp")
    fun `bubble stays within 320dp on a phone`() {
        val w = bubbleWidthDp()
        assertTrue("phone bubble was $w", w <= 320.5f)
    }

    @Test
    @Config(qualifiers = "w800dp-h1280dp")
    fun `bubble is wider than 320dp on a tablet in portrait`() {
        val w = bubbleWidthDp()
        assertTrue("tablet portrait bubble was $w", w > 320f && w <= 840.5f)
    }

    @Test
    @Config(qualifiers = "w1280dp-h800dp")
    fun `bubble is wider than 320dp but capped at 840dp on a tablet in landscape`() {
        val w = bubbleWidthDp()
        assertTrue("tablet landscape bubble was $w", w > 320f && w <= 840.5f)
    }
}
