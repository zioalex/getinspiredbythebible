package org.voxquieta.app.presentation.components

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.onNodeWithText
import org.junit.Test
import org.voxquieta.app.domain.models.Verse
import org.voxquieta.app.presentation.viewmodels.ChapterSheetState
import org.voxquieta.app.testing.ComposeTestHarness

/**
 * Robolectric-backed Compose UI tests for [InlineVerseCard] (the cards shown under an
 * assistant answer). Unlike [VerseChip], the inline card must show the actual verse TEXT so
 * the user can read it without opening the Verses panel — these tests guard that.
 *
 * Runs under the `testDebugCompose` task / `android-compose-tests.yml` lane.
 */
class InlineVerseCardTest : ComposeTestHarness() {

    private fun mountCard(verse: Verse) = setContentThemed {
        InlineVerseCard(
            verse = verse,
            preferredTranslation = "schlachter",
            chapterState = ChapterSheetState.Idle,
            onLoadChapter = { _, _, _ -> },
            onDismissSheet = {},
        )
    }

    @Test
    fun `renders the reference and the actual verse text`() {
        mountCard(
            Verse(
                book = "Proverbs",
                chapter = 17,
                verse = 17,
                text = "Ein Freund liebt jederzeit, und in der Not wird er als Bruder geboren.",
                translation = "schlachter",
                localizedBook = "Sprüche",
            ),
        )

        // Reference uses the localized book name when present.
        composeRule.onNodeWithText("Sprüche 17:17").assertIsDisplayed()
        // The actual verse text is visible without any extra tap.
        composeRule
            .onNodeWithText("Ein Freund liebt jederzeit, und in der Not wird er als Bruder geboren.")
            .assertIsDisplayed()
        // Translation badge.
        composeRule.onNodeWithText("SCHLACHTER").assertIsDisplayed()
    }

    @Test
    fun `renders reference even when verse text is blank`() {
        mountCard(
            Verse(book = "John", chapter = 3, verse = 16, text = "", translation = "kjv"),
        )
        composeRule.onNodeWithText("John 3:16").assertIsDisplayed()
    }
}
