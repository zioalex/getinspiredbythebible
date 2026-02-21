# PR: Fix Multilanguage Bugs

**Status:** In Progress
**Branch:** fix/multilanguage-bugs
**Started:** 2026-02-21

## Summary

Three bugs affecting non-English (Spanish, French, Portuguese, Arabic) language support.
Reported against Spanish and French; root causes affect all non-English/Italian/German locales.

## Bugs

### Bug 1: Verse links from chat text are broken for Spanish/French (and others)

**Symptom:** Clicking a verse reference like "Juan 3:16" or "Jean 3:16" in the chat pane
opens an empty modal showing "King James Version".

**Root cause:**

- `ChatMessage.tsx::handleTextClick` extracts the localized book name ("Juan") from text
- Passes it to `handleVerseClick("Juan", 3, 16)` → `getChapter("Juan", ...)` → API 404
- Modal opens with no verses, `translationName` is undefined → shows `t("defaultTranslation")` = "King James Version"
- `book_names.py::normalize_book_name()` only handles Italian + German

### Bug 2: LLM starts response in English then switches to user's language

**Symptom:** "This is from the Bible, specifically various verses. La Bible nous enseigne…"

**Root cause:**

- `SYSTEM_PROMPT_TEMPLATE` in `chat/prompts.py` contains a hardcoded English example:
  `- "This is from the Bible, specifically [Book Chapter:Verse]"`
- LLM mimics this phrase before switching to the detected language

### Bug 3: Right pane shows English book names for Spanish/French translations

**Symptom:** Verse card header shows "2 Corinthians 1:4" instead of "2 Corintios 1:4".
Right pane links "point to the English version" label-wise.

**Root cause:**

- `search.py::_get_localized_reference()` calls `book_names.get_localized_book_name()`
- `book_names.py::TRANSLATION_BOOK_NAMES` only maps `ita1927` and `schlachter`
- Spanish (`valera`), French (`ls1910`), Portuguese (`almeida`), Arabic (`arabicsv`) are missing
- `VerseResult` model has no `localized_book` field (unlike `ChapterResponse`)
- Note: `language.py` already has all 6 translation mappings — `book_names.py` is incomplete

## Tasks

- [x] Create WIP document (this file)
- [x] Bug 1+3: Update `api/utils/book_names.py` — add Spanish/French/Portuguese/Arabic mappings
      and their reverse mappings to `LOCALIZED_TO_ENGLISH`
- [x] Bug 1: Add `normalize_book_name()` calls to `get_chapter` + `get_verse` endpoints
- [x] Bug 3: Add `localized_book` field to `VerseResult` model; populate it in `search()`
- [x] Bug 2: Make source attribution example in `SYSTEM_PROMPT_TEMPLATE` language-aware
- [x] Run tests (+11 new tests); create PR #157

## Additional Bugs (discovered during testing, NOT in PR #157)

### Bug 4: Right pane appears only on second interaction

- All languages except Arabic (reported): verse sidebar doesn't render after the first chat message
  even when the response contains Bible verse references.
- Arabic works on first interaction (possibly due to model override in `language_model_overrides`).
- Possible causes: off-topic intent detector misclassifies first-message spiritual queries in
  non-English languages, OR similarity search returns empty results on first query (embeddings
  cold start with Ollama), OR the intent detector OK but `scripture_context.verses` is empty.
- Needs live testing with backend logs to confirm root cause.
- **Not fixed in this PR** — filed for separate investigation.

## Notes

- `language.py` already has complete Spanish/French/Portuguese/Arabic book name tables.
  We added the same data to `book_names.py` (copying avoids circular import).
- The `ChapterResponse` already returns `localized_book` correctly from the `language.py`
  version of `get_localized_book_name`. Search results use `book_names.py` version.
- `normalize_book_name()` only needs to be called at API boundaries (chapter/verse endpoints).
  The DB always stores English canonical names.
- Side-fix: "Referenced" (Citations) filter tab now works for all locales because
  `verse.reference` is now correctly localized (e.g., "Jean 3:16" not "John 3:16"),
  matching what `extractVerseReferences` extracts from the LLM's French/Spanish chat text.
