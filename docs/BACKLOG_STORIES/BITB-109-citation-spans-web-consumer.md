# BITB-109: Make the Citation-Span Contract Real — a Client That Consumes It

**Status:** 🎯 Todo
**Priority:** P2 — until a client consumes `citations`, the backend contract is shipped but unused,
and its correctness is only asserted by its own tests
**Size:** M
**Created:** 2026-08-22
**Prompted by:** PR #985 (BITB-086), which ships the backend half and defers both client-side
acceptance criteria
**Unblocks:** BITB-087; this is a hard prerequisite for starting the iOS client.
**Part of:** the iOS delivery plan — Stage 3 of BITB-084 → BITB-085 → BITB-086 → **BITB-109** → BITB-087 → BITB-088.

## User Story

**As** a web user, **I want** verse links rendered from the server's citation spans rather than a
browser-side regex, **so that** linkification matches what the backend actually resolved — and **as**
the maintainer, so the fourth client (iOS, BITB-087) inherits a contract that has been proven by a
real consumer rather than one that has only ever been unit-tested.

## Why This Exists

PR #985 delivers the server contract and is explicit that two acceptance criteria remain, both
client-side:

> - [ ] Web consumes `citations` behind a flag, produces byte-identical rendered output to the regex
>   path for the shared corpus, and falls back cleanly when the field is absent. **Deferred** — PR
>   #983 (BITB-059, unmerged) already touches `verseExtraction.ts`/`versePatterns.ts`; this ships as
>   the immediate fast-follow once #983 merges rather than fighting it for the same files.
> - [ ] A client given deliberately corrupt spans (offsets past end-of-string, mismatched `text`,
>   overlapping ranges) renders plain text and does not crash or duplicate content. **Deferred**
>   with the web consumer above — it's a client-side guarantee.

The deferral was the right call — two PRs editing `verseExtraction.ts` simultaneously is a
predictable conflict. But the consequence is that `citations` currently ships to nobody. Web and
Android still linkify with their own regexes, so the contract's real-world correctness is untested,
and BITB-087 (iOS) is planned to depend on a contract no client has exercised.

The blocker named in the deferral is **PR #983 merging**. Once it does, this is unblocked.

## Proposed Fix

1. **Consume `citations` in the web client behind a flag**, with the regex path retained as the
   fallback and used automatically whenever the field is absent (older backends, cached responses).
2. **Prove parity, don't assume it.** Render both paths over the shared cross-platform corpus
   (`tests/fixtures/`, PR #906) and assert byte-identical output. Any divergence is a finding about
   the *backend* contract as much as the client — which is exactly the value of having a real
   consumer.
3. **Harden against corrupt spans.** The contract is deliberately self-verifying: each span carries
   `text` and `occurrence` so a client can check `message[start:end] == text` and, on mismatch,
   recover by locating the `occurrence`-th literal match. Implement that check and its fallback, then
   test it adversarially — offsets past end-of-string, mismatched `text`, overlapping ranges — and
   assert the output degrades to plain text without crashing or duplicating content.
4. **Update the parity ledger.** `docs/AUDIT_PLAYBOOK.md` currently records that a server-authoritative
   path exists "(backend only, so far)". Once web consumes it, that row should say which clients use
   it.

## Known Contract Gap to Carry Forward

BITB-086 documents an accepted limitation: a fully-vocalized Arabic citation (tashkeel/tatweel
present) can appear in `verses_cited` but be absent from `citations`, because stripping those marks
to match the book-name table would shift the offsets out from under the spans they describe.

This is not a bug to fix here, but the web consumer must not assume `citations` is exhaustive. The
regex fallback needs to remain reachable per-message, not only per-response — otherwise Arabic users
silently lose links the old path would have rendered. Worth an explicit test.

## Acceptance Criteria

- [ ] Web consumes `citations` behind a flag; regex path retained and used when the field is absent
- [ ] Byte-identical rendered output vs. the regex path across the shared corpus
- [ ] Corrupt spans (bad offsets, mismatched `text`, overlapping ranges) render plain text — no
      crash, no duplicated content — asserted by adversarial tests
- [ ] The self-verification path (`message[start:end] == text`, else locate by `occurrence`) is
      implemented and tested, not just documented
- [ ] A vocalized-Arabic message still renders links via the fallback, proving `citations` is not
      assumed exhaustive
- [ ] `docs/AUDIT_PLAYBOOK.md` records which clients consume the server path

## Dependencies

**PR #983 (BITB-059) must merge first** — it owns `verseExtraction.ts`/`versePatterns.ts` and this
work edits the same files. That is the stated reason for the deferral, not a preference.

## Verification

Parity over the shared corpus is the headline, but the corrupt-span behaviour is the criterion that
protects users: it is what stands between a backend bug and a blank or duplicated message in
someone's browser. Test it by feeding deliberately malformed spans, not by reasoning that the backend
would never emit them — the whole point is what happens when it does.

## Related

- **BITB-086 / PR #985** — the backend contract this consumes; owns the two ACs this closes
- **BITB-059 / PR #983** — the hard dependency
- **BITB-087** — the iOS client that inherits this contract; the reason proving it now matters
- `frontend/src/lib/linkifyVerses.ts`, `frontend/src/lib/verseExtraction.ts`,
  `api/utils/verse_parser.py`, `docs/AUDIT_PLAYBOOK.md`
