# BITB-182: KubeOpenCode controller RBAC missing — agents not starting

## Summary

The KubeOpenCode controller (`kubeopencode-controller`) lacked RBAC permissions for leader election leases and its CRDs, preventing Agent reconciliation. Both `default-wf2` and `default-wf3` agents failed to start.

## Root Cause

The controller ServiceAccount (`kubeopencode-controller` in `kubeopencode-system`) had no `Role`/`RoleBinding` for:

- `coordination.k8s.io/leases` (get, create, update, patch) — required for leader election
- `kubeopencode.io` CRDs (agents, agenttemplates, tasks, crontasks, registries + status subresources) — required for reconciliation

Without leader election, the controller never became leader and skipped all reconciliation loops.

## Symptoms

- Controller logs: `Error retrieving lease lock err="Unauthorized" lock="kubeopencode-system/kubeopencode.io"` (repeated every ~2s)
- `default-wf2`: No pods created (Agent existed but no Deployment)
- `default-wf3`: Deployment existed but `replicas: 0` (stuck at 0)
- `kubectl get agent` showed `ServerReady: False`, `ServerHealthy: False`

## Fix Applied

Created two manifests in `k8s/kubeopencode/`:

1. `role-controller.yaml` — Role with lease + CRD permissions
2. `rolebinding-controller.yaml` — Binds to `kubeopencode-controller` SA

Applied via:

```bash
kubectl apply -f k8s/kubeopencode/role-controller.yaml -f k8s/kubeopencode/rolebinding-controller.yaml
kubectl rollout restart deployment/kubeopencode-controller -n kubeopencode-system
```

## Verification

- Controller acquired lease: `Successfully acquired lease lock="kubeopencode-system/kubeopencode.io"`
- Agents reconciled: Deployments created/scaled, pods Running and Ready
- `kubeoc agent attach default-wf2 -n kubeopencode-system` works

## Related Issues

- **BITB-172**: Controller also needs `events.k8s.io/events` create/patch for event recording (added in follow-up commit)
- **mobile-access.md Phase 1**: `OPENCODE_SERVER_PASSWORD` breaks gateway/readiness — do NOT add unless mobile app access is needed

## Prevention

- These RBAC manifests are now in Git (k8s/kubeopencode/) and should be applied via GitOps (ArgoCD/Flux) so they persist across Helm chart upgrades
- Controller Helm chart does NOT create these RBAC resources — repo owns them

## Follow-up

- [ ] Verify GitOps sync includes `role-controller.yaml` + `rolebinding-controller.yaml`
- [ ] Document in `k8s/kubeopencode/README.md` that controller RBAC is repo-managed
