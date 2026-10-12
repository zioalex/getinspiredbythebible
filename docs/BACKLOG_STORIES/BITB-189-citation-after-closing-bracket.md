# BITB-189: Backend Misses a Citation Directly After a Closing Bracket (`「…」约翰福音3:16`)

**Status:** 🎯 Todo
**Priority:** P2
**Size:** S
**Created:** 2026-10-12
**Prompted by:** BITB-179 follow-up — found while writing the fullwidth grounding test (the test had
to insert a space after `」`).

## Bug Report

A citation that directly follows a closing quote or bracket is not detected by the backend, but is
detected by the web parser. Checked on `main` (cb63e88) on 2026-10-12:

| Input | Backend `extract_references` | Web `extractVerseReferences` |
| ----- | ---------------------------- | ---------------------------- |
| `「神爱世人」约翰福音3:16。` | none | `john 3:16` |
| `「神爱世人」约翰福音3：16` | none | `john 3:16` |
| `」John 3:16` | none | `john 3:16` |
| `「神爱世人」 约翰福音3:16` (space) | `John 3:16` | `john 3:16` |

Chinese text quotes a verse and then cites it with no space, so this is a common form in answers.
A missed reference means no lookup, no passage context (BITB-178) and no grounding (BITB-053): the
model's quote is shown unchecked. Cause: the backend `_VERSE_PATTERN` uses a positive-whitelist
lookbehind (AGENTS.md *Common Pitfalls* #2) that admits opening brackets and CJK characters but not
closing brackets; web and Android use a letter-negative boundary.

## Functional Requirements

- FR1 Accept a closing bracket/quote (`」』》）)]"'` and their fullwidth forms) immediately before a
  book name in the backend, matching the web/Android boundary behaviour.
- FR2 No new false positives (e.g. a closing bracket followed by a non-book word and digits).

## Acceptance Criteria

- [ ] The four inputs above produce `John 3:16` in the backend, web and Android (shared corpus cases)
- [ ] Grounding integration test through `chat()` and `chat_stream()` for `「…」约翰福音3：16` with no space
- [ ] 11-language corpus does not regress; boundary parity documented in AGENTS.md pitfall #2
