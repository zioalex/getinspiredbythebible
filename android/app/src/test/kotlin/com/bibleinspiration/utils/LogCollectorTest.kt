package com.bibleinspiration.utils

import android.util.Log
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class LogCollectorTest {

    @Before
    fun setUp() { LogCollector.clear() }

    @Test
    fun `log stores entry and getLog returns it`() {
        LogCollector.log(Log.DEBUG, "TestTag", "Hello world", null)
        val log = LogCollector.getLog()
        assertTrue(log.contains("Hello world"))
        assertTrue(log.contains("TestTag"))
    }

    @Test
    fun `log includes throwable stacktrace`() {
        val ex = RuntimeException("boom")
        LogCollector.log(Log.ERROR, "Tag", "Error occurred", ex)
        val log = LogCollector.getLog()
        assertTrue(log.contains("boom"))
    }

    @Test
    fun `clear empties the log`() {
        LogCollector.log(Log.INFO, "Tag", "some message", null)
        LogCollector.clear()
        assertTrue(LogCollector.getLog().isEmpty())
    }

    @Test
    fun `priority characters are correct`() {
        LogCollector.log(android.util.Log.VERBOSE, "T", "v", null)
        LogCollector.log(android.util.Log.DEBUG, "T", "d", null)
        LogCollector.log(android.util.Log.INFO, "T", "i", null)
        LogCollector.log(android.util.Log.WARN, "T", "w", null)
        LogCollector.log(android.util.Log.ERROR, "T", "e", null)
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
            LogCollector.log(Log.DEBUG, "T", "msg $i", null)
        }
        // Should not exceed 500 entries; getLog() lines should be <= 500
        val lines = LogCollector.getLog().lines().filter { it.isNotBlank() }
        assertTrue("Expected <= 500 lines but got ${lines.size}", lines.size <= 500)
    }
}
