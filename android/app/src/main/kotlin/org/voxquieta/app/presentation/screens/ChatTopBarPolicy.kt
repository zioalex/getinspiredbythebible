package org.voxquieta.app.presentation.screens

/**
 * Pure (Compose-free) policy describing which actions/entries are visible in the
 * Chat screen's top app bar and navigation drawer.
 *
 * The Chat screen's top-right `actions` row exposes only the "+ New chat" shortcut
 * and (when there are related verses) the verses panel. Everything else — including
 * the Bible-version picker, the language picker, clearing the current conversation,
 * and opening Settings — lives behind the hamburger menu (drawer) on the left.
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
 *  - The "+ New chat" button is *always* in the top app bar — it is not
 *    state-dependent and therefore not represented in this policy object.
 *  - The verses panel icon is shown in the top bar only when at least one
 *    related verse has been collected for the current conversation.
 *  - The "Clear conversation" drawer entry is shown only when the current
 *    conversation has at least one message.
 *  - "New chat", the language picker, the Bible-version picker, "Search a
 *    community", and Settings are also available in the drawer, unconditionally.
 */
internal fun chatTopBarPolicy(
    versesCount: Int,
    messagesCount: Int,
): ChatTopBarPolicy = ChatTopBarPolicy(
    showVersesPanelInTopBar = versesCount > 0,
    showClearConversationInDrawer = messagesCount > 0,
)
