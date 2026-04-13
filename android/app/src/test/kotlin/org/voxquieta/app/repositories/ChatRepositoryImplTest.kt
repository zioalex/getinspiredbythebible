package org.voxquieta.app.repositories

import org.voxquieta.app.data.local.VoxQuietaDatabase
import org.voxquieta.app.data.local.ConversationDao
import org.voxquieta.app.data.local.MessageDao
import org.voxquieta.app.data.remote.api.BibleApiService
import org.voxquieta.app.data.repositories.ChatRepositoryImpl
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.every
import io.mockk.mockk
import io.mockk.slot
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test

/**
 * Unit tests for [ChatRepositoryImpl].
 *
 * Since [truncateTitle] is private, its behaviour is exercised via
 * [createConversation], which is the only production caller.  We capture the
 * [ConversationEntity] written to the DAO and inspect its `title` field.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class ChatRepositoryImplTest {

    private lateinit var conversationDao: ConversationDao
    private lateinit var messageDao: MessageDao
    private lateinit var db: VoxQuietaDatabase
    private lateinit var api: BibleApiService
    private lateinit var repository: ChatRepositoryImpl

    @Before
    fun setUp() {
        conversationDao = mockk(relaxed = true)
        messageDao = mockk(relaxed = true)
        db = mockk {
            every { conversationDao() } returns conversationDao
            every { messageDao() } returns messageDao
        }
        api = mockk(relaxed = true)
        repository = ChatRepositoryImpl(api, db)
    }

    // ── truncateTitle tests ───────────────────────────────────────────────────

    /**
     * 1. Text ≤60 chars — returned unchanged.
     */
    @Test
    fun `short title under 60 chars is returned unchanged`() = runTest {
        val title = "Hello World"
        val conversation = repository.createConversation("id-1", title)

        assertEquals(title, conversation.title)
    }

    /**
     * 2. Text exactly 60 chars — at the boundary, no truncation occurs.
     */
    @Test
    fun `title of exactly 60 chars is returned unchanged`() = runTest {
        val title = "A".repeat(60) // 60 chars, no spaces → length == maxLength → no truncation
        val conversation = repository.createConversation("id-2", title)

        assertEquals(title, conversation.title)
    }

    /**
     * 3. Long text with spaces — truncated at the nearest word boundary before
     *    60 chars, with an ellipsis appended.
     */
    @Test
    fun `title longer than 60 chars is truncated at word boundary`() = runTest {
        // Craft a string where there is a space before position 60 that is
        // past the halfway mark (>30), so the word-boundary branch is taken.
        // "The quick brown fox jumps over the lazy dog says hello world more" = >60 chars
        val title = "The quick brown fox jumps over the lazy dog says hello world more text here"
        // take(60) = "The quick brown fox jumps over the lazy dog says hello world"
        // lastIndexOf(' ') in that 60-char substring → 59... let's verify:
        // pos 59 is the 'r' of "world"?  Let's count manually:
        // "The quick brown fox jumps over the lazy dog says hello world" = 60 chars
        // lastIndexOf(' ') → index of space before "world" = 54
        // 54 > 30 → word boundary branch → "The quick brown fox jumps over the lazy dog says hello" + "…"
        val conversation = repository.createConversation("id-3", title)

        // Must end with "…" and be shorter than original
        assertTrue(
            "Expected title to end with ellipsis, got: ${conversation.title}",
            conversation.title.endsWith("…"),
        )
        assertTrue(
            "Expected truncated title to be shorter than original",
            conversation.title.length < title.length,
        )
        // Must not contain the trailing words that were cut
        assertFalse(
            "Expected trailing words to be removed",
            conversation.title.contains("world"),
        )
    }

    /**
     * 4. Long text with no spaces — truncated at character 60, with ellipsis.
     */
    @Test
    fun `title longer than 60 chars with no spaces is truncated at char boundary`() = runTest {
        val title = "A".repeat(80) // 80 chars, no spaces
        // take(60) = "A"*60, lastIndexOf(' ') = -1 (< maxLength/2=30) → char boundary branch
        val conversation = repository.createConversation("id-4", title)

        assertEquals("A".repeat(60) + "…", conversation.title)
    }

    /**
     * 5. 61-char title — truncated (just over the boundary).
     */
    @Test
    fun `title of 61 chars is truncated`() = runTest {
        // 61 X's, no spaces → char boundary → first 60 + "…"
        val title = "X".repeat(61)
        val conversation = repository.createConversation("id-5", title)

        assertEquals("X".repeat(60) + "…", conversation.title)
    }

    // ── Helpers re-exported so tests compile without extra imports ────────────

    private fun assertTrue(message: String, condition: Boolean) =
        org.junit.Assert.assertTrue(message, condition)

    private fun assertFalse(message: String, condition: Boolean) =
        org.junit.Assert.assertFalse(message, condition)
}
