package org.voxquieta.app.di

import android.content.Context
import androidx.room.Room
import org.voxquieta.app.data.local.VoxQuietaDatabase
import org.voxquieta.app.data.local.ConversationDao
import org.voxquieta.app.data.local.MessageDao
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
    fun provideDatabase(@ApplicationContext ctx: Context): VoxQuietaDatabase =
        Room.databaseBuilder(ctx, VoxQuietaDatabase::class.java, "bible_inspiration.db") // Historical DB name - do not rename without migration
            .fallbackToDestructiveMigration()
            .build()

    @Provides
    fun provideConversationDao(db: VoxQuietaDatabase): ConversationDao =
        db.conversationDao()

    @Provides
    fun provideMessageDao(db: VoxQuietaDatabase): MessageDao =
        db.messageDao()
}
