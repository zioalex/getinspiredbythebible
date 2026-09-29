# Mobile access to the kubeopencode agent — Plan, Story & Implementation

Reach the **default-wf2** agent's opencode server from the Android app
(`cc.agentlabs.opencode`) — securely, from your phone, on Wi‑Fi and from anywhere.
Two remote paths are built in parallel: **Cloudflare (WARP + private route)** and
**Tailscale**. Both run their connectors **in-cluster as pods**.

> Decisions locked for this build:
> Cloudflare = **WARP + private route** (Gmail/Access gate kept, nothing public) ·
> current CF = **tunnel + public hostnames + Access, no WARP/private routes yet** ·
> agent = **default-wf2** · connectors = **in-cluster pods**.

---

## 1. Story

**Epic:** Operate my self-hosted AI coding agent from a mobile thin client.

### User story

> *As the operator of a single-node k3s cluster on my QNAP, I want to connect the
> opencode Android app to my `default-wf2` agent, so that I can drive agent sessions
> from my phone — on my home Wi‑Fi and remotely — without exposing a shell-capable
> server to the public internet.*

### Acceptance criteria

1. The `default-wf2` opencode server requires a password (no unsecured server).
2. On home Wi‑Fi, the app connects to the agent and `/global/health` is green.
3. Remotely, the app connects with **no service on a public hostname**:
   - **Cloudflare:** only devices enrolled in WARP under my Gmail can reach it.
   - **Tailscale:** only devices in my tailnet can reach it.
4. If one remote path breaks, the other still works (both configured).
5. Everything is reproducible from this folder (manifests + documented dashboard steps).

**Out of scope (now):** multi-user access, per-agent RBAC, exposing more than one agent.

---

## 2. Why this shape (the key constraint)

The app speaks **HTTP Basic auth only** — it is not a browser and cannot send custom
headers. So:

- Your existing **public hostname + Cloudflare Access (Gmail)** pattern **cannot gate
  this app** (no interactive Google SSO, no `CF-Access-Client-Id` service-token header).
- Putting it on a public hostname would leave a **shell server protected by one
  password on the internet** — rejected.

Therefore both paths make the endpoint **private and device-gated**, with the opencode
password as a second layer:

```
Phone app ──Basic auth──┐
                        ▼
   ┌────────────── device-gated private transport ──────────────┐
   │  Cloudflare: WARP (Gmail) → CF edge → cloudflared pod        │
   │  Tailscale:  tailnet (Google SSO) → tailscale proxy pod      │
   └──────────────────────────┬──────────────────────────────────┘
                              ▼
            Service default-wf2-mobile :4096  (ClusterIP)
                              ▼
              default-wf2 agent pod — opencode serve :4096
```

---

## 3. Plan (phases)

| Phase | Goal | Artifact |
|---|---|---|
| 0 | Cluster healthy on flannel, low load | (done) |
| 1 | Secure the agent with a password | `agent-default-wf2.yaml` + secret |
| 2 | Stable Service both paths target | `service-mobile.yaml` |
| 3 | LAN smoke test (prove the app ↔ agent chain) | app fields below |
| 4a | Cloudflare: cloudflared pod + WARP + private route + Gmail policy | `cloudflared-deployment.yaml` + dashboard |
| 4b | Tailscale: operator + exposed Service | `tailscale-operator` (helm) + annotations |
| 5 | Verify both remote paths, document rollback | this file |

Do **Phase 1 → 2 → 3 first** (shared). Then 4a and 4b are independent.

---

## Phase 1 — Secure the agent (shared, required)

```bash
# strong password in a secret
kubectl -n kubeopencode-system create secret generic opencode-server-auth \
  --from-literal=password="$(openssl rand -hex 20)"

# note it (you'll type it into the phone app):
kubectl -n kubeopencode-system get secret opencode-server-auth \
  -o jsonpath='{.data.password}' | base64 -d; echo
```

Add the `OPENCODE_SERVER_PASSWORD` credential to the agent (see
`agent-default-wf2.yaml`; reconcile with your live spec first):

```bash
kubectl -n kubeopencode-system get agent default-wf2 -o yaml   # compare
kubectl apply -f agent-default-wf2.yaml
kubectl -n kubeopencode-system rollout status deploy/default-wf2-server
# confirm the warning is gone:
kubectl -n kubeopencode-system logs deploy/default-wf2-server | grep -i password || echo "no 'unsecured' warning — good"
```

---

## Phase 2 — Stable Service (shared)

```bash
# read the selector kubeopencode uses, paste it into service-mobile.yaml
kubectl -n kubeopencode-system get svc default-wf2 -o jsonpath='{.spec.selector}'; echo

kubectl apply -f service-mobile.yaml
kubectl -n kubeopencode-system get svc default-wf2-mobile -o wide   # note CLUSTER-IP
```

Record the **ClusterIP** (e.g. `10.43.210.96`) — Cloudflare's private route targets it.
Pinning it (uncomment `clusterIP:` in the manifest) is recommended so the route never
drifts.

---

## Phase 3 — LAN smoke test (prove it works before remote)

Temporarily reach the Service from your laptop/phone on the LAN via a NodePort or
port-forward, and connect the app:

```bash
# quick temporary NodePort just for the test:
kubectl -n kubeopencode-system patch svc default-wf2-mobile \
  -p '{"spec":{"type":"NodePort","ports":[{"name":"http","port":4096,"targetPort":4096,"nodePort":30096}]}}'
```

App fields:

- **Server URL:** `http://192.168.178.200:30096`
- **Username:** *(blank — defaults to `opencode`)*
- **Password:** the value from Phase 1

Green `/global/health` = the app↔agent chain works. Then revert to ClusterIP:

