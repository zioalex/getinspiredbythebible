package org.voxquieta.app.screens

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.voxquieta.app.presentation.components.WhatsNewEntry
import org.voxquieta.app.presentation.components.parseWhatsNew
import org.voxquieta.app.presentation.components.pickWhatsNewNotes
import org.voxquieta.app.presentation.components.shouldShowWhatsNew

/**
 * Unit tests for [shouldShowWhatsNew], the version-tracking logic behind the
 * "What's New" bottom sheet (BITB-058): shown once per update, never on a
 * fresh install, never repeated for the same version.
 */
class WhatsNewTest {

    private val current = 42

    @Test
    fun `fresh install (stored -1) does not show`() {
        assertFalse(shouldShowWhatsNew(storedVersionCode = -1, currentVersionCode = current))
    }

    @Test
    fun `same version does not show`() {
        assertFalse(shouldShowWhatsNew(storedVersionCode = current, currentVersionCode = current))
    }

    @Test
    fun `updated (stored is current minus 1) shows`() {
        assertTrue(shouldShowWhatsNew(storedVersionCode = current - 1, currentVersionCode = current))
    }

    @Test
    fun `much older stored version shows`() {
        assertTrue(shouldShowWhatsNew(storedVersionCode = 1, currentVersionCode = current))
    }

    @Test
    fun `stored newer than current does not show (downgrade guard)`() {
        assertFalse(shouldShowWhatsNew(storedVersionCode = current + 1, currentVersionCode = current))
    }

    // BITB-175: the sheet shows curated release-notes/<version>/<locale>.md, not the raw
    // CHANGELOG; the BITB-168 support-note marker was retired with it.

    private val notes = mapOf("en" to "- Read aloud keeps going", "it" to "- La lettura continua")

    @Test
    fun `parses the generated asset`() {
        val raw = """[{"version":"1.63.0","date":"2026-12-01","body":"- Read aloud keeps going",""" +
            """"notes":{"en":"- Read aloud keeps going","it":"- La lettura continua"},"extra":1}]"""
        assertEquals(WhatsNewEntry("1.63.0", "2026-12-01", notes.getValue("en"), notes), parseWhatsNew(raw))
    }

    @Test
    fun `empty, malformed or text-less asset means no sheet`() {
        assertNull(parseWhatsNew("[]"))
        assertNull(parseWhatsNew("not json"))
        assertNull(parseWhatsNew("""[{"version":"1.63.0","body":"  "}]"""))
    }

    @Test
    fun `notes follow the UI language and fall back to English`() {
        val entry = WhatsNewEntry("1.63.0", body = notes.getValue("en"), notes = notes)
        assertEquals("- La lettura continua", pickWhatsNewNotes(entry, "it"))
        assertEquals("- Read aloud keeps going", pickWhatsNewNotes(entry, "ko"))
        assertEquals("- only body", pickWhatsNewNotes(WhatsNewEntry("1", body = "- only body"), "de"))
    }
}
