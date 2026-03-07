package com.bibleinspiration.di

import android.content.Context
import androidx.room.Room
import com.bibleinspiration.data.local.BibleInspirationDatabase
import com.bibleinspiration.data.local.ConversationDao
import com.bibleinspiration.data.local.MessageDao
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object DatabaseModule {

    @Provides
    @Singleton
    fun provideDatabase(@ApplicationContext ctx: Context): BibleInspirationDatabase =
        Room.databaseBuilder(ctx, BibleInspirationDatabase::class.java, "bible_inspiration.db")
            .build()

    @Provides
    fun provideConversationDao(db: BibleInspirationDatabase): ConversationDao =
        db.conversationDao()

    @Provides
    fun provideMessageDao(db: BibleInspirationDatabase): MessageDao =
        db.messageDao()
}
