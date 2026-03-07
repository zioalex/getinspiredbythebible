# PR1 — feat/android-room-persistence

## Status: In Progress

## Summary
Implement persistent conversation history using Room database.

## Files Changed

### New Files
- `data/local/ConversationEntity.kt` — Room entity for conversations
- `data/local/MessageEntity.kt` — Room entity for messages (with FK cascade to conversations)
- `data/local/ConversationDao.kt` — DAO with Flow-based observation and CRUD
- `data/local/MessageDao.kt` — DAO for messages
- `data/local/BibleInspirationDatabase.kt` — Room database class (v1)
- `data/local/mappers/SerializableVerse.kt` — Serializable DTO to avoid polluting domain with annotations
- `data/local/mappers/ConversationEntityMapper.kt` — ConversationEntity ↔ Conversation domain
- `data/local/mappers/MessageEntityMapper.kt` — MessageEntity ↔ Message domain (JSON verses)
- `di/DatabaseModule.kt` — Hilt module providing Room DB, ConversationDao, MessageDao
- `domain/models/Conversation.kt` — New domain model
- `presentation/viewmodels/ConversationsViewModel.kt` — VM for conversations list screen
- `presentation/screens/ConversationsScreen.kt` — List of conversations with swipe-to-delete
- `android/app/schemas/` — Room schema export directory

### Modified Files
- `domain/repositories/ChatRepository.kt` — Added persistence methods
- `data/repositories/ChatRepositoryImpl.kt` — Implemented new persistence methods
- `presentation/viewmodels/ChatViewModel.kt` — Persistence integration + loadConversation
- `presentation/screens/ChatScreen.kt` — Accepts conversationId parameter
- `MainActivity.kt` — NavHost with conversations + chat routes
- `app/build.gradle.kts` — Added KSP room.schemaLocation arg

### Test Files
- `test/.../database/MessageEntityMapperTest.kt` — JSON round-trip for verses
- `test/.../viewmodels/ConversationsViewModelTest.kt` — deleteConversation, clearAll
- `test/.../viewmodels/ChatViewModelTest.kt` — Updated stubs for new repository methods

## Architecture Decisions
1. **SerializableVerse DTO**: Keep domain Verse clean; use separate data-layer DTO for kotlinx.serialization
2. **touchConversation()**: Added to ChatRepository to update `updatedAt` on conversations when new messages arrive
3. **Import aliasing**: Both `data.local.mappers.toDomain` and `data.remote.mappers.toDomain` coexist — Kotlin resolves by receiver type
4. **SharingStarted.WhileSubscribed(5000)**: Standard pattern for ViewModels to avoid keeping DB connections alive when no UI is observing

## Known Issues / Limitations
- No network access in dev environment — tests must be verified in CI
- `loadConversation()` in ChatViewModel uses `collect` which stays active; in production this should be a one-shot query after initial load
