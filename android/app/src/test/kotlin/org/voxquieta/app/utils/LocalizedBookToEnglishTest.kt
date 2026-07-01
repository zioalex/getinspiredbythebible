package org.voxquieta.app.utils

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Guards the bundled fallback book-name map against silent drift from the web frontend map
 * (frontend/src/lib/verseExtraction.ts LOCALIZED_BOOK_TO_ENGLISH), which is the parity source.
 * If you intentionally change the map on one platform, update the other and this count.
 */
class LocalizedBookToEnglishTest {

    @Test
    fun `entry count matches the web map`() {
        // 720 localized-name entries at parity with the web map.
        assertEquals(720, LOCALIZED_BOOK_TO_ENGLISH.size)
    }

    @Test
    fun `maps to exactly the 66 canonical English books`() {
        assertEquals(66, LOCALIZED_BOOK_TO_ENGLISH.values.toSet().size)
    }

    @Test
    fun `keys and values are all lowercase`() {
        for ((k, v) in LOCALIZED_BOOK_TO_ENGLISH) {
            assertEquals("key not lowercased: $k", k.lowercase(), k)
            assertEquals("value not lowercased: $v", v.lowercase(), v)
        }
    }

    @Test
    fun `resolves the key English aliases used by the reported bug`() {
        assertEquals("psalms", LOCALIZED_BOOK_TO_ENGLISH["psalm"])
        assertEquals("psalms", LOCALIZED_BOOK_TO_ENGLISH["salmos"])
        assertEquals("isaiah", LOCALIZED_BOOK_TO_ENGLISH["isaías"])
        assertTrue(LOCALIZED_BOOK_TO_ENGLISH.containsKey("song of solomon"))
    }
}
