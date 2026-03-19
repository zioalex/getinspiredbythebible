package com.bibleinspiration.di

import com.bibleinspiration.data.repositories.ChatRepositoryImpl
import com.bibleinspiration.data.repositories.ChurchRepositoryImpl
import com.bibleinspiration.data.repositories.ContactRepositoryImpl
import com.bibleinspiration.domain.repositories.ChatRepository
import com.bibleinspiration.domain.repositories.ChurchRepository
import com.bibleinspiration.domain.repositories.ContactRepository
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
abstract class RepositoryModule {

    @Binds
    @Singleton
    abstract fun bindChatRepository(impl: ChatRepositoryImpl): ChatRepository

    @Binds
    @Singleton
    abstract fun bindChurchRepository(impl: ChurchRepositoryImpl): ChurchRepository

    @Binds
    @Singleton
    abstract fun bindContactRepository(impl: ContactRepositoryImpl): ContactRepository
}
