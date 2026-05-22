package org.voxquieta.app.components

import org.junit.Assert.assertTrue
import org.junit.Test
import org.voxquieta.app.presentation.components.DEFAULT_SHOW_REFERENCED

/**
 * Guard test for BITB-034. Asserts the default filter constant so that any future
 * refactor that flips the default from "Cited" to "All Related" is caught by CI
 * immediately, without requiring the Compose runtime.
 */
class VersesPanelDefaultsTest {

    @Test
    fun `DEFAULT_SHOW_REFERENCED is true so the panel opens on the Cited filter`() {
        assertTrue(
            "VersesPanel must open on the 'Cited' filter by default (DEFAULT_SHOW_REFERENCED)",
            DEFAULT_SHOW_REFERENCED,
        )
    }
}
