package org.voxquieta.app.presentation.components

import androidx.compose.ui.test.hasClickAction
import androidx.compose.ui.test.onAllNodes
import androidx.compose.ui.test.onFirst
import androidx.compose.ui.test.performClick
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.voxquieta.app.presentation.screens.onExamplePromptTapped
import org.voxquieta.app.testing.ComposeTestHarness

/**
 * BITB-081 — tapping a welcome-screen example question sends it on the first
 * tap, even on a cold start where Turnstile has not yet produced a token.
 *
 * The banner is mounted with the same handler [ChatScreen][org.voxquieta.app
 * .presentation.screens.ChatScreen] uses ([onExamplePromptTapped]); ChatScreen
 * itself cannot be mounted here because it resolves its ViewModels via
 * `hiltViewModel()`, which needs an Activity context.
 */
class WelcomeBannerComposeTest : ComposeTestHarness() {

    @Test
    fun `tapping a suggestion sends immediately when turnstile is not ready`() {
        // Cold start: no Turnstile token yet. The handler under test takes no
        // readiness flag at all, so there is nothing to gate on here.
        val sent = mutableListOf<String>()
        var inputText = "stale draft"

        setContentThemed {
            WelcomeBanner(
                onPromptSelected = { prompt ->
                    onExamplePromptTapped(
                        prompt = prompt,
                        clearInput = { inputText = "" },
                        sendMessage = { sent += it },
                    )
                },
            )
        }

        // The suggestion cards are the only clickable nodes in the banner.
        composeRule.onAllNodes(hasClickAction()).onFirst().performClick()
        composeRule.waitForIdle()

        assertEquals("one tap must send exactly once", 1, sent.size)
        assertTrue(sent.single().isNotBlank())
        assertEquals("tapped text must not be left in the composer", "", inputText)
    }
}
