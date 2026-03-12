package com.bibleinspiration.utils

import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * Priority int values matching android.util.Log constants (avoid importing android.util.Log
 * in unit tests — the Android stub throws RuntimeException("Stub!") without
 * testOptions { unitTests.isReturnDefaultValues = true }):
 *   VERBOSE=2, DEBUG=3, INFO=4, WARN=5, ERROR=6
 */
class LogCollectorTest {

    @Before
    fun setUp() { LogCollector.clear() }

    @Test
    fun `log stores entry and getLog returns it`() {
        LogCollector.log(3 /* DEBUG */, "TestTag", "Hello world", null)
        val log = LogCollector.getLog()
        assertTrue(log.contains("Hello world"))
        assertTrue(log.contains("TestTag"))
    }

    @Test
    fun `log includes throwable stacktrace`() {
        val ex = RuntimeException("boom")
        LogCollector.log(6 /* ERROR */, "Tag", "Error occurred", ex)
        val log = LogCollector.getLog()
        assertTrue(log.contains("boom"))
    }

    @Test
    fun `clear empties the log`() {
        LogCollector.log(4 /* INFO */, "Tag", "some message", null)
        LogCollector.clear()
        assertTrue(LogCollector.getLog().isEmpty())
    }

    @Test
    fun `priority characters are correct`() {
        LogCollector.log(2 /* VERBOSE */, "T", "v", null)
        LogCollector.log(3 /* DEBUG */,   "T", "d", null)
        LogCollector.log(4 /* INFO */,    "T", "i", null)
        LogCollector.log(5 /* WARN */,    "T", "w", null)
        LogCollector.log(6 /* ERROR */,   "T", "e", null)
        val log = LogCollector.getLog()
        assertTrue(log.contains("V/T"))
        assertTrue(log.contains("D/T"))
        assertTrue(log.contains("I/T"))
        assertTrue(log.contains("W/T"))
        assertTrue(log.contains("E/T"))
    }

    @Test
    fun `entries capped at 500`() {
        repeat(600) { i ->
            LogCollector.log(3 /* DEBUG */, "T", "msg $i", null)
        }
        // Should not exceed 500 entries; getLog() lines should be <= 500
        val lines = LogCollector.getLog().lines().filter { it.isNotBlank() }
        assertTrue("Expected <= 500 lines but got ${lines.size}", lines.size <= 500)
    }
}
