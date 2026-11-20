---
id: BITB-336
status: todo
priority: P3
size: XS
created: 2026-11-16
---

# BITB-336: French Messages Still Use Informal tu While the UI Uses vous

**Follow-up of:** BITB-331 / BITB-334 (verifier findings, 2026-11-16).

## Problem

BITB-334 moved the French welcome copy to vous. `frontend/messages/fr.json` sessionLimitMessage and contentBlockedMessage (around lines 135-136) and Android `values-fr` error_content_blocked still use tu.

## Acceptance criteria

- [ ] Remaining tu-forms changed to vous on web and Android; tests/parity pass.
