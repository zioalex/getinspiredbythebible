---
id: BITB-362
status: in-review
priority: P2
size: S
created: 2026-11-26
prs: [1342]
---

# BITB-362: Allow Agent-Pod Egress to the llama.cpp LLM Provider (Supplemental Strict-Tier LAN Opt-In)

## User story

As the owner of the KubeOpenCode home cluster, I want opencode to use the
privately-hosted llama.cpp server (an OpenAI-compatible endpoint serving
`unsloth/gemma-4-26B-A4B-it-GGUF:UD-Q4_K_M`, model id `llama-cpp/gemma-4-26b`)
as an LLM provider, so the agents get a self-hosted provider option — without
opening the LAN.

## Context

- The strict tier (`agent-egress-strict`, BITB-152) denies RFC1918/link-local/
  loopback destinations by construction: its public-internet rule carries the
  `except` list. The llama server is a private-range host, so agent pods cannot
  reach it and `llama-cpp` provider calls from opencode fail.
- `docs/SECURITY-KUBEOPENCODE.md` → *LAN opt-in* prescribes the fix pattern:
  "Add a supplemental NetworkPolicy opening only that IP:port." Nothing
  realized that pattern in the repo until this story.
- Applying anything to the cluster is an owner action: the agent pod has no
  kubectl egress to the API server and no write on `networkpolicies` — the
  operator-only boundary that keeps the strict tier meaningful.

## What this PR delivers

1. `k8s/kubeopencode/networkpolicy-allow-llama-egress.yaml` — `agent-egress-llama`,
   namespace `kubeopencode-system`, sibling tier labels
   (`app.kubernetes.io/part-of: kubeopencode`, `kubeopencode.io/tier: strict`),
   `podSelector` identical to `agent-egress-strict`; ONE egress rule to ONE
   `ipBlock` peer — the llama server host as a single `/32` — with a single
   ports entry, TCP/8080. Nothing broader: no other port, no wider CIDR, no
   other pods.
2. T9 tests in `scripts/test_kubeopencode_netpol.py` pin the scope so it cannot
   drift: a supplemental may never be a pod's only egress policy, never select
   pods no tier policy covers, must stay one-rule/one-peer/`/32`/one-port, must
   select agent pods exactly as the agent tier does, and must carry the tier
   metadata. The T1 partition tests now assert over the tier policies only
   (supplementals stack on top of the partition).
3. Docs: a Files row and the apply order in `k8s/kubeopencode/README.md`, plus
   the *What strict allows* list, the *LAN opt-in* section and the rollout
   order in `docs/SECURITY-KUBEOPENCODE.md` — the new manifest applies with
   the other allow-policies, BEFORE `networkpolicy-default-deny.yaml`.

## Acceptance criteria

- [x] Manifest exists with exactly one egress rule, one `/32` `ipBlock` peer
      (the llama server host), one ports entry (TCP/8080), a `podSelector`
      identical to `agent-egress-strict`, and the sibling labels/namespace
- [x] `make test-kubeopencode-netpol` green (23 tests, including the new T9
      guards)
- [x] README and security doc enumerate the policy, its scope, and its place
      in the apply order (before `networkpolicy-default-deny.yaml`); a reader
      with none of the authoring session's context can find and apply it
- [ ] (Owner step) Apply in the documented order, then run the connectivity
      probe and the opencode end-to-end check below

## Owner apply step (unticked)

From `k8s/kubeopencode/`, with the other allow-policies, before default-deny:

```bash
kubectl apply -f networkpolicy-egress-strict.yaml
kubectl apply -f networkpolicy-egress-server.yaml
kubectl apply -f networkpolicy-allow-server-ingress.yaml
kubectl apply -f networkpolicy-allow-llama-egress.yaml
kubectl apply -f networkpolicy-default-deny.yaml
```

Verify from an agent pod — the llama server address is read from the live
opencode config, never hardcoded here:

```bash
LLAMA_IP=$(jq -r '.provider."llama-cpp".options.baseURL' /workspace/opencode.json | cut -d/ -f3 | cut -d: -f1)
POD=$(kubectl -n kubeopencode-system get pod -l app.kubernetes.io/managed-by=kubeopencode \
  -o jsonpath='{.items[0].metadata.name}')
kubectl -n kubeopencode-system exec "$POD" -- \
  curl -s -o /dev/null -w '%{http_code}\n' -m 5 "http://${LLAMA_IP}:8080/v1/models"   # expect 200
```

Then the opencode end-to-end probe with the provider's model:

```bash
opencode run --model llama-cpp/gemma-4-26b "Reply with the single word: ping"
```

## Out of scope

- Any other LAN host or port; per-domain egress filtering (Cilium `toFQDNs` or
  an egress proxy) — the security doc's noted future migration
- Changing `agent-egress-strict` or the partition policies
- Wiring `llama-cpp` into agent fallback chains (an opencode config change,
  governed by the BITB-280 live-config gate — file separately if wanted)

## References

- `docs/SECURITY-KUBEOPENCODE.md` → *LAN opt-in* (the pattern this realizes)
- BITB-152 (strict tier), BITB-285 (`k8s/kubeopencode/` is the canonical home)
- `scripts/test_kubeopencode_netpol.py` (regression classes T1–T9)
