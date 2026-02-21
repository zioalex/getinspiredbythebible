# Android App: Bible Inspiration Chat

**Status:** In Progress
**Started:** 2026-02-21

## Summary

Native Android application for the Bible Inspiration Chat platform.
Connects to the existing FastAPI backend (`/api/v1/chat/stream`, `/api/v1/scripture/*`).
Supports 7 locales (en, it, de, es, fr, pt, ar) with full RTL for Arabic.

## Tech Stack

| Layer | Choice |
|-------|--------|
| Language | Kotlin |
| UI | Jetpack Compose + Material 3 |
| Architecture | MVVM + Clean Architecture |
| DI | Hilt |
| Networking | Retrofit + OkHttp |
| SSE Streaming | OkHttp EventSource / manual Flow parser |
| Local DB | Room (chat history cache) |
| Async | Kotlin Coroutines + StateFlow |
| Testing | JUnit 4, MockK, kotlinx-coroutines-test |

## Project Location

`android/` directory at repository root.

## Chunks

### Chunk 0 — Scaffold ✅

- [x] `android/settings.gradle.kts`
- [x] `android/build.gradle.kts` (root)
- [x] `android/app/build.gradle.kts`
- [x] `android/gradle/libs.versions.toml` (version catalog)
- [x] `android/app/src/main/AndroidManifest.xml`
- [x] Source directory skeleton (presentation / domain / data / di / utils)
- [x] `.gitignore` for Android

### Chunk 1 — Domain + Data Models ✅

- [x] `Message.kt`, `Verse.kt`, `ChatRequest.kt`, `ChatResponse.kt` (domain)
- [x] DTO counterparts (`ChatRequestDto`, `ChatResponseDto`, `VerseDto`, `StreamChunkDto`)
- [x] Mappers (`ChatMapper.kt`)
- [x] Unit tests for mappers (`ChatMapperTest.kt`)

### Chunk 2 — API Client + SSE Streaming ✅

- [x] `BibleApiService.kt` (Retrofit interface)
- [x] `ApiClient.kt` (OkHttp + Retrofit setup)
- [x] `EventSourceParser.kt` (SSE → Flow)
- [x] `ChatRepository.kt` interface + `ChatRepositoryImpl.kt`

### Chunk 3 — ChatViewModel ✅

- [x] `ChatViewModel.kt` with `uiState: StateFlow<ChatUiState>`
- [x] `sendMessage()` with streaming accumulation
- [x] Error state and `clearError()`, `clearConversation()`
- [x] Unit tests: 7 tests in `ChatViewModelTest.kt`

### Chunk 4 — Compose UI: Chat Screen ✅

- [x] `ChatScreen.kt` (Scaffold + LazyColumn + auto-scroll)
- [x] `ChatMessageItem.kt` (user/assistant bubbles)
- [x] `ChatInputField.kt` (OutlinedTextField + send button)
- [x] `VerseChip.kt` (collapsible verse references)
- [x] `WelcomeBanner.kt`
- [x] `MainActivity.kt` + `BibleInspirationApp.kt` (Hilt)
- [x] Theme + Typography

### Chunk 5 — i18n + RTL ✅

- [x] `res/values/strings.xml` (English base)
- [x] `res/values-it/`, `values-de/`, `values-es/`, `values-fr/`, `values-pt/`, `values-ar/`
- [x] `LocaleHelper.kt` (RTL detection + `layoutDirectionFor()`)

### Next Up

- [ ] Navigation graph (`NavGraph.kt`) for future multi-screen flow
- [ ] `LanguageSwitcher.kt` composable in Settings
- [ ] Room database for local chat history
- [ ] CI/CD: GitHub Actions workflow for Android build + unit tests

## Progress Log

### 2026-02-21

- Background research completed (tech stack, architecture, Play Store requirements)
- WIP tracking document created
- Task breakdown created in Claude Code task list
- Scaffolded full `android/` project: Gradle (version catalog), AndroidManifest, source tree
- Implemented domain models (Message, Verse, ChatRequest, ChatResponse, StreamChunk)
- Implemented DTOs + ChatMapper with unit tests
- Implemented BibleApiService (Retrofit), ApiClient (OkHttp), EventSourceParser (SSE→Flow), ChatRepositoryImpl
- Implemented ChatViewModel with StateFlow + 7 unit tests
- Implemented Compose UI: ChatScreen, ChatMessageItem, ChatInputField, VerseChip, WelcomeBanner
- Implemented Hilt DI: NetworkModule, RepositoryModule
- Added string resources for all 7 locales (en, it, de, es, fr, pt, ar)
- Implemented LocaleHelper with RTL detection
