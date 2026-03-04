# BITB-015: Auto-Detect User Language for AI Responses

**Status:** In Progress
**Branch:** fix/auto-detect-language
**Started:** 2026-02-24

## Investigation Findings

- detect_language() exists: YES, in `utils/language.py` using lingua-py library
- Language passed to system prompt: YES, detected language is passed to all prompt builders
- Prompt instruction strength: WEAK - uses "You MUST respond entirely in X" but then adds
  "Do not switch to English unless the user does"
- Streaming endpoint has language context: YES, both streaming and non-streaming pass language_code
- Root cause identified: **WEAK LANGUAGE INSTRUCTION** - The prompt says "respond entirely in X"
  but then immediately provides an escape clause "unless the user does". This confuses the LLM
  and causes mid-response language switching.

## Changes Made

- [x] prompts.py: strengthened language instructions
- [x] service.py: enhanced logging for language detection
- [x] tests: updated test expectations for stronger prompts
- [x] All tests passing (949 passed)

## Test Results

- Italian detection: PASS (existing tests in test_language_detection.py)
- Spanish detection: PASS (existing tests in test_language_detection.py)
- German detection: PASS (existing tests in test_language_detection.py)
- French detection: PASS (existing tests in test_language_detection.py)
- Short message fallback: PASS (existing tests)
- All 949 tests passing

## PR URL

{to be filled}
