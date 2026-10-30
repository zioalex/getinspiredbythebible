package org.voxquieta.app.data.local

import androidx.room.Database
import androidx.room.RoomDatabase

/**
 * Main Room database for the Vox Quieta app.
 *
 * Version history:
 *   1 — initial schema (conversations + messages tables)
 *   2 — messages.crisisJson (BITB-255); see [MIGRATION_1_2]
 */
@Database(
    entities = [ConversationEntity::class, MessageEntity::class],
    version = 2,
    exportSchema = true,
)
abstract class VoxQuietaDatabase : RoomDatabase() {
    abstract fun conversationDao(): ConversationDao
    abstract fun messageDao(): MessageDao
}
