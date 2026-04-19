package org.voxquieta.app.data.local

import androidx.room.Entity
import androidx.room.PrimaryKey

/**
 * Room entity for a persisted conversation.
 */
@Entity(tableName = "conversations")
data class ConversationEntity(
    @PrimaryKey val id: String,
    val title: String,
    val createdAt: Long,
    val updatedAt: Long,
)
