# User Story: Auto-Detect User Language and Respond Accordingly

**As a** user who doesn't speak the default UI language (English)
**I want** the AI to automatically detect and respond in the language I'm writing in
**So that** I can have a natural conversation without manually switching the UI language

## Problem Statement

**Current Behavior:**

- User writes: "Ciao come stai?" (Italian)
- UI is in English (default or Spanish locale)
- AI responds: "Ciao! Mi dispiace, ma devo rispondere in inglese come richiesto. How are you today?..."
- AI starts in Italian but switches to English mid-sentence

**Root Cause:** The backend language detection is working (it detects Italian), but something is overriding it to force English responses.

## Functional Requirements

- [ ] AI detects the language of the user's first message automatically
- [ ] AI responds entirely in the detected language, regardless of UI locale setting
- [ ] Language detection happens on the backend (not just frontend)
- [ ] Detected language persists for the entire conversation
- [ ] User can override by explicitly changing language in UI
- [ ] Detection works for all supported languages: English, Italian, Spanish, German, French

## Non-Functional Requirements

- **UX:** Response should be 100% in detected language, no language mixing mid-response
- **Accuracy:** Language detection should be >95% accurate for messages longer than 5 words
- **Performance:** Detection should add <50ms latency to response
- **Reliability:** If detection fails or is uncertain, default to UI locale language

## Acceptance Criteria

### Core Functionality

- [ ] User writes "Ciao come stai?" → AI responds entirely in Italian
- [ ] User writes "Hola, ¿cómo estás?" → AI responds entirely in Spanish
- [ ] User writes "Guten Tag" → AI responds entirely in German
- [ ] User writes "Hello" → AI responds in English
- [ ] No language switching mid-response (entire response in one language)

### Edge Cases

- [ ] Very short messages (< 3 words) → fall back to UI locale language
- [ ] Mixed language messages → detect dominant language
- [ ] Code-switched messages (e.g., "Ciao! How are you?") → detect first language or most frequent

### Integration

- [ ] Detected language is used for Bible translation preference (if available)
- [ ] Detected language overrides UI locale for AI responses only (UI stays in selected locale)
- [ ] Language preference persists across conversation (doesn't reset on each message)

### Consistency Across Prompts

- [ ] Language instruction in system prompt is respected
- [ ] Verse lookup prompt uses detected language
- [ ] Prayer lookup prompt uses detected language
- [ ] All prompt templates honor the detected language

## Tech Constraints

### Backend (FastAPI)

- Language detection already exists in `api/chat/service.py` via `langdetect` library
- System prompts already have language-specific instructions in `api/chat/prompts.py`
- Current logic: `detect_language()` → `get_system_prompt(language_code)` → LLM
- Issue may be in prompt template or LLM instruction adherence

### Frontend (Next.js)

- UI locale (EN/IT/ES/DE) is separate from AI response language
- User can manually select translation preference (Bible version)
- Detected language should be displayed to user (e.g., "Responding in Italian")

### LLM Provider

- Must work with all providers: Ollama, Claude, OpenRouter
- Some models may be better at language adherence than others
- Prompt engineering may be needed to enforce language consistency

## Out of Scope

- Automatic UI locale switching (user explicitly chooses UI language)
- Translation of previous messages when language changes
- Multilingual conversations (mixing languages intentionally)
- Adding new languages beyond current set (EN, IT, ES, DE, FR)

## Investigation Needed

**Questions for orchestrator/fullstack-engineer:**

1. Is `langdetect` correctly detecting the language? (add logging to verify)
2. Is the detected language code being passed to `get_system_prompt()`?
3. Is the language instruction in the system prompt strong enough?
4. Is the LLM model ignoring the language instruction?
5. Is there a secondary prompt or instruction overriding the language?

**Possible Root Causes:**

1. **Prompt Template Issue:** Language instruction may be too weak or buried in long prompt
2. **LLM Model Behavior:** Model may default to English despite instructions
3. **Translation Preference Override:** Bible translation selection might be forcing language
4. **Multiple Prompts:** Different prompts (VERSE_LOOKUP, PRAYER_LOOKUP) may not honor language
5. **Streaming Issue:** Language instruction may not be included in streaming context

## Testing Requirements

### Manual Testing (All Providers)

1. **Italian Detection:**
   - Input: "Ciao come stai?"
   - Expected: Full Italian response, no English
   - Test with: Ollama, Claude, OpenRouter

2. **Spanish Detection:**
   - Input: "Hola, ¿cómo estás?"
   - Expected: Full Spanish response

3. **German Detection:**
   - Input: "Guten Tag, wie geht es dir?"
   - Expected: Full German response

4. **French Detection:**
   - Input: "Bonjour, comment allez-vous?"
   - Expected: Full French response

5. **Mixed Language:**
   - Input: "Ciao! Can you help me?"
   - Expected: Response in Italian (first language) or English (dominant language)

6. **Very Short Message:**
   - Input: "Ciao"
   - Expected: Response in Italian OR UI locale (acceptable fallback)

### Logging Requirements

- [ ] Log detected language code for each message
- [ ] Log which system prompt template was used
- [ ] Log if LLM response language differs from expected language

### Automated Testing

- [ ] Unit test for `detect_language()` function with sample inputs
- [ ] Integration test: Italian input → Italian response
- [ ] Integration test: Spanish input → Spanish response
- [ ] Regression test: English input → English response (ensure no breakage)

## Expected User Flow

1. User opens app (UI in English by default)
2. User types: "Ciao come stai?"
3. Backend detects language: Italian (`it`)
4. Backend loads Italian system prompt with strong language instruction
5. LLM responds entirely in Italian
6. UI shows: "Responding in Italian 🇮🇹" (optional visual indicator)
7. Subsequent messages continue in Italian until user switches explicitly

## Success Metrics

- [ ] Zero language-switching mid-response (100% single-language responses)
- [ ] >95% language detection accuracy (measured over 100 test inputs)
- [ ] User satisfaction: multilingual users report natural conversations
- [ ] No regressions: English-only users unaffected

---

**Priority:** P0 (Critical UX bug for non-English users)
**Status:** ✅ Done (the P0 default-case bug was resolved by **PR #585**, 2026-05-18 — the web frontend now omits the `language` param so the backend auto-detects from message text; Android sends `null` by default. A follow-up enhancement for the *explicit language-selection* edge case is tracked in `language-mismatch-switch-suggestion.md`.)
**Effort:** Medium (1-2 days for investigation + fix + testing)
**Impact:** High (affects all non-English speaking users)

**Related Issues:**

- May be related to language switching issue reported: "Spanish locale, Italian input, English first sentence then Italian"
- Both suggest LLM is not consistently following language instructions
