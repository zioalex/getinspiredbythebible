# BITB-267: Backend Verse Parser Misses a Citation After `**`, `—` or `¿`

**Status:** 🎯 Todo
**Priority:** P3
**Size:** S
**Created:** 2026-11-05
**Prompted by:** BITB-189 — the backend whitelist lookbehind was widened to closing brackets/quotes,
but other non-letter starts remain a backend-vs-web/Android boundary gap.

## Bug Report

The backend `_VERSE_PATTERN` uses a positive-whitelist lookbehind (AGENTS.md *Common Pitfalls* #2);
web and Android use a letter-negative boundary. Starts that are neither whitelisted nor letters are
therefore detected by web/Android but not by the backend:

| Input | Backend | Web / Android |
| ----- | ------- | ------------- |
| `**John 3:16**` | none (to verify) | `john 3:16` |
| `—John 3:16` | none (to verify) | `john 3:16` |
| `¿Juan 3:16?` | none (to verify) | `john 3:16` |

Re-verify against `main` before fixing: a missed backend reference means no lookup, passage context
or grounding for that citation.

## Functional Requirements

- FR1 Accept `*`, dashes (`-`, `–`, `—`) and `¿` / `¡` immediately before a book name in the backend.
- FR2 Keep the whitelist approach; letter/digit/underscore-glued starts (`abcJohn`, `_John`, `3John`)
  stay rejected, and no new false positives.

## Acceptance Criteria

- [ ] The three inputs above produce `John 3:16` in backend, web and Android (shared corpus cases)
- [ ] Parametrized 11-language backend test; letter-glued guards unchanged
- [ ] AGENTS.md pitfall #2 note about the known gap removed
