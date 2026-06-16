package org.voxquieta.app.presentation.components

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.test.assertIsNotFocused
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performTextInput
import org.junit.Assert.assertEquals
import org.junit.Test
import org.voxquieta.app.testing.ComposeTestHarness

/**
 * Robolectric-backed Compose UI tests for [ChatInputField] (BITB-048).
 *
 * Verifies that submitting a message forwards the text to [ChatInputField.onSend]
 * and clears focus (dismissing the IME) — the core BITB-048 requirement.
 */
class ChatInputFieldComposeTest : ComposeTestHarness() {

    @Test
    fun `send button forwards typed text to onSend`() {
        var sent: String? = null
        setContentThemed {
            var text by mutableStateOf("")
            ChatInputField(
                value = text,
                onValueChange = { text = it },
                onSend = { sent = it },
            )
        }

        composeRule.onNodeWithText("Share what’s on your heart…").performTextInput("Hello")
        composeRule.onNodeWithContentDescription("Send").performClick()
        composeRule.waitForIdle()

        assertEquals("Hello", sent)
    }

    @Test
    fun `text field loses focus after a successful send (keyboard dismissed)`() {
        setContentThemed {
            var text by mutableStateOf("")
            ChatInputField(
                value = text,
                onValueChange = { text = it },
                onSend = { /* parent clears value in production */ },
            )
        }

        val field = composeRule.onNodeWithText("Share what’s on your heart…")
        field.performTextInput("Hello")   // implicitly focuses the field
        composeRule.onNodeWithContentDescription("Send").performClick()
        composeRule.waitForIdle()

        // focusManager.clearFocus() in submit() → field no longer focused → IME dismissed
        field.assertIsNotFocused()
    }
}
