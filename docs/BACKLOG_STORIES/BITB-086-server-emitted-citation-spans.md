# BITB-086: Server-Emitted Citation Spans — Let a Client Linkify Verses Without Its Own Regex

**Status:** 🎯 Todo
**Priority:** P2 (raise to P1 if BITB-087 is scheduled — it is a hard prerequisite)
**Size:** L (backend contract + web reference consumer + cross-language corpus)
**Created:** 2026-07-29
**Part of:** the iOS delivery plan — Stage 2 of BITB-084 → BITB-085 → **BITB-086** → BITB-087 → BITB-088.
**Unblocks:** BITB-087 (a native iOS client that ships **no** verse regex of its own).

## User Story

**As a** maintainer about to add a fourth client, **I want** the backend to tell clients *where* in
the answer each verse citation appears, **so that** making citations tappable no longer requires
every client to re-implement an eleven-language citation grammar in a different regex dialect.

**As a** reader on any platform, **I want** every citation the backend recognised to be tappable,
**so that** a citation the server resolved but my client's regex missed is not a dead piece of text.

## Why Now

The backend **already knows** every citation in the answer. `api/chat/service.py:1310-1321` merges
the LLM's structured citations with its own regex extraction into `merged_refs`, and
`api/chat/service.py:1375-1386` ships the result to clients as `verses_cited` (raw reference
strings) plus `resolved_verses` (DB-resolved, ranges expanded).

**No client uses it for linkification.** A `grep` for `verses_cited` / `versesCited` across
`frontend/src/` and `android/app/src/main` returns **nothing** — the only consumers are
`api/routes/feedback.py:78` and tests. Instead each client re-derives the same information from the
raw text with its own regex:

| Platform | Implementation | Dialect |
|---|---|---|
| Backend | `api/utils/verse_parser.py` | Python `re` |
| Web | `frontend/src/lib/versePatterns.ts` | JS `\p{Script=Han}` |
| Android | `android/.../presentation/components/ChatMessageItem.kt` (~104-362) | Java `\p{IsHan}` |

Keeping those three aligned is finding **A1 (CRITICAL)** of `docs/audits/2026-07-adversarial-audit.md`
and the subject of **BITB-059**, which has shipped only the book-name-map half of its Phase 1. The
regex grammar itself — separators, ranges, script classes, the nested-quantifier connector branch —
is explicitly **Phase 3, not started**. A native iOS client written today would add a *fourth*
dialect (`NSRegularExpression`/ICU) to a problem the repo has already labelled critical, and it
would land in the gap BITB-059 has not yet closed.

BITB-059's *Out of scope* section names this exact alternative — "Moving extraction fully
server-side (evaluated as the alternative in the audit) — larger change, revisit if the generator
approach proves insufficient." **A fourth client is the revisit trigger.** The generator approach
does not solve the grammar for a new platform; it only solves the book-name map.

## Design

### The contract

Add an additive `citations` array to the streaming `completion` event, following the exact
backward-compatibility pattern the file already documents for `corrected_message` /`corrections`
(`service.py:1380-1381`: "older clients ignore unknown fields, so this is backward compatible").

Each entry locates one citation **in the final message text** and identifies what it points to:

```jsonc
{
  "type": "completion",
  "verses_cited": ["Romans 8:38-39"],       // unchanged — do not repurpose or remove
  "resolved_verses": [ /* unchanged */ ],
  "citations": [
    {
      "text": "Romans 8:38-39",   // the exact substring, for verification
      "start": 142,               // offset into the final message text
      "end": 156,                 // exclusive
      "occurrence": 0,            // 0-based index of this substring in the text
      "book": "Romans",           // canonical English book name
      "chapter": 8,
      "verse": 38,
      "verse_end": 39             // null for single-verse citations
    }
  ]
}
```

Three decisions in that shape are load-bearing and must not be quietly changed during
implementation:

1. **Offsets are computed against the *authoritative* text.** When grounding rewrote a quote,
   `corrected_message` *replaces* the streamed content (`service.py:1383`). Offsets computed
   against the pre-correction text would be silently wrong exactly on the messages the app worked
   hardest to get right. Compute spans **after** `_ground_streamed_answer` returns, against
   `corrected_message` when present and `full_response` otherwise. Add a test that fails if this is
   done in the wrong order.
2. **The offset unit is specified, not assumed.** Python `str` indexes code points, JS and Kotlin
   index UTF-16 code units, and Swift `String` indexes grapheme clusters. With Arabic combining
   marks, Devanagari, and CJK in play, an unspecified unit is a guaranteed off-by-N. **Specify
   UTF-16 code units** (native for two of the four clients, well-defined conversions for the other
   two) and say so in the field docs.
3. **`text` + `occurrence` make the contract self-verifying.** A client asserts
   `message.slice(start, end) == text`; on mismatch it falls back to locating the `occurrence`-th
   literal instance of `text`, and if *that* fails it renders plain text rather than mangling the
   message. This turns the encoding question from a correctness cliff into a degradation path, and
   is what lets a Swift client — where offset arithmetic is genuinely awkward — use pure substring
   search and ignore offsets entirely.

### Rollout, in this order

1. **Backend emits `citations`.** No client behaviour changes. Purely additive.
2. **Web becomes the reference consumer, behind a flag,** with the existing
   `versePatterns.ts` regex as the fallback path. Web is the cheapest place to prove the contract
   (`vitest` + `frontend/e2e/` Playwright already exist) and proving it here is what stops the
   contract from rotting as an iOS-only code path nobody else exercises.
3. **iOS (BITB-087) consumes it as its only mechanism** — no Swift regex, no fallback grammar to
   maintain, degrading to plain text if `citations` is absent.

