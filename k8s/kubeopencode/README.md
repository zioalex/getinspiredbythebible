DNS Setup
------------

Point `chat.home.local` to your k3s ingress IP (192.168.178.200 by default):

- Add `192.168.178.200 chat.home.local` to your /etc/hosts
  or configure in your FritzBox / Pi-hole DHCP static lease.

Use
-----

Apply in order (strict tier, zero-downtime — see `docs/SECURITY-KUBEOPENCODE.md`):

```bash
kubectl apply -f secret-opencode-api-key.yaml
kubectl apply -f networkpolicy-egress-strict.yaml -f networkpolicy-allow-server-ingress.yaml
# verify new agent works, then:
kubectl apply -f networkpolicy-default-deny.yaml
kubectl apply -f agent-desktop.yaml -f ingress-server.yaml
```

Then open http://chat.home.local in a browser. You will see:

- Agent Browser
- Your `desktop` agent
- Click `desktop` → Web Terminal / Task Create

This behaves like a minimal Claude Desktop: type prompts, watch logs live, sessions persist across restarts (2Gi storage, 30m standby idle timeout).

No API key needed — uses the free opencode/big-pickle model.

Hostname
--------

For production, set your own domain / Ingress TLS and update `ingress-server.yaml` accordingly.