```bash
kubectl -n kubeopencode-system patch svc default-wf2-mobile \
  -p '{"spec":{"type":"ClusterIP"}}'
```

---

## Phase 4a — Cloudflare: WARP + private route (in-cluster cloudflared)

You have a tunnel + public hostnames + Access already, but not WARP/private networking.
Here we add a private route and gate device enrollment by your Gmail.

### A. Dashboard — create the tunnel + token

1. Zero Trust → **Networks → Tunnels → Create a tunnel** (name `k3s-qnap`), type
   *Cloudflared*. Copy the **tunnel token**.

### B. Deploy the connector in-cluster

```bash
kubectl -n kubeopencode-system create secret generic cloudflared-token \
  --from-literal=token='<PASTE_TUNNEL_TOKEN>'
kubectl apply -f cloudflared-deployment.yaml
kubectl -n kubeopencode-system rollout status deploy/cloudflared
# the tunnel should show "HEALTHY" in the dashboard
```

**C. Dashboard — add the private network route**
2. Open the tunnel → **Private Network → Add a private network**:
   route = your Service's **ClusterIP as a /32** (e.g. `10.43.210.96/32`).
   (Or the whole Service CIDR `10.43.0.0/16` if you'd rather not pin.)

**D. Turn on WARP + gate by Gmail**
3. Zero Trust → **Settings → WARP Client**: ensure device enrollment is enabled and
   the enrollment policy **requires your Google/Gmail identity** (Login methods →
   Google; Device enrollment permissions → your email/group).
4. **Split Tunnels (Include mode)** or default: make sure the route CIDR above is
   sent through WARP.
5. *(Optional, stronger)* add a **Gateway network policy** or **Access for
   Infrastructure** target on that private IP:4096 scoped to your identity.

**E. Phone**
6. Install **Cloudflare One / WARP** app → sign in with your Gmail → connect.
7. In the opencode app:

- **Server URL:** `http://10.43.210.96:4096`  *(the Service ClusterIP)*
- **Username:** blank · **Password:** Phase‑1 password

*Gmail gates who can enroll a device into the tunnel; nothing is on a public hostname;
opencode password is the second layer.*

---

## Phase 4b — Tailscale: operator + exposed Service (in-cluster)

### A. Tailscale admin console

1. **Settings → OAuth clients → Generate** a client with tag `tag:k8s-operator`
   (create the tag under **Access controls** first if needed). Copy id + secret.

### B. Install the operator (Helm, in-cluster)

```bash
helm repo add tailscale https://pkgs.tailscale.com/helmcharts
helm repo update
helm upgrade --install tailscale-operator tailscale/tailscale-operator \
  --namespace tailscale --create-namespace \
  --set-string oauth.clientId="<OAUTH_ID>" \
  --set-string oauth.clientSecret="<OAUTH_SECRET>" \
  --set-string operatorConfig.hostname=k3s-qnap-operator
kubectl -n tailscale rollout status deploy/operator
```

**C. Expose the Service**
The `default-wf2-mobile` Service already carries the annotations
(`tailscale.com/expose: "true"`, `tailscale.com/hostname: opencode-mobile`).
The operator creates a proxy pod and a tailnet device:

```bash
kubectl -n kubeopencode-system get svc default-wf2-mobile -o yaml | grep -A3 annotations
# a device "opencode-mobile" should appear in your Tailscale admin console
```

**D. Phone**
2. Install **Tailscale** app → sign in **with your Google account** → connect.
3. In the opencode app:

- **Server URL:** `http://opencode-mobile:4096`  *(MagicDNS)* — or the device's
     `100.x.y.z` tailnet IP if MagicDNS isn't on
- **Username:** blank · **Password:** Phase‑1 password

*Only devices in your tailnet (enrolled via your Google identity) can reach it.*

---

## Phase 5 — Verify & rollback

### Verify both

```bash
kubectl -n kubeopencode-system get pods            # cloudflared + tailscale proxy Running
kubectl -n kubeopencode-system get agent default-wf2   # READY
```

From the phone on each transport, the app's `/global/health` should be green and a
session should start on `default-wf2`.

### Rollback (per path, non-destructive)

```bash
# Cloudflare off:
kubectl -n kubeopencode-system delete deploy cloudflared
#   + remove the private route in the dashboard
# Tailscale off:
kubectl -n kubeopencode-system annotate svc default-wf2-mobile tailscale.com/expose-
helm -n tailscale uninstall tailscale-operator
# Password stays; the agent remains secured either way.
```

---

## Security checklist (a shell server is behind this)

- [ ] `OPENCODE_SERVER_PASSWORD` set — server refuses to run unsecured (Phase 1).
- [ ] **No public hostname** points at 4096. Private route / tailnet only.
- [ ] Cloudflare device enrollment **requires your Gmail**; WARP split-tunnel includes the route.
- [ ] Tailnet ACLs restrict the device to you.
- [ ] `default-wf2-mobile` is owned by you (operator won't revert it).
- [ ] One agent exposed, not several (keeps the VM light; smaller blast radius).
- [ ] (Optional) NetworkPolicy so only the connector pods can reach the agent pod.

## Resource note (in-cluster choice)

You chose in-cluster connectors. Post-Cilium the VM has headroom, and limits are set
(`cloudflared` ~25–150m CPU / 48–128Mi; the Tailscale proxy is similarly small). If load
climbs again, moving these two to host-level systemd services is the fallback — same
config, less per-pod overhead.

---

## Files in this folder

| File | Purpose |
|---|---|
| `agent-default-wf2.yaml` | Agent with `OPENCODE_SERVER_PASSWORD` added |
| `service-mobile.yaml` | Stable Service both paths target (+ Tailscale annotations) |
| `cloudflared-deployment.yaml` | In-cluster cloudflared connector (token mode) |
| `README.md` | This plan / story / runbook |
