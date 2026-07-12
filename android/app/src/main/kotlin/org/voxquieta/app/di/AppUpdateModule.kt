package org.voxquieta.app.di

import android.content.Context
import com.google.android.play.core.appupdate.AppUpdateManager
import com.google.android.play.core.appupdate.AppUpdateManagerFactory
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

/**
 * Hilt module providing the platform [AppUpdateManager] singleton that
 * [org.voxquieta.app.InAppUpdateManager] wraps.
 */
@Module
@InstallIn(SingletonComponent::class)
object AppUpdateModule {

    @Provides
    @Singleton
    fun provideAppUpdateManager(
        @ApplicationContext context: Context,
    ): AppUpdateManager = AppUpdateManagerFactory.create(context)
}
