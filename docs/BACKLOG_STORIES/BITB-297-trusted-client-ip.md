# BITB-297: Trusted Client IP — Close the Local-Only Bypass and Stop Keying Limits on a Forged Header

**Status:** 🔍 In Review — built and independently verified; owner production checks pending
**Priority:** P0
**Size:** M
**Created:** 2026-11-11
**Prompted by:** [2026-11-11 verified review](../audits/2026-11-11-verified-review.md) rows R1, R2, R3, P5.
**Plan:** [2026-11-11 improvement plan](../audits/2026-11-11-improvement-plan.md), wave 1.
**Commit:** `fix(api): derive the client IP from trusted proxies only (BITB-297)`

## Problem

Observed in production on 2026-11-11:

```text
GET https://api.voxquieta.org/health                                  -> 403
GET https://api.voxquieta.org/health  -H "X-Forwarded-For: 127.0.0.1" -> 200 (full component report)
```

Three copies of the same logic take the **first** `X-Forwarded-For` entry as the client:

- `api/utils/local_only.py:40-64` (`get_client_ip`) — guards `/health` and
  `/debug/embeddings`; `:87` additionally admits the literal string `testclient`.
- `api/utils/security.py:180-196` (`get_client_ip`) — the key for every per-IP rate limit
  and for security-violation logs.
- `api/utils/turnstile.py:182-192` (`_get_client_ip`) — sent to Cloudflare as `remoteip`,
  and used by `api/middleware/access_audit.py:202`.

`api/main.py:510` reads the raw header again for client-error logs.

The live result proves the client-supplied leftmost entry survives both Cloudflare and
the Azure Container Apps ingress. Consequences:

- Anyone can read the detailed health report, and each call makes a paid LLM call and a
  paid embedding call (`api/routes/health.py:91-180`). `/debug/embeddings` is open the
  same way.
- Per-IP rate limits can be reset at will by changing the header, and each fake IP
  writes rows into `rate_limit_hits`.
- `api/Dockerfile:57` uses the paid `/health` endpoint as the container health check.

## Topology (what is known)

`client → Cloudflare → Azure Container Apps ingress (Envoy) → uvicorn`. The Container
Apps FQDN is also reachable directly (the monitors use it), so Cloudflare-only headers
such as `CF-Connecting-IP` cannot be trusted on their own. Microsoft's documentation
disagrees with itself on whether the ingress appends to or overwrites
`X-Forwarded-For`; the design below is correct in both cases, and requirement 6 gives
the owner a way to see the real chain.

## Decisions already made

1. **One resolver, right-to-left.** Build the chain `XFF entries + [socket peer]`; walk
   from the right; skip every entry inside a trusted-proxy network; the first entry that
   is not trusted is the client.
2. **Trusted networks by default:** loopback, RFC 1918, `100.64.0.0/10`, `fc00::/7`
   (the ingress hop) plus Cloudflare's published IPv4/IPv6 ranges. Configurable through
   one setting.
3. **`CF-Connecting-IP` is a fallback only**: used when every chain entry is trusted
   *and* the last forwarded hop is inside a Cloudflare range.
4. **`X-Real-IP` is ignored.** Nothing in this topology sets it.
5. **No string special-cases.** `testclient` is removed; tests pass a client address or
   override the dependency.
6. **Unparseable entries are untrusted** and returned as-is, so they can never be
   mistaken for a local address.

## Requirements

1. New `api/utils/client_ip.py` exporting `resolve_client_ip(request) -> str`
   implementing decisions 1–6. Pure function of headers, peer and settings; no I/O.
2. New setting `trusted_proxy_cidrs: list[str]` in `api/config.py` with the defaults from
   decision 2, validated at `Settings()` start-up (an invalid CIDR is a start-up error).
   Keep the Cloudflare list in one constant with the date it was copied and the source
   URL `https://www.cloudflare.com/ips/`. Add the variable to `scripts/env-manifest.yaml`.
3. Replace all three copies and the raw read in `api/main.py:510` with the resolver.
   Keep thin wrappers under the old names if other modules import them (grep first:
   `get_client_ip`, `_get_client_ip`).
4. `require_local_access` (`api/utils/local_only.py`) uses the resolver, drops the
   `testclient` branch, and keeps the existing debug-mode rule for an empty address.
5. `api/Dockerfile:57` health check switches to `/health/live`.
   `.github/workflows/azure-deploy.yml:1268-1269` probes `https://$domain/health` after
   deploy — read that step and make sure it still passes (it should accept `403`, or be
   pointed at `/health/live`).
