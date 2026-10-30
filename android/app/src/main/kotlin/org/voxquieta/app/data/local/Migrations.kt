package org.voxquieta.app.data.local

import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

/**
 * v1 -> v2 (BITB-255): adds the nullable `crisisJson` column that stores the emergency/crisis
 * contacts card shown above an assistant message.
 *
 * An explicit migration is required: [org.voxquieta.app.di.DatabaseModule] keeps
 * `fallbackToDestructiveMigration()` for unexpected versions, which would otherwise WIPE every
 * user's saved conversations on this upgrade. The column is nullable with no default so existing
 * rows are kept untouched (`crisisJson = NULL` means "no card").
 */
val MIGRATION_1_2: Migration = object : Migration(1, 2) {
    override fun migrate(db: SupportSQLiteDatabase) {
        db.execSQL("ALTER TABLE messages ADD COLUMN crisisJson TEXT")
    }
}
