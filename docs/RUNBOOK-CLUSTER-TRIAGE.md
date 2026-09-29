# Cluster triage runbook

Ordered ladder for debugging a misbehaving cluster. Written after the
2026-09-19 outage, which took most of a day and produced five wrong diagnoses
before the right one.

## The rule

**When a hypothesis and a cheap binary test both exist, run the test.**

Every wrong turn that day came from reasoning about what the manifests *should*
do. Every real answer came from runtime state: which pod owned an IP, what the
error body actually said, what iptables was enforcing rather than what was
declared. The discriminating test was available nearly every time and cost one
command.

Start here:

```bash
make collect-k8s-diagnostics NAMESPACE=kubeopencode-system
```

Its section names match the rungs below.

## The ladder

Cheapest and most decisive first. Stop as soon as a rung names the layer.

### 1. Who is the actor?

Errors carry an IP or a pod name. Resolve it before theorising about it.

```bash
kubectl get pods -A -o wide | grep 10.42.0.9
bash scripts/collect-k8s-diagnostics.sh --pod-ip 10.42.0.9
```

`dial tcp ... 10.42.0.9->10.43.0.10:53` means *some specific pod* cannot reach
cluster DNS. Which pod decides whether you are looking at a policy, an
application, or the resolver.

### 2. Read the body, not the status code

A `503` or `500` tells you nothing. The response body usually names the exact
failing call and address.

```bash
kubectl -n NS port-forward pod/POD 2746:2746 >/dev/null 2>&1 &
sleep 3; curl -s localhost:2746/ready; echo; curl -s localhost:2746/api/v1/tasks
```

On 2026-09-19 the body read
`Get "https://10.43.0.1:443/api": dial tcp: connect: connection refused` —
which named the culprit outright after hours of inferring from `503`s.

### 3. Bisect by blast radius

Before anything else, find out whether the fault is *yours* or the *cluster's*.
Run the same probe from a pod that none of your config touches.

```bash
kubectl -n kube-system run probe --rm -i --restart=Never --image=busybox:1.36 -- \
  sh -c 'nslookup example.com 8.8.8.8; nc -w3 1.1.1.1 443 </dev/null && echo tcp-ok'
```

Fails there too → not your NetworkPolicies, not your namespace. This single
test exonerates or implicates your changes in seconds.

### 4. Let the failure shape pick the layer

| symptom | means | look at |
| --- | --- | --- |
| timeout / `i/o timeout` | packet dropped | NetworkPolicy, routing, blackhole |
| `connection refused` | RST returned | nothing listening, or an explicit REJECT rule |
| `curl` exit 6, `could not resolve` | DNS only | resolver, not connectivity |
| `NXDOMAIN` | resolver answered | the name is wrong, the path is fine |
| `curl` exit 7 vs 28 | refused vs dropped | same split as rows 1–2 |

kube-router REJECTs rather than drops, so `connection refused` **can** be a
NetworkPolicy. Do not use it to rule policy out.

### 5. Intermittent means measure a rate

One success proves nothing against an intermittent fault.

```bash
for i in $(seq 1 30); do
  dig +short +time=2 +tries=1 @192.168.178.1 example.com >/dev/null 2>&1 && printf . || printf X
done; echo
```

A single `dig` "proved" the node was healthy on 2026-09-19. It was not.

### 6. Capture on both sides of the suspect hop

Definitive, and it ends argument.

```bash
sudo timeout 35 tcpdump -ni cni0   'udp port 53' > /tmp/pod-side.txt 2>&1 &
sudo timeout 35 tcpdump -ni enp1s0 'udp port 53' > /tmp/wan-side.txt 2>&1 &
# ...trigger the failing operation...
```

| pod side | wan side | meaning |
| --- | --- | --- |
| query | nothing | dropped inside the node |
| query | query, no reply | left correctly; upstream is not answering |
| query | query + reply | reply lost on the return path (NAT, pod firewall) |

### 7. Declared state is not enforced state

`kubectl get` shows what you asked for. `iptables` and `ipset` show what is
enforced. The gap between them is where the bugs live.

```bash
kubectl get netpol -A
GWIP=$(kubectl -n NS get pod POD -o jsonpath='{.status.podIP}')
CHAIN=$(sudo iptables -S | grep -m1 "$GWIP" | grep -oE 'KUBE-POD-FW-[A-Z0-9]+')
sudo iptables -S "$CHAIN"
sudo ipset list KUBE-DST-XXXX
```

A pod chain naming a policy is the ground truth for what governs that pod.

## Discipline that cost the most when skipped

* **Re-read cluster state before every instruction that changes it.** Reapplying
  `default-deny-all` while `server-egress-strict` was deleted recreated the
  original outage and cost hours. One `kubectl get netpol` first would have
  caught it.
* **Change one thing at a time**, and confirm enforcement changed before the
  next change — not just that the object exists.
* **Know the settle time.** kube-router reconciles asynchronously; a test on a
  10-second window measures the previous state. `sudo systemctl restart k3s`
  forces a rebuild when you suspect drift.
* **Derived state is not editable.** Hand-deleting a `KUBE-POD-FW-*` chain is
  undone at the next sync. Change the API objects.

## Kubernetes-specific traps this cluster has already hit

* **ClusterIP rules and DNAT.** kube-proxy rewrites a Service ClusterIP to its
  endpoint in `nat PREROUTING`, *before* NetworkPolicy is evaluated. An
  `ipBlock` naming the ClusterIP can never match. Cluster DNS survives this only
  because its rule also carries a podSelector matching CoreDNS's pod IP — the
  post-DNAT destination. The API server is a host process, so it needs an
  explicit allow for its real endpoint (`kubectl get endpoints kubernetes`).
* **`namespaceSelector` needs `kubernetes.io/metadata.name`.** A bare `name`
  label is not set on namespaces by default and silently matches nothing.
* **Probes that do not probe.** CoreDNS's `/health` and `/ready` check the
  process and its plugins, never that forwarding resolves anything.
* **`forward . /etc/resolv.conf` with several upstreams** uses `policy random`.
  One dead upstream becomes an intermittent ~50% failure, not an outage.
* **A Service with no endpoints** gets an explicit REJECT from kube-proxy, which
  surfaces as `connection refused` rather than a timeout.
