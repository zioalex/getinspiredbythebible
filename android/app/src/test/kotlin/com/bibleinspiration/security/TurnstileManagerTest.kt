package com.bibleinspiration.security

import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Test

class TurnstileManagerTest {

    private lateinit var manager: TurnstileManager

    @Before
    fun setUp() {
        manager = TurnstileManager()
    }

    @Test
    fun `initial token is null`() = runTest {
        assertNull(manager.currentToken())
        assertNull(manager.tokenFlow.first())
    }

    @Test
    fun `onTokenReceived sets token`() = runTest {
        manager.onTokenReceived("test-token-abc")

        assertEquals("test-token-abc", manager.currentToken())
        assertEquals("test-token-abc", manager.tokenFlow.first())
    }

    @Test
    fun `onTokenExpired clears token`() = runTest {
        manager.onTokenReceived("some-token")
        manager.onTokenExpired()

        assertNull(manager.currentToken())
        assertNull(manager.tokenFlow.first())
    }

    @Test
    fun `onError clears token`() = runTest {
        manager.onTokenReceived("some-token")
        manager.onError("110200")

        assertNull(manager.currentToken())
        assertNull(manager.tokenFlow.first())
    }
}
