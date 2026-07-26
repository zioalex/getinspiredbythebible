package org.voxquieta.app.screens

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.voxquieta.app.presentation.screens.ChatTopBarPolicy
import org.voxquieta.app.presentation.screens.chatTopBarPolicy

/**
 * Unit tests for the [chatTopBarPolicy] helper which encodes the visibility
 * rules for the Chat screen's top app bar and navigation drawer.
 *
 * These rules implement the product requirement that the top-right of the
 * Chat screen exposes only the "+ New chat" shortcut and (when applicable)
 * the verses panel — every other action, including the Bible-version picker
 * and the language picker, lives in the left hamburger drawer.
 */
class ChatTopBarPolicyTest {

    // ── Verses panel visibility ───────────────────────────────────────────────

    @Test
    fun `verses panel hidden when there are no verses`() {
        val policy = chatTopBarPolicy(versesCount = 0, messagesCount = 0)
        assertFalse(policy.showVersesPanelInTopBar)
    }

    @Test
    fun `verses panel visible when there is one verse`() {
        val policy = chatTopBarPolicy(versesCount = 1, messagesCount = 0)
        assertTrue(policy.showVersesPanelInTopBar)
    }

    @Test
    fun `verses panel visible when there are many verses`() {
        val policy = chatTopBarPolicy(versesCount = 42, messagesCount = 5)
        assertTrue(policy.showVersesPanelInTopBar)
    }

    @Test
    fun `verses panel visibility is independent of message count`() {
        val withMessages = chatTopBarPolicy(versesCount = 0, messagesCount = 99)
        val withoutMessages = chatTopBarPolicy(versesCount = 0, messagesCount = 0)
        assertFalse(withMessages.showVersesPanelInTopBar)
        assertFalse(withoutMessages.showVersesPanelInTopBar)
    }

    // ── Clear conversation drawer entry visibility ───────────────────────────

    @Test
    fun `clear-conversation drawer entry hidden when there are no messages`() {
        val policy = chatTopBarPolicy(versesCount = 0, messagesCount = 0)
        assertFalse(policy.showClearConversationInDrawer)
    }

    @Test
    fun `clear-conversation drawer entry visible when there is one message`() {
        val policy = chatTopBarPolicy(versesCount = 0, messagesCount = 1)
        assertTrue(policy.showClearConversationInDrawer)
    }

    @Test
    fun `clear-conversation drawer entry visible when there are many messages`() {
        val policy = chatTopBarPolicy(versesCount = 7, messagesCount = 23)
        assertTrue(policy.showClearConversationInDrawer)
    }

    @Test
    fun `clear-conversation visibility is independent of verse count`() {
        val withVerses = chatTopBarPolicy(versesCount = 99, messagesCount = 0)
        val withoutVerses = chatTopBarPolicy(versesCount = 0, messagesCount = 0)
        assertFalse(withVerses.showClearConversationInDrawer)
        assertFalse(withoutVerses.showClearConversationInDrawer)
    }

    // ── Combined / regression cases ──────────────────────────────────────────

    @Test
    fun `empty state hides both the verses panel and the clear-conversation entry`() {
        val policy = chatTopBarPolicy(versesCount = 0, messagesCount = 0)
        assertEquals(
            ChatTopBarPolicy(
                showVersesPanelInTopBar = false,
                showClearConversationInDrawer = false,
            ),
            policy,
        )
    }

    @Test
    fun `fully populated state shows both`() {
        val policy = chatTopBarPolicy(versesCount = 3, messagesCount = 4)
        assertEquals(
            ChatTopBarPolicy(
                showVersesPanelInTopBar = true,
                showClearConversationInDrawer = true,
            ),
            policy,
        )
    }

    @Test
    fun `negative inputs are treated as empty (defensive)`() {
        // Counts can never realistically be negative, but the policy must not
        // misclassify them as "present" if they ever are.
        val policy = chatTopBarPolicy(versesCount = -1, messagesCount = -5)
        assertFalse(policy.showVersesPanelInTopBar)
        assertFalse(policy.showClearConversationInDrawer)
    }
}
