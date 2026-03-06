package com.bibleinspiration.di

import com.bibleinspiration.BuildConfig
import com.bibleinspiration.data.remote.api.ApiClient
import com.bibleinspiration.data.remote.api.BibleApiService
import com.bibleinspiration.data.remote.interceptors.TurnstileInterceptor
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
