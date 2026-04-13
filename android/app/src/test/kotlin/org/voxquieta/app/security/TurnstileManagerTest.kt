package org.voxquieta.app.security

import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
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

    // -------------------------------------------------------------------------
    // Single-use token reset tests
    // -------------------------------------------------------------------------

    @Test
    fun `requestReset clears the token immediately`() = runTest {
        manager.onTokenReceived("live-token")
        manager.requestReset()

        assertNull(manager.currentToken())
        assertNull(manager.tokenFlow.first())
    }

    @Test
    fun `requestReset emits on resetTrigger`() = runTest {
        var emissionCount = 0
        val job = launch {
            manager.resetTrigger.collect { emissionCount++ }
        }
        // Advance so the collector coroutine starts and subscribes to the SharedFlow
        // before we emit, otherwise replay=0 means the emission is dropped.
        testScheduler.advanceUntilIdle()

        manager.requestReset()
        // Allow the coroutine to process the emission.
        testScheduler.advanceUntilIdle()

        assertEquals(1, emissionCount)
        job.cancel()
    }

    @Test
    fun `onTokenConsumed clears the token`() = runTest {
        manager.onTokenReceived("spent-token")
        manager.onTokenConsumed()

        assertNull(manager.currentToken())
        assertNull(manager.tokenFlow.first())
    }

    @Test
    fun `onTokenConsumed emits on resetTrigger`() = runTest {
        var emissionCount = 0
        val job = launch {
            manager.resetTrigger.collect { emissionCount++ }
        }
        // Advance so the collector coroutine starts and subscribes to the SharedFlow
        // before we emit, otherwise replay=0 means the emission is dropped.
        testScheduler.advanceUntilIdle()

        manager.onTokenConsumed()
        testScheduler.advanceUntilIdle()

        assertEquals(1, emissionCount)
        job.cancel()
    }

    @Test
    fun `requestReset emits once per call`() = runTest {
        var emissionCount = 0
        val job = launch {
            manager.resetTrigger.collect { emissionCount++ }
        }
        // Advance so the collector coroutine starts and subscribes to the SharedFlow
        // before we emit, otherwise replay=0 means all emissions are dropped.
        testScheduler.advanceUntilIdle()

        manager.requestReset()
        manager.requestReset()
        manager.requestReset()
        testScheduler.advanceUntilIdle()

        assertEquals(3, emissionCount)
        job.cancel()
    }

    @Test
    fun `new token can be received after reset`() = runTest {
        manager.onTokenReceived("old-token")
        manager.onTokenConsumed()

        assertNull(manager.currentToken())

        manager.onTokenReceived("fresh-token")

        assertEquals("fresh-token", manager.currentToken())
        assertEquals("fresh-token", manager.tokenFlow.first())
    }
}
