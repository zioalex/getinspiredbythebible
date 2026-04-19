package org.voxquieta.app.security

import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class TurnstileManager @Inject constructor() {

    private val _tokenFlow = MutableStateFlow<String?>(null)
    val tokenFlow: StateFlow<String?> = _tokenFlow.asStateFlow()

    private val _resetTrigger = MutableSharedFlow<Unit>(replay = 0, extraBufferCapacity = Channel.UNLIMITED)
    val resetTrigger: SharedFlow<Unit> = _resetTrigger.asSharedFlow()

    fun onTokenReceived(token: String) {
        _tokenFlow.value = token
    }

    fun onTokenExpired() {
        _tokenFlow.value = null
    }

    fun onError(errorCode: String) {
        _tokenFlow.value = null
    }

    fun currentToken(): String? = _tokenFlow.value

    /**
     * Clears the cached token immediately and signals the WebView to re-render
     * the Turnstile widget so a fresh single-use token is obtained.
     */
    fun requestReset() {
        _tokenFlow.value = null
        _resetTrigger.tryEmit(Unit)
    }

    /**
     * Semantic alias for [requestReset] – call this at every call site where
     * a Turnstile token has just been consumed by the server so that the next
     * request will always carry a fresh token.
     */
    fun onTokenConsumed() {
        requestReset()
    }
}
