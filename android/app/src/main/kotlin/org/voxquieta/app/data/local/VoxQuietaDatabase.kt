package org.voxquieta.app.data.local

import androidx.room.Database
import androidx.room.RoomDatabase

/**
 * Main Room database for the Vox Quieta app.
 *
 * Version history:
 *   1 — initial schema (conversations + messages tables)
 */
@Database(
    entities = [ConversationEntity::class, MessageEntity::class],
    version = 1,
    exportSchema = true,
)
abstract class VoxQuietaDatabase : RoomDatabase() {
    abstract fun conversationDao(): ConversationDao
    abstract fun messageDao(): MessageDao
}
