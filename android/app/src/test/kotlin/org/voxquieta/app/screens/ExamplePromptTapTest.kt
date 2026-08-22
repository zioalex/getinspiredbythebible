package org.voxquieta.app.screens

import org.junit.Assert.assertEquals
import org.junit.Test
import org.voxquieta.app.presentation.screens.onExamplePromptTapped

/**
 * BITB-081 — tapping an example question must send it, unconditionally,
 * on the first tap. These tests pin the contract that made the bug possible:
 * there is no readiness parameter to gate on.
 */
class ExamplePromptTapTest {

    @Test
    fun `tap sends the prompt verbatim`() {
        val sent = mutableListOf<String>()
        onExamplePromptTapped("I feel anxious", clearInput = {}, sendMessage = { sent += it })
        assertEquals(listOf("I feel anxious"), sent)
    }

    @Test
    fun `tap clears the composer before sending`() {
        val order = mutableListOf<String>()
        onExamplePromptTapped(
            prompt = "Where do I find hope?",
            clearInput = { order += "clear" },
            sendMessage = { order += "send" },
        )
        // Clearing first means the tapped text can never be left in the field,
        // even if sendMessage throws.
        assertEquals(listOf("clear", "send"), order)
    }
}
