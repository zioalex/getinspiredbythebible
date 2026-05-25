package org.voxquieta.app.presentation.screens

/**
 * Pure (Compose-free) policy describing which actions/entries are visible in the
 * Chat screen's top app bar and navigation drawer.
 *
 * The Chat screen's top-right `actions` row exposes the Bible version chip, the
 * language picker, the "+ New chat" shortcut, and (when there are related verses)
 * the verses panel. All other actions — clearing the current conversation and
 * opening Settings — live behind the hamburger menu on the left.
 *
 * Keeping this policy in a small, pure data class makes the visibility rules
 * trivially unit-testable on the JVM (no Compose / instrumented test harness
 * required), in line with the repository convention of placing screen-level
 * structural tests under `app/src/test/.../screens/` (see e.g.
 * [LanguageOptionsTest]).
 */
internal data class ChatTopBarPolicy(
    /** True when the verses panel icon (with badge) should appear in the top app bar. */
    val showVersesPanelInTopBar: Boolean,
    /** True when the "Clear conversation" entry should appear in the drawer. */
    val showClearConversationInDrawer: Boolean,
)

/**
 * Build the [ChatTopBarPolicy] for the current chat state.
 *
 * Rules (must stay in sync with [ChatScreen]):
 *  - The Bible version chip, the language picker, and the "+ New chat" button
 *    are *always* in the top app bar — they are not state-dependent and
 *    therefore not represented in this policy object.
 *  - The verses panel icon is shown in the top bar only when at least one
 *    related verse has been collected for the current conversation.
 *  - The "Clear conversation" drawer entry is shown only when the current
 *    conversation has at least one message.
 *  - "New chat" is also available in the drawer; Settings is drawer-only.
 */
internal fun chatTopBarPolicy(
    versesCount: Int,
    messagesCount: Int,
): ChatTopBarPolicy = ChatTopBarPolicy(
    showVersesPanelInTopBar = versesCount > 0,
    showClearConversationInDrawer = messagesCount > 0,
)

/**
 * Returns the display ID for the translation chip, or `null` when no translation
 * has been selected (i.e. the backend should auto-detect from the user's locale).
 *
 * The composable resolves `null` to the localised `translation_picker_title` string
 * ("Bible Version"), matching the web placeholder introduced in #551.
 *
 * @param preferredTranslation the raw value stored in [TranslationPreferences] —
 *   an empty string means "no preference / auto-detect".
 */
internal fun translationChipLabel(preferredTranslation: String): String? =
    if (preferredTranslation.isBlank()) null else preferredTranslation.uppercase()
