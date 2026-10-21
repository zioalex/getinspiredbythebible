package org.voxquieta.app.screens

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.voxquieta.app.presentation.components.shouldShowSupportNote
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

    @Test
    fun `support note shows when latest body carries the BITB-168 marker`() {
        assertTrue(shouldShowSupportNote("- Support Vox Quieta from the menu (BITB-168)"))
    }

    @Test
    fun `support note hidden for unrelated body`() {
        assertFalse(shouldShowSupportNote("- Fixed a crash (BITB-170)"))
    }

    @Test
    fun `support note hidden for empty body`() {
        assertFalse(shouldShowSupportNote(""))
    }
}
