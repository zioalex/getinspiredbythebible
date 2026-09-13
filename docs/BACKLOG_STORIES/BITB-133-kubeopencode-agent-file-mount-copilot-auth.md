# BITB-133: KubeOpenCode Agent File-Mount Support for Copilot Auth

**Priority:** P2 (Medium)
**Status:** 🎯 Todo
**Size:** S (docs + upstream request; implementation size unknown — may be upstream)
**Created:** 2026-09-13
**Affects:** `deployment/kubeopencode/` only — no application code

---

## Background

PR #1066 (merged as `b73c558`, superseding #1043) corrected the "Persist GitHub
Copilot access" recipe in `deployment/kubeopencode/README.md`. The section now
documents two options:

- **Option A (preferred):** mount `auth.json` from `opencode auth login`. It
  holds a long-lived *refresh* token from which OpenCode re-mints the
  short-lived Copilot bearer indefinitely — nothing expires on a rotation
  schedule.
- **Option B (works today):** reuse a `gho_…` OAuth user token from
  `gh auth token` via the existing `GITHUB_TOKEN` credentials wiring.

Option A is documented as *preferred-pending-CRD-support* because the
`kubeopencode.io/v1alpha1` `Agent` CRD — as far as the repo's manifests show —
exposes only `credentials[].secretRef` → `env`. It has no `volumes` /
`volumeMounts`, and `spec.persistence` covers `workspaceDir` and `sessions`,
not the OpenCode data dir (`~/.local/share/opencode/auth.json`). `agent.yaml`
carries a comment saying exactly this, and deliberately invents no CRD fields.

Unlike BITB-128's gate, which resolved the equivalent question by querying the
live CRD (`kubectl explain agent.spec.persistence --recursive`), this
limitation was established by reading manifests only. It has **not** been
verified against the live CRD — and the CRD may already persist enough of the
data dir via `sessions` to make Option A work without any CRD change.

**Cost of the status quo (Option B only):** the `gho_…` token is tied to the
user's `gh` CLI session — revoked by `gh auth logout` or token rotation — and
the CLI credentials themselves live in ephemeral pod storage. Every revocation
or restart that loses them breaks the `github-copilot` provider for the whole
agent graph until someone re-runs the device flow and rotates the
`github-copilot-auth` secret. Recurring toil with a silent outage mode.

---

## User Story

**As a** developer running the agent graph on KubeOpenCode,
**I want** the Copilot credential mounted or persisted declaratively,
**so that** a pod restart or token rotation does not break the
`github-copilot` provider or require an interactive re-login.

---

## Gate: live-CRD check (do this first)

Run against the cluster (read-only; the agent ServiceAccount is restricted to
schema reads, which is sufficient here):

```console
$ kubectl explain agent.spec --recursive | grep -i -A5 "volume\|mount\|file\|auth"
$ kubectl -n kubeopencode-system exec <agent-pod> -- \
    sh -c 'mount | grep -E "workspace|session|opencode"; echo "HOME=$HOME"; ls -la ~/.local/share/opencode/ 2>/dev/null'
```

**Outcome (a): the data dir is already on a persisted volume** (e.g.
`sessions` persistence covers `$HOME/.local/share/opencode`). Then no CRD
change is needed: store `auth.json` as a secret, document its placement, mark
Option A working in the README, and update `agent.yaml` using only supported
fields.

**Outcome (b): it is not covered and the CRD has no file-mount field.** Then
file an upstream feature request (`volumes`/`volumeMounts`, or extending
`persistence` to the OpenCode data dir), link it from this story, keep
Option B as the supported mechanism, and document the rotation runbook below.

Paste the `kubectl explain` output into this story when recording the outcome,
as BITB-128 did.

---

## Design (outcome (b) / interim)

1. **Do not invent CRD fields in `agent.yaml`.** The #1043 review caught a
   duplicate `github-copilot` credentials entry and a broken shell
   continuation; unverifiable fields would fail the same way at apply time.
2. **Rotation runbook for Option B** (document in README): detect (`401` from
   Copilot models), re-mint (`gh auth token`), re-apply the secret, delete the
   agent pod so it picks up the new value.
3. If upstream accepts the request, wire the mount and promote Option A to the
   working mechanism in a follow-up change.

---

## Functional Requirements

- [ ] Live-CRD gate recorded: `explain` output pasted here; sessions-volume
      coverage of the OpenCode data dir checked on-cluster and recorded
- [ ] Outcome (a): `auth.json` secret + placement documented, Option A marked
      working, `agent.yaml` updated with supported fields only
- [ ] Outcome (b): upstream issue filed and linked; README marks Option A
      pending; Option B remains supported with a rotation runbook
- [ ] No secret material committed to git; `detect-secrets` green

## Non-Functional Requirements

- [ ] `make pre-commit` passes (markdownlint, yamllint, prettier)
- [ ] If `agent.yaml` changes: `kubectl apply --dry-run=server -f` validates

---

## Verification

Requires cluster access (the in-cluster agent ServiceAccount cannot apply):

1. `kubectl apply -f deployment/kubeopencode/agent.yaml` → agent reaches ready.
2. **Survival proof:** place `auth.json`, delete the agent pod, confirm the
   replacement pod still has working Copilot auth with **no** `GITHUB_TOKEN`
   env set (`printenv GITHUB_TOKEN` empty, Copilot model call succeeds).
3. **Reset proof:** the documented procedure restores a clean state.

---

## Out of Scope

- Multi-replica / access-mode changes (operator-owned, as in BITB-128)
- Backup or snapshot policy for any new volume
- Any change to application runtime storage (Azure Container Apps, PostgreSQL)
- Revoking the PAT exposed during the #1043 debugging session (handled
  separately, immediately — not tracked here)

---

## Related

- PR #1066 (`b73c558`) — corrected Copilot auth docs; superseded #1043
- PR #1043 (closed, superseded) — targeted a dead branch; see #1066 for why
- `deployment/kubeopencode/agent.yaml` — `github-copilot` credentials comment
- `deployment/kubeopencode/README.md` — "Persist GitHub Copilot access"
- BITB-123 — created `deployment/kubeopencode/`
- BITB-128 — `spec.persistence` (workspace + sessions); gate pattern to follow
- BITB-129 — CI coverage for these manifests
