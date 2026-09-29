package org.voxquieta.app.presentation.components

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import org.junit.Assert.assertEquals
import org.junit.Test
import org.voxquieta.app.testing.ComposeTestHarness

/**
 * Robolectric-backed tests for [SessionLimitActions] (BITB-156).
 *
 * [SessionLimitActions] is a stateless composable so it can be mounted directly
 * here — [org.voxquieta.app.presentation.screens.ChatScreen] itself resolves its
 * ViewModel via `hiltViewModel()`, which the Robolectric Compose tier can't do
 * (see `COMPOSE_TESTS.md`).
 */
class SessionLimitActionsComposeTest : ComposeTestHarness() {

    @Test
    fun `both session-limit actions are displayed`() {
        setContentThemed {
            SessionLimitActions(
                onContinueConversation = {},
                onStartNewSession = {},
            )
        }

        composeRule.onNodeWithText("Continue this conversation").assertIsDisplayed()
        composeRule.onNodeWithText("Start New Session").assertIsDisplayed()
    }

    @Test
    fun `tapping continue invokes only the continue callback`() {
        var continueCount = 0
        var startNewCount = 0
        setContentThemed {
            SessionLimitActions(
                onContinueConversation = { continueCount++ },
                onStartNewSession = { startNewCount++ },
            )
        }

        composeRule.onNodeWithText("Continue this conversation").performClick()

        assertEquals(1, continueCount)
        assertEquals(0, startNewCount)
    }

    @Test
    fun `tapping start new session invokes only the start-new callback`() {
        var continueCount = 0
        var startNewCount = 0
        setContentThemed {
            SessionLimitActions(
                onContinueConversation = { continueCount++ },
                onStartNewSession = { startNewCount++ },
            )
        }

        composeRule.onNodeWithText("Start New Session").performClick()

        assertEquals(0, continueCount)
        assertEquals(1, startNewCount)
    }
}
