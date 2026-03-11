package com.bibleinspiration.streaming

import com.bibleinspiration.data.streaming.toChunkFlow
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.runTest
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import timber.log.Timber

@OptIn(ExperimentalCoroutinesApi::class)
class EventSourceParserTest {

    @Before
    fun setUp() {
        // Plant a no-op Timber tree so Timber.w() calls in the parser don't throw
        // "Must plant a tree before using Timber" in JVM unit tests.
        if (Timber.treeCount == 0) {
            Timber.plant(object : Timber.Tree() {
                override fun log(priority: Int, tag: String?, message: String, t: Throwable?) = Unit
            })
        }
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private fun bodyOf(text: String) =
        text.toResponseBody("text/event-stream".toMediaType())

    // ── Test cases ────────────────────────────────────────────────────────────

    /**
     * 1. Normal chunk — a well-formed data line emits a StreamChunkDto with the
     *    expected text and done=false.
     */
    @Test
    fun `well-formed data line emits StreamChunkDto`() = runTest {
        val body = bodyOf("data: {\"content\":\"hello\",\"done\":false}\n")

        val chunks = mutableListOf<com.bibleinspiration.data.remote.models.StreamChunkDto>()
        body.toChunkFlow().collect { chunks.add(it) }

        assertEquals(1, chunks.size)
        assertEquals("hello", chunks[0].content)
        assertFalse(chunks[0].done)
    }

    /**
     * 2. [DONE] sentinel — the flow terminates and emits nothing after it.
     */
    @Test
    fun `DONE sentinel terminates the flow`() = runTest {
        val body = bodyOf(
            "data: {\"content\":\"part1\",\"done\":false}\n" +
                "data: [DONE]\n" +
                "data: {\"content\":\"part2\",\"done\":false}\n",
        )

        val chunks = mutableListOf<com.bibleinspiration.data.remote.models.StreamChunkDto>()
        body.toChunkFlow().collect { chunks.add(it) }

        // Only the line before [DONE] should be emitted.
        assertEquals(1, chunks.size)
        assertEquals("part1", chunks[0].content)
    }

    /**
     * 3. done=true in JSON — the flow terminates after emitting that chunk.
     */
    @Test
    fun `done=true in JSON terminates the flow after emitting that chunk`() = runTest {
        val body = bodyOf(
            "data: {\"content\":\"final\",\"done\":true}\n" +
                "data: {\"content\":\"after\",\"done\":false}\n",
        )

        val chunks = mutableListOf<com.bibleinspiration.data.remote.models.StreamChunkDto>()
        body.toChunkFlow().collect { chunks.add(it) }

        // The done=true chunk is emitted, but nothing after it.
        assertEquals(1, chunks.size)
        assertEquals("final", chunks[0].content)
        assertTrue(chunks[0].done)
    }

    /**
     * 4. Malformed JSON — a data line with invalid JSON is skipped gracefully;
     *    the flow does NOT throw and continues to emit subsequent valid lines.
     */
    @Test
    fun `malformed JSON line is skipped and flow continues`() = runTest {
        val body = bodyOf(
            "data: {not valid json}\n" +
                "data: {\"content\":\"after malformed\",\"done\":false}\n",
        )

        val chunks = mutableListOf<com.bibleinspiration.data.remote.models.StreamChunkDto>()
        // Should not throw
        body.toChunkFlow().collect { chunks.add(it) }

        assertEquals(1, chunks.size)
        assertEquals("after malformed", chunks[0].content)
    }

    /**
     * 5. Non-data lines — lines without a "data:" prefix are ignored entirely.
     */
    @Test
    fun `non-data lines are ignored`() = runTest {
        val body = bodyOf(
            "event: ping\n" +
                ": keep-alive comment\n" +
                "\n" +
                "data: {\"content\":\"real\",\"done\":false}\n",
        )

        val chunks = mutableListOf<com.bibleinspiration.data.remote.models.StreamChunkDto>()
        body.toChunkFlow().collect { chunks.add(it) }

        assertEquals(1, chunks.size)
        assertEquals("real", chunks[0].content)
    }

    /**
     * 6. Multiple sequential chunks — two valid data lines are both emitted in order.
     */
    @Test
    fun `multiple sequential valid chunks are emitted in order`() = runTest {
        val body = bodyOf(
            "data: {\"content\":\"first\",\"done\":false}\n" +
                "data: {\"content\":\"second\",\"done\":false}\n",
        )

        val chunks = mutableListOf<com.bibleinspiration.data.remote.models.StreamChunkDto>()
        body.toChunkFlow().collect { chunks.add(it) }

        assertEquals(2, chunks.size)
        assertEquals("first", chunks[0].content)
        assertEquals("second", chunks[1].content)
    }

    /**
     * 7. Empty body — an empty ResponseBody completes the flow without emitting
     *    anything and without throwing.
     */
    @Test
    fun `empty body completes flow without emitting anything`() = runTest {
        val body = bodyOf("")

        val chunks = mutableListOf<com.bibleinspiration.data.remote.models.StreamChunkDto>()
        body.toChunkFlow().collect { chunks.add(it) }

        assertTrue(chunks.isEmpty())
    }
}
