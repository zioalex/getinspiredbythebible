package org.voxquieta.app.components

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.Parameterized
import org.voxquieta.app.domain.models.Message
import org.voxquieta.app.domain.models.Verse
import org.voxquieta.app.presentation.components.CitedRef
import org.voxquieta.app.presentation.components.citedVerses
import org.voxquieta.app.presentation.components.parseCitedRef
import org.voxquieta.app.presentation.components.referencedVerses

private fun v(book: String, chapter: Int, verse: Int, localized: String? = null) =
    Verse(book = book, chapter = chapter, verse = verse, text = "t", localizedBook = localized)

private fun msg(verses: List<Verse>, vararg cited: String) = Message(
    id = "m",
    role = Message.Role.ASSISTANT,
    content = "unused",
    verses = verses,
    versesCited = cited.toList(),
)

/** BITB-166: exact book/chapter/verse matching of server versesCited, across all 11 languages. */
@RunWith(Parameterized::class)
class CitedVerseMatchingTest(
    private val lang: String,
    private val localizedBook: String,
    private val localizedCitation: String,
    private val localizedRange: String,
) {
    companion object {
        @JvmStatic
        @Parameterized.Parameters(name = "{0}")
        fun data(): Collection<Array<String>> = listOf(
            arrayOf("en", "John", "John 3:16", "John 3:16–17"),
            arrayOf("it", "Giovanni", "Giovanni 3:16", "Giovanni 3:16–17"),
            arrayOf("de", "Johannes", "Johannes 3,16", "Johannes 3,16–17"),
            arrayOf("es", "Juan", "Juan 3:16", "Juan 3:16–17"),
            arrayOf("fr", "Jean", "Jean 3:16", "Jean 3:16–17"),
            arrayOf("pt", "João", "João 3:16", "João 3:16–17"),
            arrayOf(
                "ar", "يوحنا",
                "يوحنا ٣:١٦",
                "يوحنا ٣:١٦–١٧",
            ),
            arrayOf("ru", "Иоанн", "Иоанн 3:16", "Иоанн 3:16–17"),
            arrayOf("zh", "约翰福音", "约翰福音 3:16", "约翰福音3:16–17"),
            arrayOf(
                "hi", "यूहन्ना",
                "यूहन्ना ३:१६",
                "यूहन्ना ३:१६–१७",
            ),
            arrayOf("ko", "요한복음", "요한복음 3:16", "요한복음 3:16–17"),
        )
    }

    private fun johnVerses() = listOf(
        v("John", 3, 1, localizedBook),
        v("John", 3, 16, localizedBook),
        v("John", 3, 17, localizedBook),
        v("John", 3, 160, localizedBook),
    )

    private fun panel(vararg cited: String) =
        referencedVerses(johnVerses(), listOf(msg(emptyList(), *cited)))

    @Test
    fun `english John 3 16 returns only 3 16`() {
        assertEquals(listOf(16), panel("John 3:16").map { it.verse })
        assertEquals(listOf(16), citedVerses(msg(johnVerses(), "John 3:16")).map { it.verse })
    }

    @Test
    fun `localized citation returns only 3 16`() {
        assertEquals(listOf(16), panel(localizedCitation).map { it.verse })
        assertEquals(listOf(16), citedVerses(msg(johnVerses(), localizedCitation)).map { it.verse })
    }

    @Test
    fun `en dash range returns 16 and 17 but not 1`() {
        assertEquals(listOf(16, 17), panel("John 3:16–17").map { it.verse })
        assertEquals(listOf(16, 17), panel(localizedRange).map { it.verse })
        assertEquals(listOf(16, 17), citedVerses(msg(johnVerses(), localizedRange)).map { it.verse })
    }

    @Test
    fun `traditional chinese citation matches simplified book`() {
        if (lang != "zh") return
        assertEquals(listOf(16), panel("約翰福音 3:16").map { it.verse })
        assertEquals(listOf(16), panel("约翰福音3:16").map { it.verse })
    }
}

class CitedVerseMatchingEdgeCasesTest {
    @Test
    fun `Romans 8 28-30 matches 28 29 30 not 8 2 or 8 31`() {
        val all = listOf(2, 28, 29, 30, 31).map { v("Romans", 8, it) }
        val result = referencedVerses(all, listOf(msg(emptyList(), "Romans 8:28-30")))
        assertEquals(listOf(28, 29, 30), result.map { it.verse })
    }

    @Test
    fun `1 John 3 16 does not match John 3 16`() {
        val all = listOf(v("John", 3, 16))
        assertTrue(referencedVerses(all, listOf(msg(emptyList(), "1 John 3:16"))).isEmpty())
        val all2 = listOf(v("1 John", 3, 16))
        assertEquals(1, referencedVerses(all2, listOf(msg(emptyList(), "1 John 3:16"))).size)
    }

    @Test
    fun `comma separator John 3 comma 16`() {
        val all = listOf(v("John", 3, 1), v("John", 3, 16))
        assertEquals(listOf(16), referencedVerses(all, listOf(msg(emptyList(), "John 3,16"))).map { it.verse })
    }

    @Test
    fun `chapter-only citation matches nothing and citedVerses falls back to all`() {
        val all = listOf(v("John", 3, 1), v("John", 3, 16))
        assertTrue(referencedVerses(all, listOf(msg(emptyList(), "John 3"))).isEmpty())
        assertEquals(all, citedVerses(msg(all, "John 3")))
    }

    @Test
    fun `parseCitedRef cases`() {
        assertEquals(CitedRef("John", 3, 16, 16), parseCitedRef("John 3:16"))
        assertEquals(CitedRef("John", 3, 16, 17), parseCitedRef("John 3:16-17"))
        assertEquals(CitedRef("John", 3, 16, 17), parseCitedRef("John 3:16–17"))
        assertEquals(CitedRef("1 John", 3, 16, 16), parseCitedRef("1 John 3:16"))
        assertEquals(CitedRef("Johannes", 3, 16, 16), parseCitedRef("Johannes 3,16"))
        assertEquals(CitedRef("约翰福音", 3, 16, 16), parseCitedRef("约翰福音3:16"))
        assertEquals(CitedRef("يوحنا", 3, 16, 16), parseCitedRef("يوحنا ٣:١٦"))
        // Reversed range degrades to the start verse only.
        assertEquals(CitedRef("John", 3, 17, 17), parseCitedRef("John 3:17-16"))
        assertNull(parseCitedRef("John 3"))
        assertNull(parseCitedRef(""))
        assertNull(parseCitedRef("garbage"))
    }
}
