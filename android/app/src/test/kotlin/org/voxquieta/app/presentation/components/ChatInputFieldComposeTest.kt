package org.voxquieta.app.presentation.components

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.test.assertIsNotFocused
import androidx.compose.ui.test.hasSetTextAction
import androidx.compose.ui.test.onNodeWithContentDescription
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
 *
 * Uses [hasSetTextAction] to locate the text field rather than placeholder text,
 * avoiding charset/apostrophe encoding mismatches in resource strings.
 */
class ChatInputFieldComposeTest : ComposeTestHarness() {

    @Test
    fun `send button forwards typed text to onSend`() {
        var sent: String? = null
        setContentThemed {
            var text by remember { mutableStateOf("") }
            ChatInputField(
                value = text,
                onValueChange = { text = it },
                onSend = { sent = it },
            )
        }

        composeRule.onNode(hasSetTextAction()).performTextInput("Hello")
        composeRule.onNodeWithContentDescription("Send").performClick()
        composeRule.waitForIdle()

        assertEquals("Hello", sent)
    }

    @Test
    fun `text field loses focus after a successful send (keyboard dismissed)`() {
        setContentThemed {
            var text by remember { mutableStateOf("") }
            ChatInputField(
                value = text,
                onValueChange = { text = it },
                onSend = { /* parent clears value in production */ },
            )
        }

        val field = composeRule.onNode(hasSetTextAction())
        field.performTextInput("Hello")   // focuses the field and types
        composeRule.onNodeWithContentDescription("Send").performClick()
        composeRule.waitForIdle()

        // focusManager.clearFocus() in submit() → field loses focus → IME dismissed
        field.assertIsNotFocused()
    }
}
