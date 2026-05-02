# GAP-002: Android Streaming Metadata Parsing

**PR:** <https://github.com/zioalex/getinspiredbythebible/pull/309>
**Branch:** `feat/android-gap-002-streaming-metadata`
**Status:** OPEN — awaiting review & merge

## Summary

Implements GAP-002: the Android SSE streaming parser now handles all chunk types
from the new backend SSE format (`metadata`, `content`, `error`) in addition to
the legacy format (`done` field-based).

## Files Modified

| File | Change |
|------|--------|
| `ChatResponseDto.kt` | Added `StreamChunkDto` new fields (`type`, `messageId`, `model`, `provider`, `detectedTranslation`, `translationInfo`, `scriptureContext`); new DTOs: `TranslationInfoDto`, `ScriptureContextDto` (with `passages`), `PassageDto`, `ScriptureVerseDto` |
| `ChatMapper.kt` | Updated `StreamChunkDto.toDomain()`; added `ScriptureContextDto.toDomain()`, `ScriptureVerseDto.toDomain()` |
| `ChatResponse.kt` | Extended `StreamChunk` with `type`, `messageId`, `model`, `scriptureContext`; added `ScriptureContext`, `ScriptureVerse` domain models |
| `Message.kt` | Added `messageId`, `model`, `scriptureContext` optional fields |
| `ChatViewModel.kt` | `sendMessage()` dispatches on `chunk.type`; metadata captured; verses derived from `scriptureContext` |
| `EventSourceParserTest.kt` | +7 tests including spec-required A, B, C |
| `ChatMapperTest.kt` | +8 GAP-002 mapper tests |
| `ChatViewModelTest.kt` | +5 ViewModel metadata tests |

## Test Plan

1. `make android-build` — verify it compiles
2. Send chat message → logcat: `SSE metadata: message_id=<uuid> model=<name> verses=<n>`
3. Verse chips on chat screen render (from `scriptureContext.verses`)
4. `./android/gradlew -p android :app:testDebugUnitTest` (JDK 17 required)

## Notes

- Pre-commit toolchain (Python 3.12 venv) unavailable in this environment;
  manual type audit performed — all constructor calls verified compatible.
- `EventSourceParser.kt` required NO change — `ignoreUnknownKeys = true` already handles
  new fields; `event:` lines are already silently dropped.
