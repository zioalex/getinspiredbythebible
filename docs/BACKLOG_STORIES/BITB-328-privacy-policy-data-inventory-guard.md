---
id: BITB-328
status: in-progress
priority: P2
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

## Spec (Stage 0, confirmed with the owner 2026-11-16)

**User story:** As the operator, I want every place user-derived data is stored or sent to be
listed in one inventory that CI checks against the code and the privacy policy. A new store,
capture flag, retention period or third-party flow should then fail CI until the policy discloses it.

### Decisions (owner interview)

- **Anchors:** HTML comments `<!-- data:<id> -->` on their own line before each disclosing
  bullet or paragraph, in all 11 `frontend/public/legal/privacy-policy*.md`. react-markdown
  (no rehype-raw) drops them. A frontend test proves no anchor text renders.
- **Model check:** every SQLAlchemy `__tablename__` under `api/` must be in the inventory.
  The scripture reference tables in `api/scripture/models.py` are excluded by module, not
  listed one by one. Any other new table fails until it is classified.
- **Host check:** scan non-test `api/**/*.py` and `scripts/**/*.py` for `https?://host`
  literals, plus the defaults of URL-typed settings in `api/config.py`. Each host must be an
  inventory third party or listed under `non_user_data_hosts` with a reason. Suffix match is
  allowed for Azure (`*.openai.azure.com`, `*.cognitiveservices.azure.com`,
  `*.api.cognitive.microsoft.com`).
- **Retention tests:** cover all TTL stores (blocked samples, retrieval misses, feedback 30/90,
  contact 90). Reuse the existing tests and add only the missing ones.
- **Undisclosed flows found during Specify:** disclose only the ones enabled in prod:
  - the church finder (the location you type goes to disciplestoday.org): **disclose**;
  - Cloudflare Turnstile (on in prod, `turnstile_enabled = true`; sends a challenge token
    and your IP to challenges.cloudflare.com): **disclose**;
  - Azure Content Safety (`azure_content_safety_enabled` default `False`, not set in
    Terraform): inventory entry with `disclosure: disabled`. The guard fails if its config
    default turns `True` or a Terraform variable or tfvars entry enables it, unless the
    entry is disclosed.
- **Android inline retention strings** (e.g. `contact_privacy_note`): out of scope, follow-up story.

### Functional requirements

1. `docs/privacy/data-inventory.yaml` holds the inventory: `stores`, `third_parties`,
   `non_user_data_tables` (optional, for non-scripture exclusions), and `non_user_data_hosts`.
   Each store or third-party entry has: `id`, `kind` (`db_table` | `third_party` | `on_device`
   | `external`), `table` or `hosts`, `contains` (list from a fixed vocabulary: `message_text`,
   `reply_text`, `comment_text`, `email`, `location_text`, `ip_address`, `session_hash`,
   `derived_only`, `aggregate_counts`, `diagnostics`), `written_by` (code paths), `flag`
   (`config` key and `terraform` variable, optional), `retention` (`config` key, `default`,
   `enforced_by`), and `disclosure` (`anchor` id, or `disabled` / `n/a` with a reason).
2. Seed entries: `blocked_message_samples`, `retrieval_miss_samples`, `feedback` (text 30 and
   row 90 as two retention entries or two anchors), `contact_submissions`, `tts_event_daily`,
   OpenRouter, Azure OpenAI, OpenAI moderation, Azure Content Safety (disabled), SMTP2GO,
   Cloudflare Turnstile, the church finder (disciplestoday.org), the Cloudflare country header
   (crisis numbers), Firebase Crashlytics and Analytics, on-device conversation history, and
   browser read-aloud (online voices). The story's "sessions and rate-limit tables" do not exist
   in the DB (rate limiting is in memory); write no entry and note that in the inventory header.
3. `scripts/check_privacy_inventory.py` (stdlib + PyYAML, AST-based, no imports of `api/`)
   exits non-zero with a clear message per violation:
   a. an inventory anchor missing from any of the 11 policy files;
   b. an anchor whose disclosure block (text up to the next anchor or heading) does not contain
      the retention default as a whole number (`(?<!\d)N(?!\d)`; locale digits are not needed,
      since all 11 files use ASCII digits; the builder verifies this);
   c. a config default (parsed from `api/config.py` by AST) that differs from the inventory
      `retention.default`;
   d. a `__tablename__` outside `api/scripture/models.py` and not in the inventory;
   e. a Terraform variable matching `*_capture_enabled` / `*_retention_days` in
      `deployment/*.tf` and not in the inventory;
   f. a scanned host not covered by `third_parties[].hosts` or `non_user_data_hosts`;
   g. a `disclosure: disabled` entry whose flag defaults to true in config, or is set true in
      `deployment/*.tf` / `*.tfvars`;
   h. an anchor present in a policy file but not in the inventory (an orphan).
