# BITB-020: Replace Keyword Filter with OpenAI Free Moderation API

**Priority:** P0 (Critical — unblocks content safety enablement)
**Status:** ✅ Done (PR #512 merged 2026-05-10)
**Size:** M (4-6 hours)
**Created:** 2026-03-04

**⚠️ Post-merge action required:** Set the following env vars in Azure Container App to activate content safety in production:

```
OPENAI_API_KEY=sk-...
CONTENT_SAFETY_ENABLED=true
CONTENT_SAFETY_MODE=keyword_only
```

---

## Background

Content safety (BITB-017) was deployed to production on 2026-03-04 with feature flag
`CONTENT_SAFETY_ENABLED=false`. It cannot be safely enabled because the keyword-based
violence filter produces unacceptable false positives: common Bible study queries such as
"David killed Goliath" or "the slaughter of the innocents" match broad patterns like
`\bkill\b` and `\bslaughter\b`, resulting in HTTP 400 errors for legitimate users.

A thorough analysis (2026-03-04) evaluated three approaches. **Proposal 2 — OpenAI Free
Moderation API** was selected as the best fix: it is context-aware (understands Bible
stories vs. real threats), free and unlimited, and already fits the existing
`keyword_only → hybrid → ml_only` mode architecture.

**Technical analysis doc:** `docs/WIP/SESSION-2026-03-04-FINAL.md`

---

## User Story

**As a** spiritual guidance app user asking about Bible stories involving violence,
**I want** the content safety filter to understand the difference between discussing
scripture and expressing harmful intent,
**so that** I can ask "How did David defeat Goliath?" or "Tell me about the slaughter
of the innocents" without being blocked by a false positive.

**As a** product owner,
**I want** to enable content safety in production immediately,
**so that** the app is protected from genuinely harmful content while not frustrating
legitimate users studying the Bible.

---

## Problem Statement

### False Positives That Block Real Users (Current Keyword Filter)

The current `MultiLanguageContentFilter` uses bare word-boundary regex patterns that
match any occurrence of the word, regardless of context:

| User query | Pattern matched | Result |
|---|---|---|
| "David **killed** Goliath, what can I learn?" | `\bkill\b` | ❌ HTTP 400 blocked |
| "Jesus was **attacked** by the Pharisees" | `\battack\b` | ❌ HTTP 400 blocked |
| "The **terrorist** plot in the book of Esther" | `\bterror` | ❌ HTTP 400 blocked |
| "Saul's **weapon** was a spear" | `\bweapon\b` | ❌ HTTP 400 blocked |
| "How did Samson **slaughter** the Philistines?" | `\bslaughter\b` | ❌ HTTP 400 blocked |
| "The **murder** of Abel by Cain" | `\bmurder\b` | ❌ HTTP 400 blocked |
| "**Bomb**ardment of the walls of Jericho" | `\bbomb` | ❌ HTTP 400 blocked |

The Bible contains extensive accounts of war, killing, weapons, and violence —
a keyword filter that blocks these words cannot coexist with a Bible study app.

### What Must Be Preserved

The following correctly-working detections must remain intact:

- ✅ "Go kill yourself" → blocked (directed harm)
- ✅ "I want to build a bomb" → blocked (literal threat, no biblical context)
- ✅ Hate speech → blocked
- ✅ "I want to die" → allowed through with `compassionate_response_needed=True`
- ✅ Leet-speak / zero-width character evasion detection
- ✅ Fail-open on errors (request proceeds if filter crashes)

---

## Proposed Solution

### Architecture: Two-Stage Pipeline

```
User Message
     │
     ▼
┌─────────────────────────────────────────────┐
│  Stage 1: Keyword Fast-Pass (<5ms, $0)      │
│  Check ONLY directed_harm + hate_speech     │
│  patterns (unambiguous, never biblical)     │
│  - "go kill yourself" → BLOCK               │
│  - "kill all [group]" → BLOCK               │
│  - racial/religious slurs → BLOCK           │
└──────────────┬──────────────────────────────┘
               │ Only the ~5% most obvious cases
               │ are caught here. Rest pass through.
               ▼
┌─────────────────────────────────────────────┐
│  Stage 2: OpenAI Moderation API (~100-150ms)│
│  Model: omni-moderation-latest (FREE)       │
│  - 13 categories with confidence scores     │
│  - Context-aware: biblical ≠ threat         │
│  - "David killed Goliath" → violence: 0.02  │
│  - "I want to bomb the school" → violence:  │
│    0.97                                     │
│                                             │
│  Decision logic:                            │
│  - violence OR harassment/threatening → BLOCK│
│  - self-harm/intent only → ALLOW + flag     │
│  - self-harm/instructions → BLOCK           │
│  - all scores < threshold → ALLOW           │
└──────────────┬──────────────────────────────┘
               │ API unavailable?
               ▼
┌─────────────────────────────────────────────┐
│  Fallback: existing keyword filter          │
│  (current full behavior preserved)          │
└─────────────────────────────────────────────┘
```

### OpenAI Moderation API Key Facts

- **Cost:** Free, unlimited (no quota)
- **Model:** `omni-moderation-latest` (multimodal, best accuracy)
- **Latency:** ~100-150ms (acceptable — LLM call is already 1-5s)
- **Categories returned** (13 total, all with float confidence scores):
  - `harassment`, `harassment/threatening`
  - `hate`, `hate/threatening`
  - `illicit`, `illicit/violent`
  - `self-harm`, `self-harm/intent`, `self-harm/instructions`
  - `sexual`, `sexual/minors`
  - `violence`, `violence/graphic`
- **Language support:** 13+ languages natively (covers all 7 supported languages)
- **Context-aware:** Trained to distinguish discussing violence from threatening violence
- **Privacy:** Same as existing LLM calls (text sent to OpenAI/OpenRouter)

### Mode Mapping (Fits Existing Config)

The existing `CONTENT_SAFETY_MODE` config maps cleanly:

| Mode | Stage 1 | Stage 2 | Use case |
|---|---|---|---|
| `keyword_only` | directed_harm + hate_speech only | ❌ skipped | **Recommended: enables safely** |
| `hybrid` | directed_harm + hate_speech only | ✅ OpenAI Moderation | Maximum accuracy |
| `ml_only` | ❌ skipped | ✅ OpenAI Moderation | Pure ML (future) |

**Immediate recommendation:** Enable with `CONTENT_SAFETY_MODE=keyword_only` — which in
the new architecture means: fast directed-harm check + OpenAI Moderation. This is safe
because the old broad violence keywords are no longer in Stage 1.

---

## Acceptance Criteria

### Functional

- [ ] `MultiLanguageContentFilter` Stage 1 retains ONLY `directed_harm` and `hate_speech`
      patterns (remove `violence` and `self_harm` from Stage 1 fast-pass)
- [ ] New `OpenAIModerationProvider` in `api/providers/openai_moderation.py`:
  - Calls `POST https://api.openai.com/v1/moderations` with `omni-moderation-latest`
  - Accepts existing `openai_api_key` or `openrouter_api_key` (try both)
  - Returns `ContentSafetyResult` compatible with existing interface
  - Timeout: 3 seconds (fail-open on timeout)
- [ ] `ContentSafetyService` in `hybrid`/`keyword_only` mode uses OpenAI Moderation as
      Stage 2 instead of (or before) Azure Content Safety
- [ ] Decision logic for OpenAI moderation results:
  - `violence ≥ threshold OR harassment/threatening ≥ threshold` → BLOCK
  - `self-harm/intent > 0 AND violence == 0 AND harassment == 0` → ALLOW + `compassionate_response_needed=True`
  - `self-harm/instructions ≥ threshold` → BLOCK
  - All scores < threshold → ALLOW
- [ ] Fallback chain: OpenAI unavailable → existing keyword filter (full behavior)
- [ ] Azure Content Safety provider preserved and still usable (not removed)

### False Positive Tests (Must All PASS = be ALLOWED)

- [ ] "David killed Goliath, what can I learn?" → ALLOW
- [ ] "Jesus was attacked by the Pharisees" → ALLOW
- [ ] "The terrorist plot in the book of Esther" → ALLOW
- [ ] "Saul's weapon was a spear" → ALLOW
- [ ] "The slaughter of the innocents in Matthew 2" → ALLOW
- [ ] "Cain murdered Abel — why did God not stop it?" → ALLOW
- [ ] "Tell me about the wars in the Old Testament" → ALLOW
- [ ] "How did Samson kill the Philistines with a jawbone?" → ALLOW
- [ ] "I am struggling with drugs, how can I find hope?" → ALLOW (help-seeking)
- [ ] "I feel like I want to die, please help" → ALLOW + `compassionate_response_needed=True`

### True Positive Tests (Must All BLOCK)

- [ ] "I want to build a bomb and blow up the school" → BLOCK
- [ ] "Go kill yourself you piece of shit" → BLOCK (directed harm, Stage 1)
- [ ] "Kill all [ethnic group]" → BLOCK (hate speech, Stage 1)
- [ ] "How do I make an explosive device?" → BLOCK
- [ ] "I will murder my neighbor" → BLOCK
- [ ] "You are a [slur]" → BLOCK (hate speech, Stage 1)

### Non-Functional

- [ ] Stage 1 (keyword check) completes in <5ms
- [ ] Stage 2 (OpenAI Moderation) completes in <3s (timeout = fail-open)
- [ ] Fallback to existing keyword filter if OpenAI API unavailable
- [ ] `openai_api_key` OR `openrouter_api_key` accepted (whichever is configured)
- [ ] All existing 1,033 backend tests still pass
- [ ] New tests: minimum 15 covering false positives, true positives, and fallback
- [ ] `make pre-commit` passes (MyPy, Ruff, Black, Bandit)

---

## Configuration

### New Environment Variables

```env
# OpenAI Moderation (Stage 2 of content safety pipeline)
# Uses existing OPENAI_API_KEY if set, otherwise OPENROUTER_API_KEY
# No new key required if either is already configured
OPENAI_MODERATION_THRESHOLD=0.5   # Float 0.0-1.0, block if score >= threshold
OPENAI_MODERATION_TIMEOUT=3       # Seconds before fail-open
```

### No Breaking Config Changes

Existing variables unchanged:

```env
CONTENT_SAFETY_ENABLED=true        # Master switch
CONTENT_SAFETY_MODE=keyword_only   # Now safe to enable
```

---

## Implementation Guide

### Files to Create

**`api/providers/openai_moderation.py`** — New provider:

```python
class OpenAIModerationProvider:
    """
    OpenAI Moderation API provider (free, unlimited).
    Model: omni-moderation-latest

    Endpoint: POST https://api.openai.com/v1/moderations
    Auth: Bearer {openai_api_key or openrouter_api_key}
    """

    async def analyze_text(
        self, text: str, language: str = "en"
    ) -> ContentSafetyResult:
        """Call OpenAI moderation and map to ContentSafetyResult."""
        ...
```

### Files to Modify

**`api/utils/security.py`** — `MultiLanguageContentFilter`:

- Remove `VIOLENCE_PATTERNS` from `check_multilingual()` Stage 1
- Remove `SELF_HARM_PATTERNS` from `check_multilingual()` Stage 1
- Keep `DIRECTED_HARM_PATTERNS` (always high-confidence, never biblical)
- Keep `HATE_SPEECH_PATTERNS` (always high-confidence, never biblical)
- Keep normalize_text (still used for Stage 1 patterns)

**`api/utils/content_safety.py`** — `ContentSafetyService`:

- In `keyword_only` and `hybrid` modes: after Stage 1 keyword pass, call OpenAI Moderation
- In `hybrid` mode: call both OpenAI Moderation AND Azure Content Safety (stricter)
- Preserve Azure Content Safety as optional additional layer

**`api/config.py`**:

- Add `openai_moderation_threshold: float = 0.5`
- Add `openai_moderation_timeout: int = 3`

### Decision Logic for OpenAI Response

```python
def _interpret_openai_result(
    self,
    categories: dict[str, float],
    threshold: float,
) -> ContentSafetyResult:
    violence = categories.get("violence", 0)
    harassment_threatening = categories.get("harassment/threatening", 0)
    self_harm = categories.get("self-harm", 0)
    self_harm_intent = categories.get("self-harm/intent", 0)
    self_harm_instructions = categories.get("self-harm/instructions", 0)
    hate = categories.get("hate", 0)
    hate_threatening = categories.get("hate/threatening", 0)

    # Block: explicit violence or threatening harassment
    if violence >= threshold or harassment_threatening >= threshold:
        return ContentSafetyResult(allowed=False, reason="violence_or_threat_detected")

    # Block: self-harm instructions (not help-seeking)
    if self_harm_instructions >= threshold:
        return ContentSafetyResult(allowed=False, reason="self_harm_instructions_detected")

    # Block: hate speech
    if hate >= threshold or hate_threatening >= threshold:
        return ContentSafetyResult(allowed=False, reason="hate_speech_detected")

    # Allow but flag: self-harm intent only (help-seeking behavior)
    if self_harm_intent > 0.1 and violence < 0.1 and hate < 0.1:
        return ContentSafetyResult(
            allowed=True,
            reason="possible_help_seeking",
            is_help_seeking=True,
            compassionate_response_needed=True,
        )

    # Clean
    return ContentSafetyResult(allowed=True, reason="clean")
```

---

## Test Plan

### Unit Tests (`api/tests/test_openai_moderation.py`)

```python
# False positives — must ALLOW (mocked API responses)
async def test_allows_david_killed_goliath()
async def test_allows_war_in_old_testament()
async def test_allows_slaughter_of_innocents()
async def test_allows_help_seeking_self_harm()
async def test_allows_drug_struggle_help_seeking()

# True positives — must BLOCK (mocked API responses)
async def test_blocks_literal_bomb_threat()
async def test_blocks_murder_threat()
async def test_blocks_self_harm_instructions()

# Fallback behavior
async def test_fallback_to_keyword_when_api_unavailable()
async def test_fallback_on_timeout()

# Decision logic
async def test_self_harm_intent_alone_is_compassionate()
async def test_violence_plus_self_harm_is_blocked()

# Configuration
async def test_uses_openai_api_key_when_available()
async def test_uses_openrouter_api_key_as_fallback()
```

### Manual Smoke Test (After Deploy)

```bash
# Should return HTTP 200
curl -X POST https://getinspiredbythebible.ai4you.sh/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "How did David defeat Goliath?"}'

# Should return HTTP 400
curl -X POST https://getinspiredbythebible.ai4you.sh/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "I want to build a bomb and blow up the school"}'
```

---

## Out of Scope

- Replacing Azure Content Safety provider (kept for `hybrid` mode)
- Adding OpenAI moderation to image inputs (text-only app)
- Changing the `self-harm/intent` compassionate response behavior (already correct)
- Removing the `MultiLanguageContentFilter` class entirely (kept for Stage 1 and fallback)
- Frontend changes

---

## Dependencies

- **Unblocks:** Enabling `CONTENT_SAFETY_ENABLED=true` in production
- **Depends on:** BITB-017 (PR #208 merged ✅)
- **API key:** `OPENAI_API_KEY` or `OPENROUTER_API_KEY` (at least one already configured in production)

---

## Definition of Done

- [ ] PR merged to main
- [ ] All CI checks green
- [ ] All existing 1,033 tests pass
- [ ] New moderation tests pass (≥15)
- [ ] False positive tests all return HTTP 200 (manual smoke test)
- [ ] True positive tests all return HTTP 400 (manual smoke test)
- [ ] `CONTENT_SAFETY_ENABLED=true` enabled in production Azure Container App
- [ ] Production monitored for 24 hours with no unexpected blocks
- [ ] `docs/HOW-TO-ENABLE-CONTENT-SAFETY.md` updated to reflect new architecture

---

## Effort Estimate

| Phase | Time |
|---|---|
| Create `OpenAIModerationProvider` | 2 hours |
| Update `MultiLanguageContentFilter` (remove broad patterns from Stage 1) | 30 min |
| Update `ContentSafetyService` (wire new provider) | 1 hour |
| Tests (≥15 new tests) | 1-2 hours |
| `make pre-commit` + CI | 30 min |
| **Total** | **5-6 hours** |
