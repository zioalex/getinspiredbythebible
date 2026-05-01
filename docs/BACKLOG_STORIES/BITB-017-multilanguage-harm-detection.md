# BITB-017: Multi-Language Violence & Harm Detection

**Priority:** P0 (Critical Security)
**Size:** M (1-2 days)
**Status:** ✅ Done (PR #208 merged and deployed to production)
**Size:** M (1-2 days)
**Created:** 2026-02-24
**Completed:** 2026-03-04

---

## ✅ COMPLETED & DEPLOYED (2026-03-04)

**PR #208:** <https://github.com/zioalex/getinspiredbythebible/pull/208>
**Branch:** `feat/BITB-017-content-safety` (merged and deleted)
**Merge Commit:** `67bdca6e0de2e9f1e1d3fab8988b27f6165b3848`
**Deployed:** 2026-03-04T20:54:40Z

✅ **Development Complete:**

- Code review complete (duplication eliminated)
- Merge conflicts resolved
- All CI checks passing
- 1,033 tests passing (includes 36 new content safety tests)

✅ **Deployment Complete:**

- All 3 workflows succeeded (pre-commit, tests, deploy)
- Docker images built and pushed to ACR
- Azure Container Apps updated
- Production site verified: <https://getinspiredbythebible.ai4you.sh/>

✅ **Feature Flag Status:**

- Default: `CONTENT_SAFETY_ENABLED=false` (feature dormant, zero user impact)
- Ready for gradual rollout when needed

🎯 **Next Steps (Gradual Rollout):**

1. **Phase 1** (This Week): Enable `CONTENT_SAFETY_MODE=keyword_only` via Azure env var
2. **Monitor**: False positives, false negatives, latency
3. **Phase 2** (Next Week): Switch to `CONTENT_SAFETY_MODE=hybrid` (Azure API)
4. **Monitor**: API costs, detection accuracy, user feedback

**Deployment Record:** `docs/DONE/PR208-BITB-017-deployment-record.md`

---

## User Story

**As a** product owner and safety officer,
**I want** to detect and reject violent, harmful, or inappropriate content in all supported languages,
**so that** the app cannot be used to promote violence, self-harm, or abuse,
**while still** allowing people seeking help or expressing raw emotions to receive spiritual guidance.

---

## Problem Statement

### Critical Incident

User submitted (in Italian):

```
"Ciao, sono cosi' frustrato. Voglio costruire una bomba e fare esplodere i miei pensieri"
(Translation: "Hi, I'm so frustrated. I want to build a bomb and blow up my thoughts")
```

**Expected behavior:** Request rejected with 400 error, security violation logged

**Actual behavior:** AI responded with scripture (Job 21:27), completely missing the violent language

### Critical Distinction: Help-Seeking vs. Harmful Intent

**⚠️ IMPORTANT:** This is a **spiritual guidance and counseling app**. We must distinguish between:

**✅ ALLOW (Help-Seeking / Raw Emotions):**

- `"I'm getting into drugs and cocaine, how can I get out of this?"` → **ALLOW**, respond with hope/recovery verses
- `"I feel like shit"` → **ALLOW**, respond with comfort/encouragement
- `"I feel like an asshole for what I did"` → **ALLOW**, respond with forgiveness/repentance verses
- `"I want to die"` (context: expressing pain) → **ALLOW**, respond with hope/crisis resources
- `"I'm so angry I could explode"` → **ALLOW**, respond with anger management verses

**🚫 BLOCK (Harmful Intent / Abuse):**

- `"You are a shit"` (directed at AI/others) → **BLOCK**, kind message
- `"I want to build a bomb"` (literal threat) → **BLOCK**, security log
- `"Go kill yourself"` (directed at others) → **BLOCK**, hate speech
- `"F*ck you"` (abuse directed at AI) → **BLOCK**, profanity filter

**Key Principle:** If the user is seeking help or expressing raw feelings about themselves, **respond with compassion**. If the user is being abusive, threatening, or directing harm at others, **block kindly**.

### Root Cause

Current profanity filter (`api/utils/security.py`):

- Only detects **English profanity** (fuck, shit, asshole, etc.)
- Does **NOT detect**:
  - Violence terms (bomb, kill, murder, suicide, etc.)
  - Self-harm language (hurt myself, want to die, etc.)
  - Non-English harmful content (bomba, suicidio, etc.)
  - Unicode evasion (f​u​c​k with zero-width spaces)
  - Character substitution (f*ck, sh!t)

**Severity**: **CRITICAL** — App can be used to seek biblical justification for violence or self-harm

---

## Acceptance Criteria

### Must Have (P0)

- [ ] Detect violence keywords in all 7 supported languages (EN, IT, DE, ES, FR, PT, AR)
  - bomb, explosive, weapon, gun, kill, murder, attack, terrorism
  - bomba (IT/ES/PT), bombe (DE/FR), قنبلة (AR)
  - uccidere (IT), töten (DE), matar (ES), tuer (FR), قتل (AR)
- [ ] Detect self-harm keywords in all 7 languages
  - suicide, kill myself, want to die, self-harm, cut myself
  - suicidio (IT/ES/PT), Selbstmord (DE), suicide (FR), انتحار (AR)
- [ ] Detect hate speech keywords (racism, slurs, religious hatred)
- [ ] Unicode normalization before pattern matching (prevent zero-width char evasion)
- [ ] Character substitution detection (`f*ck`, `sh!t`, `b0mb`)
- [ ] Request blocked with HTTP 400 and clear error message
- [ ] Security violation logged with language, pattern matched, full text hash
- [ ] Unit tests for all language patterns and evasion techniques

### Should Have (P1)

- [ ] Use ML-based harmful content classifier (e.g., OpenAI Moderation API, Azure Content Safety)
  - Detects violence, self-harm, hate speech, sexual content
  - Language-agnostic (works for all languages)
  - Fallback to keyword filter if API unavailable
- [ ] Configurable severity levels: block vs. warn vs. log-only
- [ ] Admin dashboard to review flagged content (future)

### Nice to Have (P2)

- [ ] Context-aware detection (differentiate "I'm dying to know" vs. "I want to die")
- [ ] False positive tracking and tuning
- [ ] Custom response for blocked content (offer crisis helpline resources)

---

## Tech Constraints

- **Performance**: Filter must execute in <50ms (runs on every request)
- **Privacy**: Do NOT log full message text (only hash + matched pattern)
- **Fail-safe**: If filter crashes, **fail-open with logging** (don't break the app)
- **Internationalization**: Must work with Unicode (Arabic, Chinese, emoji)
- **Offline-capable**: Keyword filter must work without external API calls (ML classifier is optional enhancement)

---

## Out of Scope

- Image/media content moderation (text-only for now)
- User reputation scoring
- Manual review workflow (track separately in BITB-019)
- Legal compliance (GDPR, COPPA, etc.) — separate story

---

## Implementation Approach

### Option A: Enhanced Keyword Filter (Fast, Privacy-First)

**Pros**: No external API, fast, private, free
**Cons**: Requires manual maintenance, language-specific patterns

```python
# Expanded PROFANITY_PATTERNS in api/utils/security.py
VIOLENCE_PATTERNS = {
    "en": [r"\bbomb", r"\bkill", r"\bmurder", r"\bsuicide", ...],
    "it": [r"\bbomba", r"\buccidere", r"\bsuicidio", ...],
    "de": [r"\bbombe", r"\btöten", r"\bselbstmord", ...],
    # ... ES, FR, PT, AR
}

def normalize_text(text: str) -> str:
    """Normalize unicode, remove zero-width chars, expand substitutions."""
    # NFKC normalization
    # Remove zero-width spaces
    # Expand l33t speak (@ -> a, 0 -> o, etc.)
```

### Option B: ML-Based Classifier (Highest Accuracy)

**Pros**: Language-agnostic, detects nuance, continuously updated
**Cons**: External API dependency, cost, latency, privacy concerns

```python
# New provider: api/providers/content_safety.py
class ContentSafetyProvider:
    async def check(self, text: str) -> tuple[bool, str | None]:
        # Call Azure Content Safety API or OpenAI Moderation
        # Cache results for identical text
```

### Option C: Hybrid (Recommended)

1. **First pass**: Keyword filter (0-cost, instant)
2. **Second pass**: ML classifier if keywords inconclusive (optional, configurable)
3. **Escalation**: Log borderline cases for manual review

---

## Testing Strategy

### Unit Tests

```python
# api/tests/test_content_safety.py

def test_blocks_violence_english():
    assert not filter.check("I want to build a bomb")[0]

def test_blocks_violence_italian():
    assert not filter.check("Voglio costruire una bomba")[0]

def test_blocks_self_harm_arabic():
    assert not filter.check("أريد أن أقتل نفسي")[0]  # "I want to kill myself"

def test_unicode_evasion_blocked():
    assert not filter.check("f​u​c​k")[0]  # zero-width spaces

def test_character_substitution_blocked():
    assert not filter.check("b0mb")[0]  # 0 -> o

def test_context_allows_metaphor():
    # Should NOT block metaphorical use (stretch goal)
    assert filter.check("This sermon is the bomb!")[0]
```

### Manual QA

- [ ] Test with native speakers in all 7 languages
- [ ] Test common evasion techniques
- [ ] Verify crisis situations redirect appropriately

---

## Dependencies

- None (can implement immediately)

---

## Success Metrics

- **Zero false negatives**: All violent/harmful content blocked
- **<5% false positives**: Legitimate queries not incorrectly blocked
- **<50ms latency**: Filter executes quickly
- **100% language coverage**: Works for all 7 supported languages

---

## Follow-Up Work

- **BITB-019**: Crisis Response Flow — Offer helpline resources when harm detected
- **BITB-020**: Content Moderation Dashboard — Review flagged content, tune filters
- **BITB-021**: Theological Review — Ensure AI doesn't misuse scripture for harmful purposes

---

## References

- TASKS.md #2.4: "Profanity Filter Easily Bypassed"
- OpenAI Moderation API: <https://platform.openai.com/docs/guides/moderation>
- Azure Content Safety: <https://azure.microsoft.com/en-us/products/ai-services/ai-content-safety>
- Unicode normalization: <https://unicode.org/reports/tr15/>
