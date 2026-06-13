package org.voxquieta.app.streaming

import org.voxquieta.app.data.streaming.toChunkFlow
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.runTest
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
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

        val chunks = mutableListOf<org.voxquieta.app.data.remote.models.StreamChunkDto>()
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

        val chunks = mutableListOf<org.voxquieta.app.data.remote.models.StreamChunkDto>()
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

        val chunks = mutableListOf<org.voxquieta.app.data.remote.models.StreamChunkDto>()
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

        val chunks = mutableListOf<org.voxquieta.app.data.remote.models.StreamChunkDto>()
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

        val chunks = mutableListOf<org.voxquieta.app.data.remote.models.StreamChunkDto>()
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

        val chunks = mutableListOf<org.voxquieta.app.data.remote.models.StreamChunkDto>()
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

        val chunks = mutableListOf<org.voxquieta.app.data.remote.models.StreamChunkDto>()
        body.toChunkFlow().collect { chunks.add(it) }

        assertTrue(chunks.isEmpty())
    }

    // ── GAP-002: metadata event tests ─────────────────────────────────────────

    /**
     * 8. Metadata event — a data line with type=metadata emits a StreamChunkDto
     *    with the message_id and model fields populated and empty content.
     */
    @Test
    fun `metadata event is parsed and emitted with messageId and model`() = runTest {
        val body = bodyOf(
            """data: {"type":"metadata","message_id":"abc-123","provider":"ollama","model":"llama3.2","detected_translation":"kjv"}""" + "\n",
        )

        val chunks = mutableListOf<org.voxquieta.app.data.remote.models.StreamChunkDto>()
        body.toChunkFlow().collect { chunks.add(it) }

        assertEquals(1, chunks.size)
        assertEquals("metadata", chunks[0].type)
        assertEquals("abc-123", chunks[0].messageId)
        assertEquals("llama3.2", chunks[0].model)
        assertEquals("", chunks[0].content)
        assertFalse(chunks[0].done)
    }

    /**
     * 9. Metadata event followed by content chunks — both are emitted in order.
     *    The metadata chunk has type="metadata" and the content chunk has type="content".
     */
    @Test
    fun `metadata event followed by content chunks emits both in order`() = runTest {
        val body = bodyOf(
            """data: {"type":"metadata","message_id":"msg-001","model":"llama3.2"}""" + "\n" +
                """data: {"type":"content","content":"Hello","done":false}""" + "\n" +
                """data: {"type":"content","content":" world","done":true}""" + "\n",
        )

        val chunks = mutableListOf<org.voxquieta.app.data.remote.models.StreamChunkDto>()
        body.toChunkFlow().collect { chunks.add(it) }

        assertEquals(3, chunks.size)
        assertEquals("metadata", chunks[0].type)
        assertEquals("msg-001", chunks[0].messageId)
        assertEquals("", chunks[0].content)
        assertEquals("Hello", chunks[1].content)
        assertEquals(" world", chunks[2].content)
        assertTrue(chunks[2].done)
    }

    /**
     * 10. Metadata event with scripture_context verses — verses are extracted and included
     *     in the emitted StreamChunkDto.
     */
    @Test
    fun `metadata event with scripture_context verses emits StreamChunkDto with parsed verses`() = runTest {
        val body = bodyOf(
            """data: {"type":"metadata","message_id":"abc","model":"llama3","detected_translation":"kjv","scripture_context":{"query":"love","verses":[{"book":"John","chapter":3,"verse":16,"text":"For God so loved...","translation":"kjv","localized_book":null}],"passages":[]}}""" + "\n",
        )

        val chunks = mutableListOf<org.voxquieta.app.data.remote.models.StreamChunkDto>()
        body.toChunkFlow().collect { chunks.add(it) }

        assertEquals(1, chunks.size)
        assertEquals("metadata", chunks[0].type)
        assertEquals(1, chunks[0].verses.size)
        assertEquals("John", chunks[0].verses[0].book)
        assertEquals(3, chunks[0].verses[0].chapter)
        assertEquals(16, chunks[0].verses[0].verse)
    }

    /**
     * 11. Metadata event with localized_book in scripture_context verses — localized book
     *     name is included in the parsed VerseDto.
     */
    @Test
    fun `metadata event verses include localized_book when present`() = runTest {
        val body = bodyOf(
            """data: {"type":"metadata","message_id":"abc","model":"llama3","scripture_context":{"query":"love","verses":[{"book":"John","chapter":3,"verse":16,"text":"For God so loved...","translation":"kjv","localized_book":"Иоанна"}],"passages":[]}}""" + "\n",
        )

        val chunks = mutableListOf<org.voxquieta.app.data.remote.models.StreamChunkDto>()
        body.toChunkFlow().collect { chunks.add(it) }

        assertEquals(1, chunks.size)
        assertEquals("Иоанна", chunks[0].verses[0].localizedBook)
    }

    /**
     * 12. Metadata event without scripture_context — emits chunk with empty verses list.
     */
    @Test
    fun `metadata event without scripture_context emits empty verses list`() = runTest {
        val body = bodyOf(
            """data: {"type":"metadata","message_id":"abc","model":"llama3"}""" + "\n",
        )

        val chunks = mutableListOf<org.voxquieta.app.data.remote.models.StreamChunkDto>()
        body.toChunkFlow().collect { chunks.add(it) }

        assertEquals(1, chunks.size)
        assertTrue(chunks[0].verses.isEmpty())
    }

    /**
     * 13. Typed content chunk — a chunk with type="content" is treated as a
     *     regular content chunk.
     */
    @Test
    fun `typed content chunk is treated as a regular content chunk`() = runTest {
        val body = bodyOf(
            """data: {"type":"content","content":"typed hello","done":false}""" + "\n",
        )

        val chunks = mutableListOf<org.voxquieta.app.data.remote.models.StreamChunkDto>()
        body.toChunkFlow().collect { chunks.add(it) }

        assertEquals(1, chunks.size)
        assertEquals("typed hello", chunks[0].content)
        assertFalse(chunks[0].done)
    }

    /**
     * 14. Metadata event with language_suggestion — the field is extracted and populated
     *     on the emitted StreamChunkDto.
     */
    @Test
    fun `metadata event with language_suggestion populates languageSuggestion field`() = runTest {
        val body = bodyOf(
            """data: {"type":"metadata","message_id":"abc","model":"llama3","language_suggestion":"de"}""" + "\n",
        )

        val chunks = mutableListOf<org.voxquieta.app.data.remote.models.StreamChunkDto>()
        body.toChunkFlow().collect { chunks.add(it) }

        assertEquals(1, chunks.size)
        assertEquals("metadata", chunks[0].type)
        assertEquals("de", chunks[0].languageSuggestion)
    }

    /**
     * 15. Metadata event without language_suggestion — the field is null on the emitted chunk.
     */
    @Test
    fun `metadata event without language_suggestion yields null languageSuggestion`() = runTest {
        val body = bodyOf(
            """data: {"type":"metadata","message_id":"abc","model":"llama3"}""" + "\n",
        )

        val chunks = mutableListOf<org.voxquieta.app.data.remote.models.StreamChunkDto>()
        body.toChunkFlow().collect { chunks.add(it) }

        assertEquals(1, chunks.size)
        assertNull(chunks[0].languageSuggestion)
    }

    /**
     * 16. Completion event with resolved_verses — both the string citations and the
     *     resolved verse objects (with text) are parsed onto the chunk.
     */
    @Test
    fun `completion event parses verses_cited and resolved_verses`() = runTest {
        val body = bodyOf(
            """data: {"type":"completion","verses_cited":["John 14:27"],"resolved_verses":[{"book":"John","chapter":14,"verse":27,"text":"Peace I leave with you...","translation":"kjv"}]}""" + "\n",
        )

        val chunks = mutableListOf<org.voxquieta.app.data.remote.models.StreamChunkDto>()
        body.toChunkFlow().collect { chunks.add(it) }

        assertEquals(1, chunks.size)
        assertEquals("completion", chunks[0].type)
        assertEquals(listOf("John 14:27"), chunks[0].versesCited)
        assertEquals(1, chunks[0].resolvedVerses.size)
        assertEquals("John", chunks[0].resolvedVerses[0].book)
        assertEquals(27, chunks[0].resolvedVerses[0].verse)
    }
}
