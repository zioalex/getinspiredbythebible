package org.voxquieta.app.di

import org.voxquieta.app.BuildConfig
import org.voxquieta.app.data.remote.api.ApiClient
import org.voxquieta.app.data.remote.api.BibleApiService
import org.voxquieta.app.data.remote.interceptors.TurnstileInterceptor
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object NetworkModule {

    @Provides
    @Singleton
    fun provideBibleApiService(turnstileInterceptor: TurnstileInterceptor): BibleApiService =
        ApiClient.create(
            baseUrl = BuildConfig.BASE_URL,
            debug = BuildConfig.DEBUG,
            turnstileInterceptor = turnstileInterceptor,
        )
}
