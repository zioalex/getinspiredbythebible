package org.voxquieta.app.data.local

import android.content.Context
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.voxquieta.app.di.DatabaseModule

/**
 * BITB-320: Room v2 -> v3 (`messages.interrupted INTEGER NOT NULL DEFAULT 0`).
 *
 * Builds a genuine v2 database with raw SQL, then opens it through the PRODUCTION
 * [DatabaseModule.provideDatabase] so the test also proves the migration is registered (the
 * destructive fallback would otherwise wipe every saved conversation on upgrade).
 */
@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34], application = android.app.Application::class)
class MigrationV2ToV3Test {

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

    private fun createV2Database() {
        val raw = context.openOrCreateDatabase(dbName, Context.MODE_PRIVATE, null)
        raw.execSQL(
            "CREATE TABLE IF NOT EXISTS `conversations` (`id` TEXT NOT NULL, `title` TEXT NOT NULL, " +
                "`createdAt` INTEGER NOT NULL, `updatedAt` INTEGER NOT NULL, PRIMARY KEY(`id`))",
        )
        raw.execSQL(
            "CREATE TABLE IF NOT EXISTS `messages` (`id` TEXT NOT NULL, `conversationId` TEXT NOT NULL, " +
                "`role` TEXT NOT NULL, `content` TEXT NOT NULL, `versesJson` TEXT NOT NULL, " +
                "`createdAt` INTEGER NOT NULL, `crisisJson` TEXT, PRIMARY KEY(`id`), " +
                "FOREIGN KEY(`conversationId`) REFERENCES `conversations`(`id`) " +
                "ON UPDATE NO ACTION ON DELETE CASCADE )",
        )
        raw.execSQL(
            "CREATE INDEX IF NOT EXISTS `index_messages_conversationId` ON `messages` (`conversationId`)",
        )
        raw.execSQL("INSERT INTO conversations VALUES ('c1', 'Old chat', 1, 2)")
        raw.execSQL("INSERT INTO messages VALUES ('m1', 'c1', 'user', 'hello', '[]', 10, NULL)")
        raw.execSQL("INSERT INTO messages VALUES ('m2', 'c1', 'assistant', 'peace', '[]', 11, '{\"k\":1}')")
        raw.version = 2
        raw.close()
    }

    @Test
    fun `migration range is 2 to 3`() {
        assertEquals(2, MIGRATION_2_3.startVersion)
        assertEquals(3, MIGRATION_2_3.endVersion)
    }

    @Test
    fun `upgrading a v2 database keeps rows and defaults interrupted to false`() = runTest {
        createV2Database()

        val db = DatabaseModule.provideDatabase(context)
        try {
            val messages = db.messageDao().observeByConversation("c1").first()
            assertEquals(listOf("m1", "m2"), messages.map { it.id })
            assertEquals(listOf("hello", "peace"), messages.map { it.content })
            assertEquals("""{"k":1}""", messages.last().crisisJson)
            assertTrue("old rows must not be interrupted", messages.none { it.interrupted })
        } finally {
            db.close()
        }
    }

    @Test
    fun `a migrated database stores and reads back the interrupted flag`() = runTest {
        createV2Database()

        val db = DatabaseModule.provideDatabase(context)
        try {
            db.messageDao().upsertIfConversationExists(
                MessageEntity(
                    id = "m3",
                    conversationId = "c1",
                    role = "assistant",
                    content = "Cut off",
                    versesJson = "[]",
                    createdAt = 12,
                    interrupted = true,
                ),
            )
            val stored = db.messageDao().observeByConversation("c1").first()
            assertEquals(3, stored.size)
            assertTrue(stored.last().interrupted)
            assertFalse(stored.first().interrupted)
        } finally {
            db.close()
        }
    }

    @Test
    fun `a v1 database upgrades through both migrations`() = runTest {
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
        raw.version = 1
        raw.close()

        val db = DatabaseModule.provideDatabase(context)
        try {
            val messages = db.messageDao().observeByConversation("c1").first()
            assertEquals(listOf("m1"), messages.map { it.id })
            assertFalse(messages.single().interrupted)
        } finally {
            db.close()
        }
    }

    @Test
    fun `a fresh v3 database is created without a migration`() = runTest {
        val db = Room.databaseBuilder(context, VoxQuietaDatabase::class.java, dbName)
            .addMigrations(MIGRATION_1_2, MIGRATION_2_3)
            .allowMainThreadQueries()
            .build()
        try {
            assertTrue(db.messageDao().observeByConversation("none").first().isEmpty())
        } finally {
            db.close()
        }
    }
}
