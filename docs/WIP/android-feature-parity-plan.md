# Android Feature-Parity Plan

**Created:** 2026-03-12
**Status:** Awaiting product-owner review
**Source of truth for prioritisation:** `docs/BACKLOG.md`

---

## Background

A full gap analysis was conducted between the web frontend (`frontend/`) and the Android app (`android/`) as of 2026-03-12.
The Android app already has several features the web lacks (Room persistence, conversation history, theme toggle, debug log export).
This plan covers only the gaps where the **web is ahead of Android**.

---

## How to read this plan

| Field | Meaning |
|---|---|
| **Gap #** | Sequential reference number |
| **Story** | User-value framing |
| **Web does** | Current web behaviour |
| **Android does** | Current Android behaviour |
| **What to build** | Concrete engineering work |
| **Affected files** | Non-exhaustive list of files that change |
| **Size** | S < 4 h · M 1–2 days · L 3–5 days · XL 1–2 weeks |
| **Depends on** | Must be done before this story |

---

## Milestone P0 — API contract correctness (ship immediately, no visible UI change)

These are silent bugs that cause incorrect or missing data from the backend.

---

### GAP-001 · Add `include_search` and `session_id` to `ChatRequestDto`

**Size:** S
**Depends on:** nothing

**Story:** As a user on Android, I want the backend to return scripture context and track my session, so that verse results and DAU/MAU analytics work the same as on web.

**Web does:**
`frontend/src/lib/api.ts` sends `include_search: true` and `session_id: <uuid>` in every chat request body.

**Android does:**
`ChatRequestDto` only has `message`, `conversation_id`, `translation`. No `include_search` or `session_id`.

**What to build:**

1. Add `include_search: Boolean = true` to `ChatRequestDto` (data class, `@SerializedName("include_search")`)
2. Add `session_id: String` to `ChatRequestDto`
3. Generate `session_id` as a UUID that persists for the lifetime of the app process (or `SharedPreferences` for DAU/MAU parity with web)
4. Pass both fields in `ChatRepositoryImpl.streamChat()`

**Affected files:**

- `data/remote/models/ChatRequestDto.kt`
- `data/repository/ChatRepositoryImpl.kt`
- `domain/repository/ChatRepository.kt` (interface — add sessionId param if needed)
- `presentation/viewmodels/ChatViewModel.kt` (pass sessionId)

---

### GAP-002 · Receive streaming metadata (`message_id`, `model`, `provider`, `detected_translation`, `scripture_context`)

