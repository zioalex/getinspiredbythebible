package org.voxquieta.app

import android.content.Context
import androidx.room.Room
import org.voxquieta.app.data.local.VoxQuietaDatabase
import org.voxquieta.app.data.local.ConversationDao
import org.voxquieta.app.data.local.MessageDao
import org.voxquieta.app.di.DatabaseModule
import dagger.Module
import dagger.Provides
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import dagger.hilt.testing.TestInstallIn
import javax.inject.Singleton

/**
 * Replaces [DatabaseModule] during instrumented tests with an in-memory Room database.
 *
 * Benefits over the production disk-based DB:
 * - No disk I/O delays that could cause flaky test timing
 * - Isolated per test run — no leftover state between CI jobs
 * - `allowMainThreadQueries()` avoids coroutine threading issues in tests
 */
@Module
@TestInstallIn(
    components = [SingletonComponent::class],
    replaces = [DatabaseModule::class],
)
object TestDatabaseModule {

    @Provides
    @Singleton
    fun provideInMemoryDatabase(
        @ApplicationContext ctx: Context,
    ): VoxQuietaDatabase =
        Room.inMemoryDatabaseBuilder(ctx, VoxQuietaDatabase::class.java)
            .allowMainThreadQueries()
            .build()

    @Provides
    fun provideConversationDao(db: VoxQuietaDatabase): ConversationDao =
        db.conversationDao()

    @Provides
    fun provideMessageDao(db: VoxQuietaDatabase): MessageDao =
        db.messageDao()
}
