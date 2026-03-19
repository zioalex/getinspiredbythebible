package com.bibleinspiration.viewmodels

import com.bibleinspiration.presentation.viewmodels.ChapterSheetState
import com.bibleinspiration.data.remote.models.ChapterResponseDto
import com.bibleinspiration.data.remote.models.ChapterVerseDto
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Pure logic tests for the [ChapterSheetState] sealed class hierarchy.
 *
 * These tests verify:
 * - Each state can be correctly pattern-matched with `is`
 * - Data states carry the right payloads
 * - States are distinguishable via type checks (no false positives)
 */
class ChapterSheetStateTest {

    // ── Idle state ────────────────────────────────────────────────────────────

    @Test
    fun `Idle is an instance of ChapterSheetState`() {
        val state: ChapterSheetState = ChapterSheetState.Idle
        assertTrue(state is ChapterSheetState.Idle)
    }

    @Test
    fun `Idle is not Loading`() {
        val state: ChapterSheetState = ChapterSheetState.Idle
        assertFalse(state is ChapterSheetState.Loading)
    }

    @Test
    fun `Idle is not Success`() {
        val state: ChapterSheetState = ChapterSheetState.Idle
        assertFalse(state is ChapterSheetState.Success)
    }

    @Test
    fun `Idle is not Error`() {
        val state: ChapterSheetState = ChapterSheetState.Idle
        assertFalse(state is ChapterSheetState.Error)
    }

    // ── Loading state ─────────────────────────────────────────────────────────

    @Test
    fun `Loading is an instance of ChapterSheetState`() {
        val state: ChapterSheetState = ChapterSheetState.Loading
        assertTrue(state is ChapterSheetState.Loading)
    }

    @Test
    fun `Loading is not Idle`() {
        val state: ChapterSheetState = ChapterSheetState.Loading
        assertFalse(state is ChapterSheetState.Idle)
    }

    @Test
    fun `Loading is not Success`() {
        val state: ChapterSheetState = ChapterSheetState.Loading
        assertFalse(state is ChapterSheetState.Success)
    }

    @Test
    fun `Loading is not Error`() {
        val state: ChapterSheetState = ChapterSheetState.Loading
        assertFalse(state is ChapterSheetState.Error)
    }

    // ── Success state ─────────────────────────────────────────────────────────

    @Test
    fun `Success carries the provided ChapterResponseDto`() {
        val dto = ChapterResponseDto(
            book = "John",
            chapter = 3,
            verses = listOf(ChapterVerseDto(16, "For God so loved the world…")),
        )
        val state = ChapterSheetState.Success(dto)

        assertTrue(state is ChapterSheetState.Success)
        assertEquals("John", state.response.book)
        assertEquals(3, state.response.chapter)
        assertEquals(1, state.response.verses.size)
        assertEquals(16, state.response.verses.first().verseNumber)
    }

    @Test
    fun `Success with empty verses list has zero-size verses`() {
        val dto = ChapterResponseDto(book = "Psalms", chapter = 23, verses = emptyList())
        val state = ChapterSheetState.Success(dto)

        assertTrue(state.response.verses.isEmpty())
    }

    @Test
    fun `Success is not Idle`() {
        val state = ChapterSheetState.Success(
            ChapterResponseDto("Genesis", 1, listOf(ChapterVerseDto(1, "In the beginning…"))),
        )
        assertFalse(state is ChapterSheetState.Idle)
    }

    @Test
    fun `Success is not Loading`() {
        val state = ChapterSheetState.Success(
            ChapterResponseDto("Genesis", 1, listOf(ChapterVerseDto(1, "In the beginning…"))),
        )
        assertFalse(state is ChapterSheetState.Loading)
    }

    @Test
    fun `Success is not Error`() {
        val state = ChapterSheetState.Success(
            ChapterResponseDto("John", 3, emptyList()),
        )
        assertFalse(state is ChapterSheetState.Error)
    }

    @Test
    fun `Success translation is preserved when set`() {
        val dto = ChapterResponseDto(
            book = "Romans",
            chapter = 8,
            verses = listOf(ChapterVerseDto(28, "All things work together…")),
            translation = "NIV",
        )
        val state = ChapterSheetState.Success(dto)
        assertEquals("NIV", state.response.translation)
    }

    @Test
    fun `Success translation defaults to null when not set`() {
        val dto = ChapterResponseDto(book = "Romans", chapter = 8, verses = emptyList())
        val state = ChapterSheetState.Success(dto)
        assertNull(state.response.translation)
    }

    // ── Error state ───────────────────────────────────────────────────────────

    @Test
    fun `Error carries the provided message`() {
        val state = ChapterSheetState.Error("Network error. Please check your connection.")

        assertTrue(state is ChapterSheetState.Error)
        assertEquals("Network error. Please check your connection.", state.message)
    }

    @Test
    fun `Error with empty message string`() {
        val state = ChapterSheetState.Error("")
        assertTrue(state is ChapterSheetState.Error)
        assertEquals("", state.message)
    }

    @Test
    fun `Error is not Idle`() {
        val state = ChapterSheetState.Error("some error")
        assertFalse(state is ChapterSheetState.Idle)
    }

    @Test
    fun `Error is not Loading`() {
        val state = ChapterSheetState.Error("some error")
        assertFalse(state is ChapterSheetState.Loading)
    }

    @Test
    fun `Error is not Success`() {
        val state = ChapterSheetState.Error("some error")
        assertFalse(state is ChapterSheetState.Success)
    }

    // ── when-expression completeness ──────────────────────────────────────────

    @Test
    fun `when expression exhaustively handles all states`() {
        val states: List<ChapterSheetState> = listOf(
            ChapterSheetState.Idle,
            ChapterSheetState.Loading,
            ChapterSheetState.Success(ChapterResponseDto("John", 1, emptyList())),
            ChapterSheetState.Error("err"),
        )

        val labels = states.map { state ->
            when (state) {
                is ChapterSheetState.Idle -> "idle"
                is ChapterSheetState.Loading -> "loading"
                is ChapterSheetState.Success -> "success"
                is ChapterSheetState.Error -> "error"
            }
        }

        assertEquals(listOf("idle", "loading", "success", "error"), labels)
    }

    // ── ChapterVerseDto helpers ───────────────────────────────────────────────

    @Test
    fun `ChapterVerseDto holds correct verseNumber and text`() {
        val dto = ChapterVerseDto(verseNumber = 7, text = "Ask and it will be given.")
        assertEquals(7, dto.verseNumber)
        assertEquals("Ask and it will be given.", dto.text)
    }

    @Test
    fun `ChapterResponseDto holds book chapter and verses`() {
        val verses = (1..5).map { ChapterVerseDto(it, "verse $it") }
        val dto = ChapterResponseDto(book = "Matthew", chapter = 5, verses = verses)
        assertEquals("Matthew", dto.book)
        assertEquals(5, dto.chapter)
        assertEquals(5, dto.verses.size)
    }
}