**Size:** M
**Depends on:** GAP-001 (backend won't return `scripture_context` without `include_search: true`)

**Story:** As an Android developer, I want the streaming parser to handle all SSE chunk types, so that message IDs, model info, and scripture context arrive at the right time (before text streaming begins) rather than only on `done: true`.

**Web does:**
`StreamChunk` can be `type: "metadata" | "content" | "error"`. The `metadata` event carries `message_id`, `provider`, `model`, `detected_translation`, `translation_info`, and `scripture_context` (with `verses` and `passages`) — and arrives **before any content chunks**.

**Android does:**
`StreamChunkDto` has only `content: String?`, `done: Boolean`, `verses: List<VerseDto>?`. The `EventSourceParser` only reads `data:` lines; it never reads a `type:` field. Verses only appear in the final `done: true` chunk.

**What to build:**

1. Extend `StreamChunkDto` with `type: String?`, `message_id: String?`, `model: String?`, `provider: String?`, `detected_translation: String?`, `translation_info: TranslationInfoDto?`, `scripture_context: ScriptureContextDto?`
2. Add `TranslationInfoDto`, `ScriptureContextDto` data classes
3. Update `EventSourceParser` to detect `event: metadata` lines and parse accordingly
4. Surface `message_id` on the `Message` domain model (needed by GAP-003 feedback)
5. Deliver `scripture_context` verses to the UI as soon as the metadata chunk arrives (not just on done)

**Affected files:**

- `data/remote/models/ChatResponseDto.kt`
- `data/remote/models/TranslationInfoDto.kt` (new)
- `data/remote/models/ScriptureContextDto.kt` (new)
- `data/remote/EventSourceParser.kt`
- `data/repository/ChatRepositoryImpl.kt`
- `domain/models/Message.kt` (add `messageId: String?`)
- `presentation/viewmodels/ChatViewModel.kt`

---

## Milestone P1 — High-value user-facing features

---

### GAP-003 · Message feedback (thumbs up / thumbs down)

**Size:** M
**Depends on:** GAP-002 (needs `message_id` in streaming metadata)

**Story:** As a user, I want to rate assistant messages with a thumbs up or down, so that I can give feedback on the quality of Bible answers.

**Web does:**
Every assistant message shows 👍 / 👎 buttons. Tapping opens `FeedbackModal` with an optional comment field and a privacy notice. On submit it calls `POST /api/v1/feedback` with `{ message_id, rating, comment }`.

**Android does:**
No feedback UI. `Message` domain model has no `messageId`. `BibleApiService` has no feedback endpoint.

**What to build:**

1. Add `POST /api/v1/feedback` to `BibleApiService` with `FeedbackRequest` / `FeedbackResponse` DTOs
2. Add `FeedbackRepository` + `SubmitFeedbackUseCase`
3. Add thumbs up/down icon buttons to `ChatMessageItem` (only for assistant messages)
4. Add `FeedbackBottomSheet` composable (rating pre-filled, optional comment, privacy notice, submit button)
5. Wire `ChatViewModel.submitFeedback(messageId, rating, comment)`
6. Add string resources: `feedback_helpful`, `feedback_not_helpful`, `feedback_comment_hint`, `feedback_thank_you`, `feedback_privacy_notice`

**Affected files:**

- `data/remote/api/BibleApiService.kt`
- `data/remote/models/FeedbackDto.kt` (new)
- `data/repository/FeedbackRepository.kt` (new)
- `domain/usecases/SubmitFeedbackUseCase.kt` (new)
- `presentation/components/ChatMessageItem.kt`
- `presentation/components/FeedbackBottomSheet.kt` (new)
- `presentation/viewmodels/ChatViewModel.kt`
- `res/values/strings.xml` + all locale files

---

### GAP-004 · Markdown rendering

**Size:** M
**Depends on:** nothing

**Story:** As a user, I want assistant messages to render bold text, bullet lists, and scripture blockquotes correctly, so that the answer is easy to read rather than showing raw `**` and `>` symbols.

**Web does:**
`ReactMarkdown` with custom components: bold, italic, blockquotes (styled as scripture), unordered/ordered lists, inline code displayed as verse references.

**Android does:**
`ChatMessageItem` uses a plain `Text(message.content)` composable — raw markdown symbols are visible.

**What to build:**

1. Add `io.noties.markwon:markwon-core` (and optionally `markwon-ext-strikethrough`, `markwon-ext-tables`) to `build.gradle.kts`
2. Create `MarkdownText` composable wrapping Markwon's `AndroidView` with `TextView`
3. Style blockquotes with a left amber border (matching web scripture style)
4. Replace `Text(message.content)` in `ChatMessageItem` with `MarkdownText(message.content)`
5. Unit test: assert `**bold**` renders without raw asterisks

**Affected files:**

- `app/build.gradle.kts`
- `presentation/components/MarkdownText.kt` (new)
- `presentation/components/ChatMessageItem.kt`

---

### GAP-005 · Share message

**Size:** S
**Depends on:** nothing

**Story:** As a user, I want to share an assistant's Bible answer via WhatsApp, copy to clipboard, or any other app, so that I can spread inspirational scripture to friends.

**Web does:**
`ShareMenu` component on every assistant message offers: copy to clipboard, WhatsApp, Twitter/X, Facebook, Bluesky.

**Android does:**
No share UI on messages. `shareDebugLogs()` in `ChatViewModel` uses the Android share sheet but only for debug logs.

**What to build:**

1. Add a share icon button to `ChatMessageItem` (assistant messages only)
2. On tap: use Android `Intent.ACTION_SEND` to invoke the system share sheet with message text
3. Add "Copy to clipboard" as a fallback (long-press or secondary button)
4. String: `share_message`, `copied_to_clipboard`

**Affected files:**

- `presentation/components/ChatMessageItem.kt`
- `presentation/viewmodels/ChatViewModel.kt` (optional: expose shareMessage helper)
- `res/values/strings.xml` + all locale files

---

### GAP-006 · Backend warm-up / cold-start UX

**Size:** S
**Depends on:** nothing

**Story:** As a mobile user, I want the app to tell me when the server is waking up, so that I don't think the app is broken during a cold start.

**Web does:**
On mount, calls `GET /health/ready` polling until `{ ready: true }`. Shows an amber "Server is waking up…" banner while not ready.

**Android does:**
No health check. First API call fails silently or shows a generic error if the container is cold.

**What to build:**

1. Add `GET /health/ready` to `BibleApiService` returning `HealthReadyResponse(ready: Boolean)`
2. `ChatViewModel.init` calls `pollUntilReady()` (retry every 3 s, max 60 s)
3. Expose `isBackendReady: StateFlow<Boolean>` from `ChatViewModel`
4. Add an amber `WarmingUpBanner` composable in `ChatScreen` (shown while `!isBackendReady`)
5. Disable send button while `!isBackendReady`
6. String: `server_warming_up`

**Affected files:**

- `data/remote/api/BibleApiService.kt`
- `data/remote/models/HealthDto.kt` (new)
- `presentation/viewmodels/ChatViewModel.kt`
- `presentation/components/WarmingUpBanner.kt` (new)
- `presentation/screens/ChatScreen.kt`
- `res/values/strings.xml` + all locale files

---

### GAP-007 · "Scroll to bottom" floating button

**Size:** S
**Depends on:** nothing

**Story:** As a user reading a long conversation, I want a "scroll to bottom" button to appear when I scroll up, so that I can jump back to the latest message with one tap.

**Web does:**
A pill button appears when the user has scrolled up during streaming.

**Android does:**
`LazyColumn` auto-scrolls only when `messages.size` changes. No manual scroll-to-bottom button.

**What to build:**

1. Track `LazyListState.firstVisibleItemIndex` in `ChatScreen`
2. Show a `FloatingActionButton` (↓ arrow) when `!isAtBottom`
3. On tap: `coroutineScope.launch { listState.animateScrollToItem(messages.lastIndex) }`

**Affected files:**

- `presentation/screens/ChatScreen.kt`

---

## Milestone P2 — Engagement & discovery features

---

### GAP-008 · Church Finder

**Size:** L
**Depends on:** nothing (standalone feature)

**Story:** As a user who wants to grow in faith, I want to find churches near me after a few exchanges, so that I can connect with a local community.

**Web does:**
After 3+ message exchanges: `ChurchFinderBanner` appears in the input area. After 3–5 exchanges: `ChurchFinderInlinePrompt` appears inline in the chat. Both open `ChurchFinderModal` which calls `POST /api/v1/church/search` with `{ location, radius_km }`.

**Android does:**
No church finder at all. `BibleApiService` has no church search endpoint.

**What to build:**

1. Add `POST /api/v1/church/search` to `BibleApiService` with `ChurchSearchRequest` / `ChurchSearchResponse` DTOs
2. Add `ChurchRepository` + `SearchChurchesUseCase`
3. Track `interactionCount` in `ChatViewModel`; after 3 exchanges emit `showChurchFinderPrompt`
4. Add `ChurchFinderInlineCard` composable (shown in message list after 3–5 exchanges)
5. Add `ChurchFinderBottomSheet` composable with location input, radius picker, results list (name, address, distance, map link)
6. String resources: `church_finder_*` keys matching `frontend/messages/en.json`

**Affected files:**

- `data/remote/api/BibleApiService.kt`
- `data/remote/models/ChurchDto.kt` (new)
- `data/repository/ChurchRepository.kt` (new)
- `domain/usecases/SearchChurchesUseCase.kt` (new)
- `presentation/components/ChurchFinderInlineCard.kt` (new)
- `presentation/components/ChurchFinderBottomSheet.kt` (new)
- `presentation/viewmodels/ChatViewModel.kt`
- `presentation/screens/ChatScreen.kt`
- `res/values/strings.xml` + all locale files

---

### GAP-009 · Contact Form

**Size:** M
**Depends on:** nothing

**Story:** As a user with feedback or a question, I want a contact form in the app, so that I can reach the team without leaving the app.

**Web does:**
A collapsible `ContactForm` at the bottom of the chat with subject, optional email, message fields. Calls `POST /api/v1/feedback/contact`.

**Android does:**
No contact form. `BibleApiService` has no contact endpoint.

**What to build:**

1. Add `POST /api/v1/feedback/contact` to `BibleApiService` with `ContactRequest` / `ContactResponse` DTOs
2. Add `ContactRepository` + `SubmitContactUseCase`
3. Add a "Contact Us" entry in the Settings screen (or a menu item in the chat top bar)
4. Add `ContactFormBottomSheet` composable (subject dropdown, email optional, message, send button)
5. String resources: `contact_*` keys

**Affected files:**

- `data/remote/api/BibleApiService.kt`
- `data/remote/models/ContactDto.kt` (new)
- `data/repository/ContactRepository.kt` (new)
- `domain/usecases/SubmitContactUseCase.kt` (new)
- `presentation/components/ContactFormBottomSheet.kt` (new)
- `presentation/screens/SettingsScreen.kt`
- `res/values/strings.xml` + all locale files

---

### GAP-010 · Verse reference click-to-detail (in message body)

**Size:** M
**Depends on:** GAP-004 (Markdown rendering — verse refs appear as styled spans in markdown)

**Story:** As a user reading an assistant message, I want to tap a verse reference like "John 3:16" in the text to open the full verse, so that I can read it without searching manually.

**Web does:**
`ReactMarkdown` uses a custom `code` renderer that detects verse patterns, renders them as amber clickable spans, and opens `ChapterModal` on click.

**Android does:**
Verse chips below the bubble are tappable (open `VerseBottomSheet`). Verse references inside message text are plain text — not highlighted, not tappable.

**What to build:**

1. In `MarkdownText` (GAP-004), add a custom Markwon span for verse reference patterns (`\b[1-3]?\s?[A-Z][a-z]+\s\d+:\d+(-\d+)?\b`)
2. Apply amber text colour + underline to matched spans
3. On tap: invoke `onVerseRefClick(book, chapter, verse)` callback
4. Wire callback to open existing `VerseBottomSheet`

**Affected files:**

- `presentation/components/MarkdownText.kt`
- `presentation/components/ChatMessageItem.kt`
- `presentation/screens/ChatScreen.kt` (pass callback)

---

### GAP-011 · Verses sidebar / referenced vs. all-related filter

**Size:** M
**Depends on:** GAP-002 (scripture_context arrives in metadata chunk)

**Story:** As a user, I want to see all related verses in a dedicated panel and toggle between "Referenced" and "All Related", so that I can explore the scripture context without scrolling through all messages.

**Web does:**
Right-side panel (desktop) or FAB slide-over (mobile) shows all `relevantVerses` from `scripture_context`. Toggle between "Referenced" (verses cited in response text) and "All Related (N)".

**Android does:**
Verse chips appear per-message below each bubble. No consolidated view, no referenced/all filter.

**What to build:**

1. Add a "Verses" FAB or top-bar icon in `ChatScreen`
2. `VersesPanel` composable: `ModalBottomSheet` listing all verses for the current conversation
3. Segment control: "Referenced" | "All Related"
4. "Referenced" filter: run `extractVerseReferences(messageContent)` regex to determine which verses are cited
5. Wire to `ChatViewModel.currentVerses: StateFlow<List<Verse>>`

**Affected files:**

- `presentation/screens/ChatScreen.kt`
- `presentation/components/VersesPanel.kt` (new)
- `presentation/viewmodels/ChatViewModel.kt`

---

## Milestone P3 — Locale completeness

---

### GAP-012 · Add Russian, Chinese, Hindi, Korean locales to Android

**Size:** S
**Depends on:** nothing (backend + web already support these 4 locales as of BITB-024)

**Story:** As a Russian, Chinese, Hindi, or Korean speaker, I want the Android app UI to be in my language, so that I get the same experience as web users.

**Web does:**
11 locales: en, it, de, es, fr, ar, pt, ru, zh, hi, ko.

**Android does:**
7 locales: en, it, de, es, fr, ar, pt — missing ru, zh, hi, ko.

**What to build:**

1. Create `res/values-ru/strings.xml`, `res/values-zh/strings.xml`, `res/values-hi/strings.xml`, `res/values-ko/strings.xml`
2. Translate all 41+ existing string keys (machine-translate + native-speaker review)
3. Add the 4 locales to the language selector in Settings

**Affected files:**

- `res/values-ru/strings.xml` (new)
- `res/values-zh/strings.xml` (new)
- `res/values-hi/strings.xml` (new)
- `res/values-ko/strings.xml` (new)
- `presentation/screens/SettingsScreen.kt` (add to locale list)

---

## Dependency graph

```
GAP-001 (include_search + session_id)
    └── GAP-002 (streaming metadata)
            └── GAP-003 (feedback — needs message_id)
            └── GAP-011 (verses sidebar — needs scripture_context in metadata)

GAP-004 (markdown rendering)
    └── GAP-010 (verse ref click-to-detail)

GAP-005 (share message)          — independent
GAP-006 (backend warm-up)        — independent
GAP-007 (scroll to bottom)       — independent
GAP-008 (church finder)          — independent
GAP-009 (contact form)           — independent
GAP-012 (ru/zh/hi/ko locales)   — independent
```

---

## Missing API endpoints summary

The following endpoints are called by the web but **absent from `BibleApiService.kt`**:

| Endpoint | Method | Used by story |
|---|---|---|
| `/health/ready` | GET | GAP-006 |
| `/api/v1/feedback` | POST | GAP-003 |
| `/api/v1/feedback/contact` | POST | GAP-009 |
| `/api/v1/church/search` | POST | GAP-008 |

---

## Size / effort summary

| Gap | Title | Size | Milestone |
|---|---|---|---|
| GAP-001 | include_search + session_id | S | P0 |
| GAP-002 | Streaming metadata | M | P0 |
| GAP-003 | Message feedback | M | P1 |
| GAP-004 | Markdown rendering | M | P1 |
| GAP-005 | Share message | S | P1 |
| GAP-006 | Backend warm-up | S | P1 |
| GAP-007 | Scroll to bottom | S | P1 |
| GAP-008 | Church Finder | L | P2 |
| GAP-009 | Contact Form | M | P2 |
| GAP-010 | Verse ref click-to-detail | M | P2 |
| GAP-011 | Verses sidebar | M | P2 |
| GAP-012 | ru/zh/hi/ko locales | S | P3 |

**Total estimated effort:** ~3–4 engineer-weeks end-to-end

---

## Recommended execution order

1. **Sprint 1 (P0):** GAP-001 → GAP-002 (in sequence; enables everything else)
2. **Sprint 2 (P1, parallelisable):** GAP-003 + GAP-004 + GAP-005 + GAP-006 + GAP-007 (can be worked simultaneously across branches)
3. **Sprint 3 (P2):** GAP-008, GAP-009, GAP-010 (needs GAP-004), GAP-011 (needs GAP-002)
4. **Sprint 4 (P3):** GAP-012

---

## Out of scope for this plan

- Web features that have no mobile equivalent (blue-green deploy, staging env, database migration framework)
- Android-exclusive features already shipped (Room persistence, conversation history, theme toggle, debug export)
- Google Play Store release (tracked separately as BITB-012, blocked by BITB-003 Turnstile)
