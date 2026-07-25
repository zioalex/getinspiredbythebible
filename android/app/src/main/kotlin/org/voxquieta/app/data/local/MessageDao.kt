package org.voxquieta.app.data.local

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Transaction
import kotlinx.coroutines.flow.Flow

@Dao
interface MessageDao {

    @Query("SELECT * FROM messages WHERE conversationId = :conversationId ORDER BY createdAt ASC")
    fun observeByConversation(conversationId: String): Flow<List<MessageEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(message: MessageEntity)

    @Query("SELECT EXISTS(SELECT 1 FROM conversations WHERE id = :conversationId)")
    suspend fun conversationExists(conversationId: String): Boolean

    /**
     * Inserts [message] only if its parent conversation still exists. Wrapped in a
     * transaction so a concurrent conversation delete cannot slip between the existence
     * check and the insert, which would otherwise raise a FOREIGN KEY constraint failure
     * (SQLITE_CONSTRAINT_FOREIGNKEY). A missing parent means the conversation was deleted
     * mid-stream, so the write is safely skipped instead of crashing.
     */
    @Transaction
    suspend fun upsertIfConversationExists(message: MessageEntity) {
        if (conversationExists(message.conversationId)) {
            upsert(message)
        }
    }
}
