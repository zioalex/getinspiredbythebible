package org.voxquieta.app.di

import org.voxquieta.app.data.repositories.ChatRepositoryImpl
import org.voxquieta.app.data.repositories.ChurchRepositoryImpl
import org.voxquieta.app.data.repositories.ContactRepositoryImpl
import org.voxquieta.app.domain.repositories.ChatRepository
import org.voxquieta.app.domain.repositories.ChurchRepository
import org.voxquieta.app.domain.repositories.ContactRepository
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
