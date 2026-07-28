package org.voxquieta.app.presentation.components

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.test.assertExists
import androidx.compose.ui.test.assertIsEnabled
import androidx.compose.ui.test.hasSetTextAction
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
 * Verifies the submit path: Send button fires [ChatInputField.onSend] with the
 * typed text. Uses [hasSetTextAction] to locate the field — avoids apostrophe
 * encoding mismatches between test source (U+2019) and string resources (U+0027).
 *
 * Note: IME dismissal (focus cleared after send) is the goal of BITB-048 but
 * Robolectric does not reliably simulate Compose focus transitions in the test
 * clock environment, so that aspect is verified by manual testing on device.
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
                maxLength = 500,
            )
        }

        composeRule.onNode(hasSetTextAction()).performTextInput("Hello")
        composeRule.onNodeWithContentDescription("Send").performClick()
        composeRule.waitForIdle()

        assertEquals("Hello", sent)
    }

    @Test
    fun `text field stays enabled while loading so next message can be typed`() {
        setContentThemed {
            ChatInputField(
                value = "draft",
                onValueChange = {},
                onSend = {},
                isLoading = true,
                isSessionLimitReached = false,
                maxLength = 500,
            )
        }

        // Field must remain editable during streaming (enabled = !isSessionLimitReached)
        composeRule.onNode(hasSetTextAction()).assertIsEnabled()
    }

    @Test
    fun `counter reflects the passed maxLength rather than a hardcoded default`() {
        // BITB-075: maxLength is now a required, server-derived value (no
        // compiled-in default) — this guards against silent drift back to a
        // stale constant if a call site ever forgets to pass it explicitly.
        setContentThemed {
            var text by remember { mutableStateOf("a".repeat(9)) }
            ChatInputField(
                value = text,
                onValueChange = { text = it },
                onSend = {},
                maxLength = 10,
            )
        }

        // At 9/10 chars (>= 80% of maxLength=10) the counter must be visible
        // and show the maxLength we passed in, not some other default.
        composeRule.onNodeWithText("9/10").assertExists()
    }
}