6. New probe-secret-gated endpoint `GET /api/v1/admin/request-chain`, following the
   existing pattern in `api/routes/admin.py` (`is_monitor_probe`, fail closed). It
   returns `{"x_forwarded_for": [...], "peer": "...", "cf_connecting_ip": "...",
   "resolved": "..."}` for the calling request and nothing else. This is how the owner
   confirms the real chain in production.
7. Update `docs/SECURITY.md` (or the doc that describes rate limiting — read first) with
   the trust model in five lines.

## Tests (minimum)

Table-driven unit tests for the resolver, each row = headers + peer → expected IP:

| Case | `X-Forwarded-For` | Peer | Expected |
|---|---|---|---|
| Via Cloudflare, forged left entry | `127.0.0.1, 203.0.113.9, <cloudflare ip>` | `10.0.0.5` | `203.0.113.9` |
| Direct to Container Apps, forged | `127.0.0.1, 203.0.113.9` | `10.0.0.5` | `203.0.113.9` |
| Ingress overwrote the header | `<cloudflare ip>` + `CF-Connecting-IP: 203.0.113.9` | `10.0.0.5` | `203.0.113.9` |
| Forged private entries only | `10.1.1.1, 192.168.0.1, 203.0.113.9` | `10.0.0.5` | `203.0.113.9` |
| No header, local peer | — | `127.0.0.1` | `127.0.0.1` |
| No header, public peer | — | `203.0.113.9` | `203.0.113.9` |
| Garbage entry | `not-an-ip` | `10.0.0.5` | `not-an-ip` (and not local) |
| IPv6 client | `2001:db8::1, <cloudflare ipv6>` | `10.0.0.5` | `2001:db8::1` |
| `CF-Connecting-IP` forged on a direct hit | `203.0.113.9` + `CF-Connecting-IP: 127.0.0.1` | `10.0.0.5` | `203.0.113.9` |

Plus:

- `require_local_access`: forged `127.0.0.1`, forged `testclient`, forged `10.0.0.1`
  from a public peer → `403`; loopback peer with no header → `200`.
- Rate limiter integration: 21 requests from one real client that rotates the left-most
  header value hit the per-IP limit on the 21st.
- `/admin/request-chain`: `401` without the secret, correct payload with it.
- Every existing test that relied on `testclient` or on a left-most header is migrated,
  not deleted (`grep -rln "testclient\|X-Forwarded-For" api/tests` lists 12 files).

## Acceptance criteria

- [ ] One resolver; no other code reads `X-Forwarded-For`, `X-Real-IP` or
      `CF-Connecting-IP` (`grep -rn "X-Forwarded-For\|X-Real-IP" api --include=*.py`
      outside tests returns only `utils/client_ip.py`)
- [ ] The string `testclient` no longer appears in non-test code under `api/`
- [ ] All table cases pass
- [ ] Container health check no longer triggers LLM or embedding calls
- [ ] **Owner step:** after deploy, `curl -H "X-Forwarded-For: 127.0.0.1" https://api.voxquieta.org/health` returns `403`
- [ ] **Owner step:** call `/api/v1/admin/request-chain` through `api.voxquieta.org` and
      through the Container Apps FQDN with the probe secret; paste both payloads (IPs
      redacted) into this story; adjust `TRUSTED_PROXY_CIDRS` if the chain differs
- [ ] This satisfies the "trusted-proxy chain is verified" criterion on BITB-118 and
      BITB-156 — tick it there with a link to this story once the owner step is done

## Out of scope

- Replacing the per-session lifetime cap (a client-chosen `session_id` is not a security
  boundary; that product decision stays with BITB-118/BITB-156).
- Restricting the Container Apps FQDN to Cloudflare only.
- Refreshing the Cloudflare range list automatically (file a follow-up if the owner
  wants it; the list changes rarely).

## Related

BITB-118, BITB-156, BITB-298, July audit O5.

## Implementation notes (2026-11-11)

Built as specified, with these additions from verification:

- The trusted-proxy setting is a comma-separated string (`TRUSTED_PROXY_CIDRS`), the
  repo's convention for list-like settings; it cannot be empty or contain a network
  broader than `/8` (IPv4) or `/7` (IPv6).
- Repeated forwarded-for header lines are joined before the walk.
- A request that passed a Cloudflare hop never resolves to a loopback or private address;
  `CF-Connecting-IP` is accepted only if it names a non-proxy address.
- With no socket peer the header is not believed (`unknown`); a literal `unknown` entry
  resolves to `invalid`, so it cannot hit the debug-mode rule.
- The local-only gate rejects **every** request that carries a forwarded-for header.
  This goes beyond the story's table ("forged private entries" would otherwise still be
  judged by address) and removes any dependence on how the ingress rewrites the header.

## Follow-ups

- BITB-308 — lock the origin to Cloudflare (residual risk: a sender on a Cloudflare
  address can present a forged public client address).
