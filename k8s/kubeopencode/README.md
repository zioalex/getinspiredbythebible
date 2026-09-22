# kubeopencode config

Kubernetes manifests and docs for running the `default-wf2` opencode agent on the
home k3s cluster (namespace `kubeopencode-system`), plus mobile access and the
custom-opencode-image workflow.

> **No secrets are committed here.** The manifests reference Kubernetes Secrets by name;
> create those out-of-band (commands below). Never commit real tokens/passwords.

## Files

| File | What it is |
|---|---|
| `agent-default-wf2.yaml` | The `Agent` (opencode server), secured with `OPENCODE_SERVER_PASSWORD`; set `agentImage` here to pin the opencode version. |
| `service-mobile.yaml` | Stable Service both remote paths target (also carries Tailscale annotations). |
| `cloudflared-deployment.yaml` | In-cluster `cloudflared` connector (token mode) for the Cloudflare WARP + private-route path. |
| `mobile-access.md` | Plan/runbook for reaching the agent from the phone app (Cloudflare WARP + Tailscale). |
| `custom-opencode-image.md` | How to build/publish a custom agent image to run a newer opencode. |

## Secrets to create (not stored in git)

```bash
# provider key (OpenCode Zen)
kubectl -n kubeopencode-system create secret generic ai-credentials \
  --from-literal=api-key='<opencode-zen-key>'

# opencode server Basic-auth password (mobile app)
kubectl -n kubeopencode-system create secret generic opencode-server-auth \
  --from-literal=password="$(openssl rand -hex 20)"

# cloudflared tunnel token (Cloudflare path only)
kubectl -n kubeopencode-system create secret generic cloudflared-token \
  --from-literal=token='<tunnel-token>'

# GHCR pull secret (only if the custom agent image is private)
kubectl -n kubeopencode-system create secret docker-registry ghcr-pull \
  --docker-server=ghcr.io --docker-username=<user> \
  --docker-password='<PAT read:packages>' --docker-email=<email>
```

## Apply order

```bash
# 1. secrets (above)
# 2. agent + service
kubectl apply -f agent-default-wf2.yaml
kubectl apply -f service-mobile.yaml      # paste the live selector first — see file header
# 3. mobile remote access (pick Cloudflare and/or Tailscale) — see mobile-access.md
kubectl apply -f cloudflared-deployment.yaml
```

See `mobile-access.md` for the full mobile flow and `custom-opencode-image.md` for
updating opencode.
