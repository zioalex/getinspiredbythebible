package com.bibleinspiration.streaming

import com.bibleinspiration.data.streaming.toChunkFlow
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.runTest
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
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

    // ── GAP-002: metadata chunk tests ────────────────────────────────────────

    /**
     * 8. Metadata chunk — a data line with type=metadata is emitted with all
     *    metadata fields populated and does NOT break the flow.
     */
    @Test
    fun `metadata chunk is parsed and emitted correctly`() = runTest {
        val metadataJson = """{"type":"metadata","message_id":"abc-123","model":"gpt-4o","scripture_context":null}"""
        val body = bodyOf(
            "data: $metadataJson\n" +
                "data: {\"type\":\"content\",\"content\":\"Hello\"}\n" +
                "data: [DONE]\n",
        )

        val chunks = mutableListOf<com.bibleinspiration.data.remote.models.StreamChunkDto>()
        body.toChunkFlow().collect { chunks.add(it) }

        assertEquals(2, chunks.size)

        val metadata = chunks[0]
        assertEquals("metadata", metadata.type)
        assertEquals("abc-123", metadata.messageId)
        assertEquals("gpt-4o", metadata.model)
        assertNull(metadata.scriptureContext)

        val content = chunks[1]
        assertEquals("content", content.type)
        assertEquals("Hello", content.content)
    }

    /**
     * 9. Metadata chunk with scripture_context — scripture verses are deserialized
     *    inside the metadata chunk.
     */
    @Test
    fun `metadata chunk with scripture_context parses nested verses`() = runTest {
        val metadataJson = """
            {
              "type": "metadata",
              "message_id": "msg-1",
              "model": "claude-3-5-sonnet",
              "scripture_context": {
                "query": "love",
                "verses": [
                  {
                    "book": "John",
                    "chapter": 3,
                    "verse": 16,
                    "text": "For God so loved the world...",
                    "translation": "NIV",
                    "reference": "John 3:16",
                    "similarity": 0.95
                  }
                ]
              }
            }
        """.trimIndent().replace("\n", "")
        val body = bodyOf("data: $metadataJson\n")

        val chunks = mutableListOf<com.bibleinspiration.data.remote.models.StreamChunkDto>()
        body.toChunkFlow().collect { chunks.add(it) }

        assertEquals(1, chunks.size)
        val metadata = chunks[0]
        assertEquals("metadata", metadata.type)

        val ctx = metadata.scriptureContext
        assertNotNull(ctx)
        assertEquals("love", ctx!!.query)
        assertEquals(1, ctx.verses.size)
        assertEquals("John", ctx.verses[0].book)
        assertEquals(3, ctx.verses[0].chapter)
        assertEquals(16, ctx.verses[0].verse)
        assertEquals("NIV", ctx.verses[0].translation)
    }

    /**
     * 10. Error chunk — a data line with type=error is emitted and does not crash
     *     the parser.
     */
    @Test
    fun `error chunk is parsed without crashing`() = runTest {
        val body = bodyOf(
            "data: {\"type\":\"error\",\"error\":\"Service unavailable\",\"error_code\":\"503\"}\n",
        )

        val chunks = mutableListOf<com.bibleinspiration.data.remote.models.StreamChunkDto>()
        body.toChunkFlow().collect { chunks.add(it) }

        assertEquals(1, chunks.size)
        assertEquals("error", chunks[0].type)
        assertEquals("Service unavailable", chunks[0].error)
        assertEquals("503", chunks[0].errorCode)
    }

    /**
     * 11. Content chunk with type field — the new typed content format is handled.
     */
    @Test
    fun `typed content chunk is parsed with type=content`() = runTest {
        val body = bodyOf("data: {\"type\":\"content\",\"content\":\"streaming text\"}\n")

        val chunks = mutableListOf<com.bibleinspiration.data.remote.models.StreamChunkDto>()
        body.toChunkFlow().collect { chunks.add(it) }

        assertEquals(1, chunks.size)
        assertEquals("content", chunks[0].type)
        assertEquals("streaming text", chunks[0].content)
    }

    // ── GAP-002: spec-mandated test cases (A, B, C) ───────────────────────────

    /**
     * Test A (GAP-002): metadata chunk with scripture_context and message_id.
     *
     * The `event: metadata` line is silently dropped; the actual payload is on
     * the subsequent `data:` line. Asserts type, messageId, and verse count.
     */
    @Test
    fun `metadata chunk is parsed correctly`() = runTest {
        val body = bodyOf(
            "event: metadata\n" +
                "data: {\"type\":\"metadata\",\"message_id\":\"abc-123\"," +
                "\"scripture_context\":{\"verses\":[{\"book\":\"John\",\"chapter\":3," +
                "\"verse\":16,\"text\":\"For God so loved...\",\"translation\":\"KJV\"," +
                "\"relevance_score\":0.9}],\"passages\":[]}," +
                "\"provider\":\"ollama\",\"model\":\"llama3\",\"detected_translation\":\"KJV\"}\n",
        )

        val chunks = mutableListOf<com.bibleinspiration.data.remote.models.StreamChunkDto>()
        body.toChunkFlow().collect { chunks.add(it) }

        assertEquals(1, chunks.size)
        assertEquals("metadata", chunks[0].type)
        assertEquals("abc-123", chunks[0].messageId)
        assertEquals(1, chunks[0].scriptureContext?.verses?.size)
    }

    /**
     * Test B (GAP-002): content chunks accumulate correctly in the new format.
     *
     * Feed: 1 metadata chunk + 2 content chunks + [DONE] sentinel.
     * Expect: exactly 3 chunks emitted; [DONE] stops the flow.
     */
    @Test
    fun `content chunks accumulate correctly in new format`() = runTest {
        val body = bodyOf(
            "event: metadata\n" +
                "data: {\"type\":\"metadata\",\"message_id\":\"msg-1\"," +
                "\"provider\":\"ollama\",\"model\":\"llama3\"}\n" +
                "event: content\n" +
                "data: {\"type\":\"content\",\"content\":\"Hello \"}\n" +
                "event: content\n" +
                "data: {\"type\":\"content\",\"content\":\"world\"}\n" +
                "data: [DONE]\n",
        )

        val chunks = mutableListOf<com.bibleinspiration.data.remote.models.StreamChunkDto>()
        body.toChunkFlow().collect { chunks.add(it) }

        assertEquals(3, chunks.size)
        assertEquals("metadata", chunks[0].type)
        assertEquals("content", chunks[1].type)
        assertEquals("Hello ", chunks[1].content)
        assertEquals("content", chunks[2].type)
        assertEquals("world", chunks[2].content)
    }

    /**
     * Test C (GAP-002): legacy format (no type field) still works.
     *
     * The old backend emits `{"content":"...","done":false/true}` chunks.
     * Both chunks should be emitted; the second has `done=true`.
     */
    @Test
    fun `legacy format with no type field still works`() = runTest {
        val body = bodyOf(
            "data: {\"content\":\"hello\",\"done\":false}\n" +
                "data: {\"content\":\"\",\"done\":true}\n",
        )

        val chunks = mutableListOf<com.bibleinspiration.data.remote.models.StreamChunkDto>()
        body.toChunkFlow().collect { chunks.add(it) }

        assertEquals(2, chunks.size)
        assertNull(chunks[0].type)
        assertEquals("hello", chunks[0].content)
        assertFalse(chunks[0].done)
        assertNull(chunks[1].type)
        assertTrue(chunks[1].done)
    }
}