4. Policy edits in all 11 languages: anchors before the existing disclosures (visible text
   unchanged), plus **new** sentences for the church finder and Turnstile (a "Data you provide"
   bullet for the church finder, a "Data collected automatically" bullet for Turnstile, and
   both in the third-party table). Bump `lastUpdated` and the visible "Last updated" date.
5. `make check-privacy-inventory` target, added to `make test`; a CI step in
   `test_update.yml` `backend-tests` (or its own small job); a pytest suite
   `scripts/tests/test_check_privacy_inventory.py` or `api/tests/test_privacy_inventory.py`
   (the builder follows whichever suite CI already runs), with one failing-fixture test per
   violation class a–h, plus a test that the real repo passes.
6. Retention-semantics tests: a repeat or update never extends `expires_at` (blocked samples:
   add one if missing; retrieval misses: already exists), and feedback/contact `created_at`
   is never updated (already exists; verify).
7. AGENTS.md: a rule under *Testing* or *Backlog Hygiene* about privacy-affecting changes.
8. `.github/pull_request_template.md`: a `## Privacy impact` checkbox section.

### Non-functional requirements

- All 11 policy languages (en, it, de, es, fr, pt, ar, ru, zh, hi, ko) get the same anchors
  and the new sentences, translated idiomatically. RTL Arabic and CJK files keep their structure.
- The guard runs in under 5 s with no DB or network.
- No visible change to existing policy text except the two new disclosures and the date.

### Acceptance criteria

- [ ] `docs/privacy/data-inventory.yaml` exists with every entry above; `make check-privacy-inventory` passes on the repo.
- [ ] The guard has one failing test per class a–h (missing anchor, retention mismatch in policy,
      config default mismatch, undisclosed model, undisclosed Terraform flag/retention var,
      undisclosed host, enabled-but-disabled-disclosure, orphan anchor) and one passing test on the real repo.
- [ ] The guard runs in `make test` and in CI on every PR.
- [ ] All 11 policy files carry identical anchor sets; a vitest test proves no `data:` anchor
      text appears in the rendered privacy page.
- [ ] The church finder and Turnstile are disclosed in all 11 languages; the date is bumped.
- [ ] Retention-semantics tests exist for blocked samples, retrieval misses, feedback and contact.
- [ ] AGENTS.md rule and PR-template "Privacy impact" section added.
- [ ] Owner step: review the seeded inventory and the new policy sentences (church finder,
      Turnstile) for anything stored outside this repo (Azure diagnostics, Cloudflare logs).

### Out of scope

- Android/web inline retention notices (follow-up story).
- Data held outside the repo's control (Azure diagnostic logs, Cloudflare logs): owner step.
- Enabling Azure Content Safety.

### Open questions

- None blocking. If the policy wording for Turnstile/church finder needs a legal touch, the owner reviews it in the PR.

## Plan (Stage 1)

| File | Change |
| --- | --- |
| `docs/privacy/data-inventory.yaml` | New; schema above, seeded entries. |
| `scripts/check_privacy_inventory.py` | New guard, checks a–h, `--repo-root` arg for tests. |
| `scripts/tests/test_check_privacy_inventory.py` (or the dir CI already runs) | Fixture-repo tests for a–h + real-repo pass. |
| `frontend/public/legal/privacy-policy*.md` (11) | Anchors; church finder + Turnstile sentences + table rows; date. |
| `frontend/src/test/legal-pages.test.tsx` | Anchors are identical across locales and absent from the rendered text; church finder/Turnstile disclosed. |
| `api/tests/test_blocked_samples.py` | Repeat-upsert does not touch `expires_at` (if missing). |
| `Makefile` | `check-privacy-inventory` target; add to `test`. |
| `.github/workflows/test_update.yml` | Run the guard and its tests. |
| `AGENTS.md`, `.github/pull_request_template.md` | Rule + Privacy impact section. |
| `docs/BACKLOG_STORIES/BITB-330-*.md` | Follow-up: Android/web inline retention notices under the guard. |

**Verify:** `make check-privacy-inventory`; the guard's pytest suite; `cd api && python -m pytest
tests/test_blocked_samples.py tests/test_retrieval_misses.py tests/test_feedback_retention.py -q`;
`cd frontend && npx vitest run src/test/legal-pages.test.tsx && npm run lint && npx tsc --noEmit`;
`make backlog-check`.
