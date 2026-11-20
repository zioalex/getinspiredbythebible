---
id: BITB-353
status: todo
priority: P1
size: S
created: 2026-11-20
---

# BITB-353: Privacy Policy Must Disclose Azure AI Content Safety Before It Is Enabled

**Prompted by:** BITB-294 (provisions Azure AI Content Safety, shipped switched off).

## Problem

`frontend/public/legal/privacy-policy*.md` (11 languages) discloses Azure OpenAI only for
embeddings. BITB-294 can send user message text to Azure AI Content Safety as a moderation failover
hop (BITB-292 `azure`), which the policy does not mention. The policy must disclose it before the
owner sets `enable_azure_content_safety = true`.

## Acceptance criteria

- [ ] Prose disclosure plus a third-party table row for Azure AI Content Safety in all 11 locales
- [ ] `lastUpdated` bumped in each policy
- [ ] Test in `frontend/src/test/legal-pages.test.tsx` (like the BITB-309 block) asserting all 11 locales mention it

## Related

BITB-294, BITB-309, BITB-328.
