---
id: BITB-308
status: todo
priority: P2
size: M
rank: 10
created: 2026-11-11
---

# BITB-308: Lock the Backend Origin to Cloudflare (No Direct Container Apps Access)

**Prompted by:** BITB-297 verification, finding 2.

## Problem

The backend's Container Apps FQDN answers requests that never passed through Cloudflare
(the monitors use it on purpose). BITB-297 made client-IP resolution robust against forged
headers, but it has to trust Cloudflare's address ranges as proxies. A sender that
connects to the FQDN *from* a Cloudflare address — for example a Cloudflare Worker — is
therefore a trusted hop, and whatever it puts to the left of itself in the forwarded-for
chain is taken as the client.

What BITB-297 already guarantees in that case: the result is never a loopback or private
address, and the local-only gate rejects every forwarded request, so `/health` and
`/debug/embeddings` stay closed. What remains: such a sender may be able to present a
forged *public* client address and so dodge per-IP rate limits. Whether Cloudflare lets a
Worker set that header on outbound requests was not verified.

Bypassing Cloudflare also skips its bot protection and WAF for anyone who knows the FQDN.

## Acceptance criteria

- [ ] Decide the mechanism (owner): Cloudflare Authenticated Origin Pulls (mTLS), a
      shared secret header added by a Cloudflare Transform Rule and checked by the app, or
      a Container Apps ingress IP allow-list of Cloudflare's ranges
- [ ] Requests to the Container Apps FQDN that did not come through the project's own
      Cloudflare zone are rejected
- [ ] Monitors that call the FQDN directly (`prod-monitor.yml`, the Azure availability
      tests in `deployment/main.tf`, the post-deploy checks in `azure-deploy.yml`) keep
      working — moved to the public hostname or given the secret
- [ ] `docs/SECURITY.md` "Client IP trust model" drops the residual-risk note
- [ ] Owner step: verify with `GET /api/v1/admin/request-chain` before and after

## Notes

An IP allow-list alone does not close the Worker case (a Worker also egresses from
Cloudflare ranges); mTLS or a zone-specific secret does.

## Related

BITB-297, BITB-005, BITB-298.
