# BITB-110: Android Still Cannot Read Traditional Chinese Verse References

**Status:** ✅ Done — Traditional Chinese book names now resolve on Android via a ported 29-char
table + a Simplified shadow-copy retry, mirroring the web's `linkifyVerses.ts` technique. Hand-
ported (not generated — BITB-108/113's regex-grammar generator does not yet cover script-class
alternations), with a parity-ledger row naming the source. `VerseCorpusParityTest.kt` and Android's
Gradle/AGP toolchain could not be executed in this sandbox (no network access to the Google Maven
plugin repo) — verified by static reasoning and by mirroring the already-passing web/backend
behaviour instead of a live green CI run; see the PR/session notes for the exact gap.
**Priority:** P2 — a user-visible gap for Traditional-script readers on Android, on a feature web and
the API will already have
**Size:** S
**Created:** 2026-08-22
**Prompted by:** PR #982 (BITB-025), whose Android acceptance criterion is an explicit fast-follow

## User Story

**As** a Traditional Chinese reader using the Android app, **I want** references like `約翰福音 3:16`
to become tappable verse links, **so that** I get the same behaviour the web app and API already
give me, instead of plain unlinked text.

## Why This Exists

PR #982 normalizes Traditional → Simplified before verse parsing on two of three platforms. Its
acceptance criteria record the third as outstanding:

> - [x] Backend: Traditional Chinese book names are normalized to simplified before verse parsing
> - [x] Frontend: Traditional Chinese book names are normalized before verse extraction
> - [ ] **Android: Traditional Chinese book names are normalized in client-side regex (fast-follow)**

Android runs its own client-side verse regex (`android/.../ChatMessageItem.kt`) against a
Simplified-only book-name set. A Traditional reference therefore matches nothing and renders as plain
text — while the same message on web links correctly. That inconsistency is precisely the
three-platform drift BITB-059 exists to reduce.

## What Makes This Small

The design work is done and deliberately portable. PR #982's approach normalizes the **lookup
candidate**, never the stored set:

```ts
// Traditional Chinese retry (BITB-025): the book-name set only stores
// Simplified forms, so a Traditional-script name (e.g. "約翰福音") needs
// its Simplified form tried too. Normalize the candidate, never the set.
return known.has(key) || known.has(normalizeTraditionalToSimplified(key));
```

That shape ports directly to Kotlin, and it is why this does not fight the generated book-name map:
the map stays Simplified-only and generated, and normalization is a retry on the way in. It also
means the table is ~29 characters, not a library — the same minimal-bundle argument that applied on
web applies to the APK.

Display text must stay untouched: the user sees the original script, Traditional or Simplified. Only
the lookup key is normalized. PR #982 already holds this line on the other two platforms.

## Proposed Fix

1. Port the 29-character Traditional→Simplified table and the `normalizeTraditionalToSimplified`
   helper to Kotlin.
2. Apply it as a retry in Android's `isKnownBook`/`normalizeBookName` equivalents — candidate only,
   never the set.
3. Add the Traditional cases to Android's tests, including the mixed-script case PR #982 already
   covers on web (`創世记` — Traditional 創 plus already-Simplified 世记), and assert displayed text
   retains its original script.
4. **Prefer generating the table** if BITB-108 extends the generator to cover script-class
   alternations — a hand-copied third copy is exactly the drift this codebase keeps paying for.
   If BITB-108 has not landed, ship the hand-port with a comment pointing at the web source of truth
   and add the row to the parity ledger.

## Acceptance Criteria

- [x] Traditional Chinese book names are normalized in Android's client-side parsing
      (`ChineseScript.kt`'s `normalizeTraditionalToSimplified`, retried in
      `BookNameNormalizer.kt`'s `isKnownBook`, `ChatMessageItem.kt`'s `injectVerseLinks`, and
      `VersesPanel.kt`'s `referencedVerses`)
- [x] Mixed-script references (`創世记`) resolve correctly (corpus cases
      `zh_mixed_script_genesis` / `zh_mixed_script_ecclesiastes`, no longer skipped for Android)
- [x] Displayed text retains its original script; only the lookup key is normalized
      (`injectVerseLinks` matches against a Simplified shadow copy of the markdown but slices
      every display-facing string — the book text, the already-linked passthrough, and the
      untouched surrounding text — from the original markdown at the same offsets)
- [x] Android tests cover Traditional, mixed-script, and existing Simplified cases with no
      regression (`ChineseScriptTest.kt`, `BookNameNormalizerTest.kt`'s new Traditional cases,
      `VerseRefLinkTest.kt`'s new "Traditional Chinese" section, `VerseCorpusParityTest.kt`)
- [x] The table is hand-ported (not generated — BITB-108/113's generator does not yet cover
      script-class alternations), with a parity-ledger row in `docs/AUDIT_PLAYBOOK.md` naming its
      source (`tests/fixtures/t2s_char_map.json`)
- [x] BITB-025's Android acceptance criterion can be checked off (done in that story's file)

## Verification

The shared cross-platform corpus (PR #906) is the right home for the new cases, so the same inputs
are asserted on all three platforms rather than three divergent test sets — which is the failure mode
that produced this story in the first place.

## Related

- **BITB-025 / PR #982** — ships web + API; owns the AC this closes
- **BITB-108** — if the generator grows script-class alternations, this table should come from it
- **BITB-059** — the parity problem this is an instance of
- `android/.../ChatMessageItem.kt`, `frontend/src/lib/chineseScript.ts`,
  `frontend/src/lib/verseExtraction.ts`