**Explicitly not in this story: deleting the web or Android regex.** Both keep working; web merely
gains a second, preferred path. Ripping out three parsers in the same change as introducing the
contract is how this becomes an un-reviewable, un-shippable PR. Retiring them is BITB-059's
Phase 3 to schedule once the contract has run in production.

### Known limitation to state up front, not discover later

`citations` arrives in the **completion** event, so links appear when the message finishes
streaming, whereas today's client regex linkifies progressively as tokens arrive. On slower answers
that is a visible change. Two mitigations, and the story must pick one deliberately:

- Accept it (links settle at completion — and mid-stream matches on partial text are a source of
  flicker and false positives today), or
- also emit spans on partial content in `metadata`/content events, which is materially more
  complex and can be invalidated by `corrected_message`.

**Recommendation: accept it for v1**, and keep the web fallback flag as the escape hatch if it
reads badly.

## Acceptance Criteria

- [ ] The streaming `completion` event carries `citations` with the shape above; `verses_cited` and
      `resolved_verses` are unchanged in name, meaning, and content.
- [ ] Offsets/`text` are computed against `corrected_message` when grounding rewrote the answer, and
      against the streamed response otherwise — with a regression test for the corrected case.
- [ ] The offset unit is documented in the field comment **and** asserted by a test containing
      Arabic combining marks, Devanagari numerals, CJK, and an emoji.
- [ ] For every citation, `message[start:end] == text`, asserted across the whole cross-language
      corpus.
- [ ] `citations` covers the union the backend already knows about (structured + server regex), so a
      citation `verses_cited` contains is never missing a span — asserted, not assumed.
- [ ] Parenthesized/bracketed `(John 3:16)` / `[Salmo 23:1]`, fullwidth `（…）`,
      guillemet `《约翰福音》3:16`, German comma `Johannes 3,16`, numbered books, and ranges all
      produce spans whose `text` excludes the surrounding punctuation.
- [ ] A client on the **old** contract (no `citations` field) is provably unaffected — existing
      Android and web tests pass untouched.
- [ ] Web consumes `citations` behind a flag, produces byte-identical rendered output to the regex
      path for the shared corpus, and falls back cleanly when the field is absent.
- [ ] A client given deliberately corrupt spans (offsets past end-of-string, mismatched `text`,
      overlapping ranges) renders plain text and does not crash or duplicate content.
- [ ] `docs/AUDIT_PLAYBOOK.md`'s parity-ledger entry for the verse regex records that a
      server-authoritative path now exists and which clients use it.

## Tests to Add

- `api/tests/test_chat_citation_spans.py` (new) — parametrized across **all 11 languages**
  (en, it, de, es, fr, pt, ar, ru, zh, hi, ko) per the AGENTS.md multilingual rule: span offsets
  round-trip, punctuation excluded, ranges carry `verse_end`.
- Integration test through `chat_stream()` (mocking `search_service.get_verse`, the pattern AGENTS.md
  mandates for grounding changes) asserting spans align with `corrected_message` on a corrected
  answer.
- Reuse the **existing shared cross-platform corpus** from `tests/fixtures/` (shipped in PR #906 per
  BITB-059) as the span corpus — do not create a second, competing corpus.
- `frontend/src/lib/` unit tests: span-based renderer equals regex-based renderer over the corpus;
  malformed-span degradation; absent-field fallback.
- Adversarial input test: spans for a message containing a markdown link whose display text is
  itself a reference — today handled by the "already inside a markdown link" check documented at
  `ChatMessageItem.kt:~100`; the span path must not double-link it.

## Files Likely to Change

| File | Change |
|---|---|
| `api/chat/service.py` | Compute spans post-grounding; add `citations` to the completion dict (~1310-1386) |
| `api/utils/verse_parser.py` | Return match offsets alongside references (may already be available internally) |
| `api/chat/verse_grounding.py` | Ensure the corrected text and its spans are produced together |
| `frontend/src/lib/verseExtraction.ts` (+ renderer) | Span-based path behind a flag; regex retained as fallback |
| `frontend/src/lib/api.ts` | Parse the new completion field |
| `api/tests/test_chat_citation_spans.py` | **New** |
| `docs/AUDIT_PLAYBOOK.md` | Parity-ledger note |

## Alternative (cheaper, weaker) — record why it was not chosen

Extend `scripts/generate_localized_book_map.py` to emit a **Swift** book-name map alongside the
Kotlin one it already generates for `android/.../utils/LocalizedBookToEnglish.kt`, and hand-port the
grammar to Swift. This is mechanical and CI-guardable (the generator already has a `--check` mode
wired into `test_update.yml`) — but it solves only the *map*. The regex **grammar** is the part
BITB-059 has not touched (its Phase 3), and a hand-ported Swift grammar is precisely the fourth
dialect this story exists to avoid. Keep it as the fallback if the span contract slips, and state
plainly in the decision record that the fallback accepts a fourth grammar.

## Out of Scope

- Deleting the backend, web, or Android regex parsers (BITB-059 Phase 3).
- Mid-stream/partial-content spans (see *Known limitation*).
- The non-streaming `POST /api/v1/chat` response — Android and iOS both use
  `/api/v1/chat/stream` (`android/.../data/remote/api/BibleApiService.kt`). Add it there only if a
  consumer appears.
- Changing `verses_cited` semantics. It also feeds feedback logging
  (`api/routes/feedback.py:78`); repurposing it would break that quietly.

## Related

- **BITB-059** — parser unification; this story delivers the server-side option its *Out of scope*
  section defers, and a fourth client is the stated revisit trigger.
- **BITB-087** — the iOS client that depends on this.
- **BITB-085** — the decision record that must name this as a hard prerequisite.
- `docs/audits/2026-07-adversarial-audit.md` — A1 (CRITICAL), E13 (nested-quantifier benchmark).
