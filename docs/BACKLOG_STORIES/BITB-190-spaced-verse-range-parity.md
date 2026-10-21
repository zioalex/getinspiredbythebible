# BITB-190: Verse Ranges Written With Spaces Parse Differently on Backend vs Web/Android

**Status:** 🎯 Todo
**Priority:** P3
**Size:** S
**Created:** 2026-10-12
**Prompted by:** BITB-179 follow-up — found by the independent verifier.

## Bug Report

The backend `CV_PATTERN` allows whitespace around the range separator (`\s*[-–～〜]\s*`); the web
(`versePatterns.ts`) and Android (`ChatMessageItem.kt`) patterns do not. Checked on `main` (cb63e88):

| Input | Backend | Web / Android |
| ----- | ------- | ------------- |
| `John 3:16 - 18` | `John 3:16-18` | `John 3:16` (the `- 18` stays plain text) |
| `John 3:16 ～ 18` | `John 3:16-18` | `John 3:16` |
| `约翰福音3：16 ～ 18` | `John 3:16-18` | `John 3:16` |

So the backend grounds and fetches the whole range, while the chat link and the cited-verse matching
on web/Android cover only the first verse.

## Functional Requirements

- FR1 Pick one behaviour for all three parsers. Recommended: accept optional whitespace around the
  range separator everywhere (it is the backend's behaviour and how people write ranges), bounded to
  a single space run so no new ReDoS surface. Decide in Spec.
- FR2 The link label covers the whole range; URLs stay ASCII (BITB-179).

## Acceptance Criteria

- [ ] The inputs above give the same reference in all three parsers (shared corpus cases)
- [ ] No false positives on prose like `John 3:16 - 18 people came` beyond what the backend already
      accepts; ReDoS tests still pass
