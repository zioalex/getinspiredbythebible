package org.voxquieta.app.utils

import org.junit.Assert.assertEquals
import org.junit.Test

class LegalUrlsTest {

    private val base = "https://voxquieta.org"

    @Test
    fun `webLocaleFor strips region tag`() {
        assertEquals("en", webLocaleFor("en-US"))
        assertEquals("pt", webLocaleFor("pt_BR"))
    }

    @Test
    fun `webLocaleFor maps chinese variants to zh`() {
        assertEquals("zh", webLocaleFor("zh-Hans"))
        assertEquals("zh", webLocaleFor("zh-Hant"))
        assertEquals("zh", webLocaleFor("zh"))
    }

    @Test
    fun `webLocaleFor falls back to en for unsupported`() {
        assertEquals("en", webLocaleFor("ja"))
        assertEquals("en", webLocaleFor("xx-YY"))
        assertEquals("en", webLocaleFor(""))
    }

    @Test
    fun `privacy and terms urls include locale segment`() {
        assertEquals("$base/it/privacy", privacyUrl("it", base))
        assertEquals("$base/de/terms", termsUrl("de-AT", base))
    }

    @Test
    fun `trailing slash on base is normalized`() {
        assertEquals("$base/en/privacy", privacyUrl("en-US", "$base/"))
    }
}
