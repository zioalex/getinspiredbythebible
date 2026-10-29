package org.voxquieta.app.data.local

import android.content.Context
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.voxquieta.app.di.DatabaseModule

/**
 * BITB-251: Room v1 -> v2 (`messages.crisisJson`).
 *
 * Builds a genuine v1 database with raw SQL (the exact DDL from schemas/.../1.json), then opens it
 * through the PRODUCTION [DatabaseModule.provideDatabase] so the test also proves the migration is
 * registered. The destructive fallback would otherwise silently wipe every saved conversation on
 * upgrade, so the key assertion is that the old rows survive.
 */
@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34], application = android.app.Application::class)
class MigrationV1ToV2Test {

    // Historical DB name used by DatabaseModule.
    private val dbName = "bible_inspiration.db"
    private lateinit var context: Context

    @Before
    fun setUp() {
        context = ApplicationProvider.getApplicationContext()
        context.deleteDatabase(dbName)
    }

    @After
    fun tearDown() {
        context.deleteDatabase(dbName)
    }

    private fun createV1Database() {
        val raw = context.openOrCreateDatabase(dbName, Context.MODE_PRIVATE, null)
        raw.execSQL(
            "CREATE TABLE IF NOT EXISTS `conversations` (`id` TEXT NOT NULL, `title` TEXT NOT NULL, " +
                "`createdAt` INTEGER NOT NULL, `updatedAt` INTEGER NOT NULL, PRIMARY KEY(`id`))",
        )
        raw.execSQL(
            "CREATE TABLE IF NOT EXISTS `messages` (`id` TEXT NOT NULL, `conversationId` TEXT NOT NULL, " +
                "`role` TEXT NOT NULL, `content` TEXT NOT NULL, `versesJson` TEXT NOT NULL, " +
                "`createdAt` INTEGER NOT NULL, PRIMARY KEY(`id`), FOREIGN KEY(`conversationId`) " +
                "REFERENCES `conversations`(`id`) ON UPDATE NO ACTION ON DELETE CASCADE )",
        )
        raw.execSQL(
            "CREATE INDEX IF NOT EXISTS `index_messages_conversationId` ON `messages` (`conversationId`)",
        )
        raw.execSQL("INSERT INTO conversations VALUES ('c1', 'Old chat', 1, 2)")
        raw.execSQL("INSERT INTO messages VALUES ('m1', 'c1', 'user', 'hello', '[]', 10)")
        raw.execSQL("INSERT INTO messages VALUES ('m2', 'c1', 'assistant', 'peace', '[]', 11)")
        raw.version = 1
        raw.close()
    }

    @Test
    fun `migration range is 1 to 2`() {
        assertEquals(1, MIGRATION_1_2.startVersion)
        assertEquals(2, MIGRATION_1_2.endVersion)
    }

    @Test
    fun `upgrading a v1 database keeps conversations and messages and adds a null crisisJson`() = runTest {
        createV1Database()

        val db = DatabaseModule.provideDatabase(context)
        try {
            val conversations = db.conversationDao().observeAll().first()
            assertEquals(listOf("c1"), conversations.map { it.id })
            assertEquals("Old chat", conversations.single().title)

            val messages = db.messageDao().observeByConversation("c1").first()
            assertEquals(listOf("m1", "m2"), messages.map { it.id })
            assertEquals(listOf("hello", "peace"), messages.map { it.content })
            assertTrue("old rows must have no card", messages.all { it.crisisJson == null })
        } finally {
            db.close()
        }
    }

    @Test
    fun `a migrated database can store and read back a crisis card`() = runTest {
        createV1Database()

        val db = DatabaseModule.provideDatabase(context)
        try {
            db.messageDao().upsertIfConversationExists(
                MessageEntity(
                    id = "m3",
                    conversationId = "c1",
                    role = "assistant",
                    content = "I am here.",
                    versesJson = "[]",
                    createdAt = 12,
                    crisisJson = """{"kind":"self_harm","country":"IT"}""",
                ),
            )

            val stored = db.messageDao().observeByConversation("c1").first()
            assertEquals(3, stored.size)
            assertEquals("""{"kind":"self_harm","country":"IT"}""", stored.last().crisisJson)
            assertNull(stored.first().crisisJson)
        } finally {
            db.close()
        }
    }

    @Test
    fun `a fresh v2 database is created without a migration`() = runTest {
        val db = Room.databaseBuilder(context, VoxQuietaDatabase::class.java, dbName)
            .addMigrations(MIGRATION_1_2)
            .allowMainThreadQueries()
            .build()
        try {
            assertTrue(db.messageDao().observeByConversation("none").first().isEmpty())
        } finally {
            db.close()
        }
    }
}
