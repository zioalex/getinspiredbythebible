package org.voxquieta.app.utils

import org.junit.Assert.assertEquals
import org.junit.Test

class DonateUrlTest {

    @Test
    fun `appends ref with question mark when base has no query`() {
        assertEquals(
            "https://ko-fi.com/voxquieta?ref=android-drawer",
            donateUrl(DonateRef.DRAWER, "https://ko-fi.com/voxquieta"),
        )
    }

    @Test
    fun `appends ref with ampersand when base already has a query`() {
        assertEquals(
            "https://example.org/d?x=1&ref=android-settings",
            donateUrl(DonateRef.SETTINGS, "https://example.org/d?x=1"),
        )
    }

    @Test
    fun `ref values are stable`() {
        assertEquals("android-drawer", DonateRef.DRAWER.value)
        assertEquals("android-settings", DonateRef.SETTINGS.value)
    }
}
