package com.bibleinspiration

import android.content.Context
import androidx.room.Room
import com.bibleinspiration.data.local.BibleInspirationDatabase
import com.bibleinspiration.data.local.ConversationDao
import com.bibleinspiration.data.local.MessageDao
import com.bibleinspiration.di.DatabaseModule
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
    ): BibleInspirationDatabase =
        Room.inMemoryDatabaseBuilder(ctx, BibleInspirationDatabase::class.java)
            .allowMainThreadQueries()
            .build()

    @Provides
    fun provideConversationDao(db: BibleInspirationDatabase): ConversationDao =
        db.conversationDao()

    @Provides
    fun provideMessageDao(db: BibleInspirationDatabase): MessageDao =
        db.messageDao()
}
