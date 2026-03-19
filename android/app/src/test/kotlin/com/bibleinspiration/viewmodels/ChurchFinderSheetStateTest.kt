package com.bibleinspiration.viewmodels

import com.bibleinspiration.domain.models.Church
import com.bibleinspiration.presentation.viewmodels.ChurchFinderSheetState
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Unit tests for the [ChurchFinderSheetState] sealed class.
 *
 * Verifies:
 * - All four states exist and are distinct types
 * - Success carries its church list and location correctly
 * - Error carries its message correctly
 * - State identity and equality behave correctly
 * - `when` exhaustiveness across all branches
 */
class ChurchFinderSheetStateTest {

    private val sampleChurch = Church(
        name = "Grace Church",
        address = "Via Roma 1",
        city = "Rome",
        state = null,
        country = "Italy",
        phone = "+39 06 1234567",
        email = "info@grace.it",
        website = "https://grace.it",
    )

    // ── State identity ────────────────────────────────────────────────────────

    @Test
    fun `Idle is an instance of ChurchFinderSheetState`() {
        assertTrue(ChurchFinderSheetState.Idle is ChurchFinderSheetState)
    }

    @Test
    fun `Loading is an instance of ChurchFinderSheetState`() {
        assertTrue(ChurchFinderSheetState.Loading is ChurchFinderSheetState)
    }

    @Test
    fun `Success is an instance of ChurchFinderSheetState`() {
        val state = ChurchFinderSheetState.Success(
            churches = listOf(sampleChurch),
            location = "Rome",
        )
        assertTrue(state is ChurchFinderSheetState)
    }

    @Test
    fun `Error is an instance of ChurchFinderSheetState`() {
        assertTrue(ChurchFinderSheetState.Error("oops") is ChurchFinderSheetState)
    }

    // ── Type exclusivity ──────────────────────────────────────────────────────

    @Test
    fun `Idle is not Loading`() {
        assertFalse(ChurchFinderSheetState.Idle is ChurchFinderSheetState.Loading)
    }

    @Test
    fun `Loading is not Idle`() {
        assertFalse(ChurchFinderSheetState.Loading is ChurchFinderSheetState.Idle)
    }

    @Test
    fun `Success is not Idle`() {
        val state = ChurchFinderSheetState.Success(emptyList(), "Nowhere")
        assertFalse(state is ChurchFinderSheetState.Idle)
    }

    @Test
    fun `Error is not Success`() {
        val state = ChurchFinderSheetState.Error("network failure")
        assertFalse(state is ChurchFinderSheetState.Success)
    }

    // ── Success payload ───────────────────────────────────────────────────────

    @Test
    fun `Success carries correct church list`() {
        val churches = listOf(sampleChurch)
        val state = ChurchFinderSheetState.Success(churches = churches, location = "Rome")

        assertEquals(1, state.churches.size)
        assertEquals("Grace Church", state.churches[0].name)
        assertEquals("Rome", state.churches[0].city)
    }

    @Test
    fun `Success carries correct location string`() {
        val state = ChurchFinderSheetState.Success(churches = emptyList(), location = "Berlin")
        assertEquals("Berlin", state.location)
    }

    @Test
    fun `Success with empty church list is valid`() {
        val state = ChurchFinderSheetState.Success(churches = emptyList(), location = "Unknown")
        assertTrue(state.churches.isEmpty())
        assertEquals("Unknown", state.location)
    }

    @Test
    fun `Success with multiple churches has correct count`() {
        val churches = listOf(
            sampleChurch,
            sampleChurch.copy(name = "Faith Community", city = "Milan"),
        )
        val state = ChurchFinderSheetState.Success(churches = churches, location = "Italy")
        assertEquals(2, state.churches.size)
    }

    // ── Error payload ─────────────────────────────────────────────────────────

    @Test
    fun `Error carries its message correctly`() {
        val state = ChurchFinderSheetState.Error("Network error. Please check your connection.")
        assertEquals("Network error. Please check your connection.", state.message)
    }

    @Test
    fun `Error with empty message is valid`() {
        val state = ChurchFinderSheetState.Error("")
        assertEquals("", state.message)
    }

    @Test
    fun `two Error states with different messages are not equal`() {
        val e1 = ChurchFinderSheetState.Error("error A")
        val e2 = ChurchFinderSheetState.Error("error B")
        assertNotEquals(e1, e2)
    }

    @Test
    fun `two Error states with the same message are equal`() {
        val e1 = ChurchFinderSheetState.Error("same")
        val e2 = ChurchFinderSheetState.Error("same")
        assertEquals(e1, e2)
    }

    // ── Success equality ──────────────────────────────────────────────────────

    @Test
    fun `two Success states with same data are equal`() {
        val s1 = ChurchFinderSheetState.Success(listOf(sampleChurch), "Rome")
        val s2 = ChurchFinderSheetState.Success(listOf(sampleChurch), "Rome")
        assertEquals(s1, s2)
    }

    @Test
    fun `two Success states with different locations are not equal`() {
        val s1 = ChurchFinderSheetState.Success(emptyList(), "Rome")
        val s2 = ChurchFinderSheetState.Success(emptyList(), "Berlin")
        assertNotEquals(s1, s2)
    }

    // ── when-exhaustiveness ───────────────────────────────────────────────────

    @Test
    fun `when expression covers all four states without else branch`() {
        val states: List<ChurchFinderSheetState> = listOf(
            ChurchFinderSheetState.Idle,
            ChurchFinderSheetState.Loading,
            ChurchFinderSheetState.Success(emptyList(), "X"),
            ChurchFinderSheetState.Error("e"),
        )

        val labels = states.map { state ->
            when (state) {
                is ChurchFinderSheetState.Idle -> "idle"
                is ChurchFinderSheetState.Loading -> "loading"
                is ChurchFinderSheetState.Success -> "success"
                is ChurchFinderSheetState.Error -> "error"
            }
        }

        assertEquals(listOf("idle", "loading", "success", "error"), labels)
    }
}
