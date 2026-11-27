---
id: BITB-328
status: todo
priority: P2
kind: nfr
size: M
created: 2026-11-16
depends_on: [BITB-326]
---

# BITB-328: Keep the Privacy Policy and the Code in Sync with a Data Inventory and a CI Guard

**Prompted by:** BITB-326 (PR #1303, 2026-11-16). Turning on blocked-message capture exposed
two policy mismatches that no check caught:

1. The code refreshed the 30-day expiry on every repeat, so a record could outlive the
   policy's "up to 30 days".
2. Two bullets said chat messages are "not stored" while a third said blocked messages are
   kept.

PR #1303 fixes both and adds point tests for this one store. Nothing prevents the next new
store, TTL or flag from drifting the same way. BITB-309 (OpenAI disclosure) was the same class
of gap.

## Proposal

1. **Data inventory**, `docs/privacy/data-inventory.yaml`, the single source of truth. One
   entry per place user-derived data is stored or sent. Fields:
   - store or table, or third party;
   - what it contains (`message_text`, `derived_only`, `hash`, …);
   - the code path that writes it;
   - the enabling flag (config key and the Terraform variable, if any);
   - retention: the config key, its default, and how it is enforced (TTL column,
     sweep job, pg_cron job, provider terms);
   - the policy section/bullet id that discloses it.

   Seed it with what exists today:
   - `blocked_message_samples` (BITB-326);
   - `retrieval_misses` (BITB-256);
   - `sessions` and rate-limit tables;
   - the feedback tables;
   - read-aloud counts;
   - OpenRouter, Azure OpenAI, OpenAI moderation and Azure Content Safety;
   - Firebase/Crashlytics;
   - on-device conversation history.
2. **Stable anchors in the policy**, for example `<!-- data:blocked_message_samples -->` before
   each disclosing bullet in all 11 translations. Markdown comments don't render.
3. **CI guard**, `scripts/check_privacy_inventory.py`, run in CI and by `make test`:
   - every inventory entry has its anchor in all 11 policy files, and the retention number
     next to it equals the config default;
   - every SQLAlchemy model with a text column holding user input (or any column listed as
     user-derived) appears in the inventory;
   - every Terraform variable named `*_capture_enabled` / `*_retention_days` and every
     third-party host the backend calls appears in the inventory.

   A new store, flag or provider fails CI until it is disclosed.
4. **Retention-semantics tests:** each TTL store has a test that a repeat or update never
   extends retention past the disclosed limit.
5. **AGENTS.md rule:** a change that adds or alters stored user data, a capture flag, a
   retention period or a third-party data flow must update the inventory and the privacy policy
   in all 11 languages in the same PR. The PR description lists the changed policy sentences for
   owner review.
6. **PR template:** a "Privacy impact" checkbox section.

## Acceptance criteria

- [ ] Inventory covers all current stores and providers. The guard runs in CI and fails on:
      a missing anchor, a retention mismatch, an undisclosed model or flag, and an undisclosed
      provider host (one test each).
- [ ] Anchors added to all 11 policy files without changing visible text.
- [ ] AGENTS.md rule and PR-template section added.
- [ ] Owner step: review the seeded inventory for anything stored outside this repo
      (Azure diagnostics, Cloudflare logs).
