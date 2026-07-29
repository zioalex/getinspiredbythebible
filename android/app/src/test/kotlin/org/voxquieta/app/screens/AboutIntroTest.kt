package org.voxquieta.app.screens

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.voxquieta.app.resolveLaunchModals

/**
 * Unit tests for [resolveLaunchModals], the priority logic behind the About intro
 * sheet (BITB-082) and its collision with the "What's New" sheet (BITB-058): the two
 * must never both fire on the same cold start, and About intro takes priority — What's
 * New defers to the next launch rather than being marked seen now.
 */
class AboutIntroTest {

    private val current = 42

    @Test
    fun `about intro not yet seen wins, even when What's New would also be eligible`() {
        val decision = resolveLaunchModals(
            aboutIntroSeen = false,
            storedVersionCode = current - 1,
            currentVersionCode = current,
        )
        assertTrue(decision.showAboutIntro)
        assertFalse(decision.showWhatsNew)
    }

    @Test
    fun `about intro not yet seen defers What's New — version is not marked seen`() {
        val decision = resolveLaunchModals(
            aboutIntroSeen = false,
            storedVersionCode = current - 1,
            currentVersionCode = current,
        )
        assertFalse(
            "the deferred What's New must re-evaluate next launch, so the version must " +
                "not be marked seen on this run",
            decision.shouldMarkVersionSeen,
        )
    }

    @Test
    fun `about intro already seen — What's New proceeds normally when eligible`() {
        val decision = resolveLaunchModals(
            aboutIntroSeen = true,
            storedVersionCode = current - 1,
            currentVersionCode = current,
        )
        assertFalse(decision.showAboutIntro)
        assertTrue(decision.showWhatsNew)
        assertTrue(decision.shouldMarkVersionSeen)
    }

    @Test
    fun `about intro already seen and What's New not eligible — neither shows`() {
        val decision = resolveLaunchModals(
            aboutIntroSeen = true,
            storedVersionCode = current,
            currentVersionCode = current,
        )
        assertFalse(decision.showAboutIntro)
        assertFalse(decision.showWhatsNew)
        assertFalse(decision.shouldMarkVersionSeen)
    }

    @Test
    fun `fresh install (stored -1) with about intro already seen does not show What's New`() {
        val decision = resolveLaunchModals(
            aboutIntroSeen = true,
            storedVersionCode = -1,
            currentVersionCode = current,
        )
        assertFalse(decision.showAboutIntro)
        assertFalse(decision.showWhatsNew)
        assertTrue(
            "fresh install still records the current version even with no sheet shown",
            decision.shouldMarkVersionSeen,
        )
    }

    @Test
    fun `downgrade guard still holds when about intro has been seen`() {
        val decision = resolveLaunchModals(
            aboutIntroSeen = true,
            storedVersionCode = current + 1,
            currentVersionCode = current,
        )
        assertFalse(decision.showWhatsNew)
    }
}
