package org.voxquieta.app.di

import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import org.voxquieta.app.tts.AndroidSpeechEngine
import org.voxquieta.app.tts.SpeechEngine
import javax.inject.Singleton

/** BITB-119: binds the platform text-to-speech engine (a process-wide singleton). */
@Module
@InstallIn(SingletonComponent::class)
abstract class SpeechModule {

    @Binds
    @Singleton
    abstract fun bindSpeechEngine(impl: AndroidSpeechEngine): SpeechEngine
}
