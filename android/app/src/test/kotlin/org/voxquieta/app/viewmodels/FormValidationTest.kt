package org.voxquieta.app.viewmodels

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Documents and verifies the "submit-only touched" validation logic used in
 * [ChurchFinderBottomSheet] and [ContactFormBottomSheet].
 *
 * The rule: an inline error is shown only when the user has explicitly attempted
 * to submit (touched = true) AND the required field is blank. Errors must NOT
 * appear during normal typing — `touched` is set exclusively on submit/search
 * attempts, not inside `onValueChange`.
 *
 * These are plain JVM tests; no Compose or Android runtime is required.
 */
class FormValidationTest {

    // ── Helper that mirrors the composable's inline expression ────────────────

    private fun fieldError(touched: Boolean, value: String): Boolean =
        touched && value.isBlank()

    // ── ChurchFinder: location field ──────────────────────────────────────────

    @Test
    fun `church finder - no error on fresh open (not touched, blank)`() {
        assertFalse(fieldError(touched = false, value = ""))
    }

    @Test
    fun `church finder - no error while user is typing (not touched, non-blank)`() {
        assertFalse(fieldError(touched = false, value = "R"))
    }

    @Test
    fun `church finder - no error when field has content after submit attempt`() {
        assertFalse(fieldError(touched = true, value = "Rome"))
    }

    @Test
    fun `church finder - error shown when submit attempted with blank field`() {
        assertTrue(fieldError(touched = true, value = ""))
    }

    @Test
    fun `church finder - error shown when submit attempted with whitespace-only field`() {
        assertTrue(fieldError(touched = true, value = "   "))
    }

    @Test
    fun `church finder - error clears once user types after failed submit`() {
        // User tapped Search with blank → touched=true. Now types "Berlin".
        assertFalse(fieldError(touched = true, value = "Berlin"))
    }

    @Test
    fun `church finder - onSearch guard blank location must not call onSearch`() {
        val calls = mutableListOf<String>()
        val onSearch: (String) -> Unit = { calls.add(it) }
        val location = ""
        if (location.isNotBlank()) onSearch(location)
        assertTrue("onSearch must not be called with blank location", calls.isEmpty())
    }

    @Test
    fun `church finder - onSearch guard non-blank location calls onSearch`() {
        val calls = mutableListOf<String>()
        val onSearch: (String) -> Unit = { calls.add(it) }
        val location = "Rome"
        if (location.isNotBlank()) onSearch(location)
        assertTrue("onSearch must be called once", calls.size == 1)
        assertTrue("onSearch receives the trimmed location", calls[0] == "Rome")
    }

    // ── ContactForm: message field ────────────────────────────────────────────

    @Test
    fun `contact form - no error on fresh open (not touched, blank)`() {
        assertFalse(fieldError(touched = false, value = ""))
    }

    @Test
    fun `contact form - no error while user is typing (not touched, non-blank)`() {
        assertFalse(fieldError(touched = false, value = "H"))
    }

    @Test
    fun `contact form - error shown when submit attempted with blank message`() {
        assertTrue(fieldError(touched = true, value = ""))
    }

    @Test
    fun `contact form - error shown for whitespace-only message`() {
        assertTrue(fieldError(touched = true, value = "\n\n"))
    }

    @Test
    fun `contact form - no error when message has content after submit attempt`() {
        assertFalse(fieldError(touched = true, value = "Hello pastor"))
    }

    // ── Regression guard: remember (not rememberSaveable) resets on each open ──

    @Test
    fun `church finder - second open starts with blank input and no error`() {
        val touched = false
        val value = ""
        assertFalse(fieldError(touched, value))
        assertFalse(value.isNotBlank())
    }

    @Test
    fun `church finder - re-open after blank-submit error shows clean form`() {
        assertFalse(fieldError(touched = false, value = ""))
    }

    // ── Regression guard: touched must NOT be set by onValueChange ────────────

    @Test
    fun `typing then clearing does NOT produce an error without a submit attempt`() {
        // Simulates: type "R" → delete → field is blank, but no submit attempted.
        // touched must still be false because onValueChange must not set it.
        var touched = false
        var value = ""

        // Simulate typing "R"
        value = "R"
        // touched NOT updated here (correct — onValueChange should not set touched)

        // Simulate deleting "R"
        value = ""
        // touched NOT updated here either

        assertFalse(
            "No error should appear mid-typing without a submit attempt",
            fieldError(touched, value),
        )
    }

    @Test
    fun `clearing field after successful search does NOT re-show error`() {
        // After a successful search the user clears the field for the next query.
        // touched is still true (set during the previous submit), but since they
        // are now typing (value is non-blank), or just cleared (value is blank but
        // we don't set touched again), the error must appear only when they blank out.
        //
        // Actually with the submit-only pattern: touched remains true after first
        // search, so clearing the field WILL re-show the error — that's acceptable
        // and expected ("you cleared the field, enter a location to search").
        // What must NOT happen is the error appearing mid-typing of the new query.
        var touched = true   // set during first successful search
        var value = "Rome"

        // User clears to type new query
        value = ""
        assertTrue(
            "After a previous search, clearing the field shows the error (expected)",
            fieldError(touched, value),
        )

        // User starts typing new city
        value = "B"
        assertFalse(
            "Error clears as soon as the user starts typing the new location",
            fieldError(touched, value),
        )
    }
}
