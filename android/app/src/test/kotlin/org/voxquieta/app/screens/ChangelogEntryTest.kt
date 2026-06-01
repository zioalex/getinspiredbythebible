package org.voxquieta.app.screens

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.voxquieta.app.presentation.screens.ChangelogEntry

class ChangelogEntryTest {

    @Test
    fun `ChangelogEntry stores body with markdown links unchanged`() {
        val body = "* Fix crash ([#123](https://github.com/org/repo/pull/123))"
        val entry = ChangelogEntry(version = "1.0.0", date = "2024-01-01", body = body)
        assertEquals(body, entry.body)
    }

    @Test
    fun `ChangelogEntry body preserves raw markdown syntax`() {
        val body = "### Fixed\n\n* Update deps ([#456](https://github.com/org/repo/pull/456))"
        val entry = ChangelogEntry(version = "2.0.0", date = "2024-06-01", body = body)
        assertTrue(entry.body.contains("[#456](https://github.com/org/repo/pull/456)"))
    }

    @Test
    fun `ChangelogEntry with blank date is valid`() {
        val entry = ChangelogEntry(version = "0.1.0", date = "", body = "Initial release")
        assertTrue(entry.date.isBlank())
        assertEquals("Initial release", entry.body)
    }

    @Test
    fun `ChangelogEntry data class equality holds`() {
        val a = ChangelogEntry("1.0.0", "2024-01-01", "body")
        val b = ChangelogEntry("1.0.0", "2024-01-01", "body")
        assertEquals(a, b)
    }
}
