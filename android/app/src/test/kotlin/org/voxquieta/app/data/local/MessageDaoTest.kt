package org.voxquieta.app.data.local

import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/**
 * Robolectric-backed because [MessageDao] needs a real (in-memory) Room database with
 * foreign-key enforcement — the behaviour under test is the FOREIGN KEY guard added to
 * prevent the SQLITE_CONSTRAINT_FOREIGNKEY crash when a conversation is deleted mid-stream.
 */
@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34], application = android.app.Application::class)
class MessageDaoTest {

    private lateinit var db: VoxQuietaDatabase
    private lateinit var messageDao: MessageDao
    private lateinit var conversationDao: ConversationDao

    @Before
    fun setUp() {
        db = Room.inMemoryDatabaseBuilder(
            ApplicationProvider.getApplicationContext(),
            VoxQuietaDatabase::class.java,
        ).build()
        messageDao = db.messageDao()
        conversationDao = db.conversationDao()
    }

    @After
    fun tearDown() {
        db.close()
    }

    private fun conversation(id: String) =
        ConversationEntity(id = id, title = "t", createdAt = 0L, updatedAt = 0L)

    private fun message(id: String, conversationId: String) = MessageEntity(
        id = id,
        conversationId = conversationId,
        role = "assistant",
        content = "hi",
        versesJson = "[]",
        createdAt = 0L,
    )

    @Test
    fun `upsertIfConversationExists inserts when the parent conversation exists`() = runTest {
        conversationDao.upsert(conversation("c1"))

        messageDao.upsertIfConversationExists(message("m1", "c1"))

        val stored = messageDao.observeByConversation("c1").first()
        assertEquals(1, stored.size)
        assertEquals("m1", stored.first().id)
    }

    @Test
    fun `upsertIfConversationExists is a no-op when the parent conversation is missing`() = runTest {
        // No conversation row inserted — this simulates the conversation being deleted mid-stream.
        messageDao.upsertIfConversationExists(message("m1", "missing"))

        val stored = messageDao.observeByConversation("missing").first()
        assertTrue("Expected no message to be persisted for a missing parent", stored.isEmpty())
    }

    @Test
    fun `plain upsert throws a foreign key constraint failure when the parent is missing`() = runTest {
        // Documents the underlying crash the guard protects against: a bare insert against a
        // non-existent conversation violates the foreign key.
        try {
            messageDao.upsert(message("m1", "missing"))
            org.junit.Assert.fail("Expected a foreign key constraint failure")
        } catch (e: android.database.sqlite.SQLiteConstraintException) {
            assertTrue(e.message?.contains("FOREIGN KEY", ignoreCase = true) == true)
        }
    }
}
