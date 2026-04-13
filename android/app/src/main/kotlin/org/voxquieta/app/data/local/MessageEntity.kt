package org.voxquieta.app.data.local

import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.PrimaryKey

/**
 * Room entity for a persisted chat message.
 *
 * Foreign key references [ConversationEntity] with CASCADE delete so that
 * removing a conversation also removes all its messages automatically.
 */
@Entity(
    tableName = "messages",
    foreignKeys = [
        ForeignKey(
            entity = ConversationEntity::class,
            parentColumns = ["id"],
            childColumns = ["conversationId"],
            onDelete = ForeignKey.CASCADE,
        ),
    ],
    indices = [Index("conversationId")],
)
data class MessageEntity(
    @PrimaryKey val id: String,
    val conversationId: String,
    /** "user" or "assistant" */
    val role: String,
    val content: String,
    /** JSON-serialised [List<SerializableVerse>]. */
    val versesJson: String,
    val createdAt: Long,
)
