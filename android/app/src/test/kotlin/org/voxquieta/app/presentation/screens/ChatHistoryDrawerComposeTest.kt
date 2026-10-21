package org.voxquieta.app.presentation.screens

import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performSemanticsAction
import org.junit.Assert.assertEquals
import org.junit.Test
import org.voxquieta.app.testing.ComposeTestHarness

/**
 * Robolectric-backed Compose UI tests for the support entry in [ChatHistoryDrawer]
 * (BITB-168). Runs under the `testDebugCompose` lane.
 */
class ChatHistoryDrawerComposeTest : ComposeTestHarness() {

    private fun mountDrawer(onOpenSupport: () -> Unit = {}) {
        setContentThemed {
            ChatHistoryDrawer(
                conversations = emptyList(),
                currentConversationId = null,
                hasMessages = false,
                onNewChat = {},
                onSelectConversation = {},
                onOpenAllConversations = {},
                onClearConversation = {},
                onOpenLanguagePicker = {},
                onOpenTranslationPicker = {},
                onOpenChurchFinder = {},
                onOpenSupport = onOpenSupport,
                onOpenSettings = {},
            )
        }
    }

    @Test
    fun `support item is displayed`() {
        mountDrawer()
        composeRule.onNodeWithText("Support Vox Quieta").assertIsDisplayed()
    }

    @Test
    fun `clicking the support item fires the callback once`() {
        var clicks = 0
        mountDrawer(onOpenSupport = { clicks++ })
        // Semantic click, not a pointer tap: the drawer is taller than Robolectric's default
        // screen, so the item's centre can fall outside the visible area and a tap would miss.
        composeRule
            .onNodeWithText("Support Vox Quieta")
            .performSemanticsAction(SemanticsActions.OnClick)
        assertEquals(1, clicks)
    }

    @Test
    fun `settings item is still displayed`() {
        mountDrawer()
        composeRule.onNodeWithText("Settings").assertIsDisplayed()
    }
}
