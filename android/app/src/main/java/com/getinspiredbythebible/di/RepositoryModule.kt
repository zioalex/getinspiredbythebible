package com.getinspiredbythebible.di

import com.getinspiredbythebible.data.repository.ChatRepository
import com.getinspiredbythebible.data.repository.ChatRepositoryImpl
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

/**
 * Hilt module that binds the [ChatRepository] interface to its production implementation
 * [ChatRepositoryImpl].
 *
 * Using [@Binds] (instead of [@Provides]) generates less code at compile time and is the
 * idiomatic pattern when both the interface and implementation live in the same module.
 */
@Module
@InstallIn(SingletonComponent::class)
abstract class RepositoryModule {

    @Binds
    @Singleton
    abstract fun bindChatRepository(impl: ChatRepositoryImpl): ChatRepository
}
