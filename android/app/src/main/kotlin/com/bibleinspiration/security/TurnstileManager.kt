package com.bibleinspiration.security

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class TurnstileManager @Inject constructor() {

    private val _tokenFlow = MutableStateFlow<String?>(null)
    val tokenFlow: StateFlow<String?> = _tokenFlow.asStateFlow()

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
}
