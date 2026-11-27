#!/bin/bash
# Live verification of the KubeOpenCode strict-tier NetworkPolicies (BITB-152).
#
# Usage (normally via the Makefile):
#   make verify-kubeopencode-netpol        # the full strict-tier suite
#   make verify-llama-egress              # focused llama allow only (BITB-362)
# or directly:
#   bash scripts/verify-kubeopencode-netpol.sh
#   bash scripts/verify-kubeopencode-netpol.sh --llama-only
#   bash scripts/verify-kubeopencode-netpol.sh --print-llama-target
#     # no cluster: prints the focused check's default target (host:port) and
#     # exits -- lets the static suite pin the manifest extraction below.
#
# Exits 0 only if every guarantee holds. Safe to run on demand or in a pipeline
# stage that has a kubeconfig; it is read-only apart from three probe pods and
# one Service, all of which it deletes on exit.
#
# Why probe pods instead of exec-ing into real agents: agents scale to zero on
# `standby.idleTimeout`, so a suite pinned to a live agent fails with
# "timed out waiting for the condition" depending on who used the cluster last.
# The probes also carry the two label sets deliberately, which is what the
# policies actually select on:
#
#   platform:  no app.kubernetes.io/managed-by   -> server-egress-strict
#   workspace: app.kubernetes.io/managed-by=...  -> agent-egress-strict
#
# Env overrides:
#   NAMESPACE       namespace under test            (default kubeopencode-system)
#   LAN_TARGET      LAN host:port that must be denied (default [IP_ADDRESS]:6443)
#   PUBLIC_URL      public HTTPS URL that must work (default openrouter models API)
#   LLAMA_TARGET    llama host:port that must be ALLOWED for agent pods
#                   (default: EXTRACTED at runtime from the committed
#                   k8s/kubeopencode/networkpolicy-allow-llama-egress.yaml --
#                   the address is deliberately never hardcoded here)
#   CURL_IMAGE      image for the probe pods
#   LISTENER_IMAGE  image for the fake workspace listener
#   TIMEOUT         per-request timeout, seconds    (default 5)
#   KEEP_PROBES     set to 1 to skip cleanup (debugging)

set -euo pipefail

NAMESPACE="${NAMESPACE:-kubeopencode-system}"
LAN_TARGET="${LAN_TARGET:-[IP_ADDRESS]:6443}"
PUBLIC_URL="${PUBLIC_URL:-https://openrouter.ai/api/v1/models}"
# Empty default: the focused --llama-only mode resolves it from the committed
# manifest at runtime (see llama_default_target) -- never hardcoded here.
LLAMA_TARGET="${LLAMA_TARGET:-}"
CURL_IMAGE="${CURL_IMAGE:-curlimages/curl:8.5.0}"
LISTENER_IMAGE="${LISTENER_IMAGE:-busybox:1.36}"
TIMEOUT="${TIMEOUT:-5}"
KEEP_PROBES="${KEEP_PROBES:-0}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LLAMA_MANIFEST="${REPO_ROOT}/k8s/kubeopencode/networkpolicy-allow-llama-egress.yaml"

AGENT_SA="system:serviceaccount:${NAMESPACE}:kubeopencode-agent"
PROBE_LABEL="kubeopencode.io/netpol-probe=true"
AGENT_POD="netpol-probe-agent"
PLATFORM_POD="netpol-probe-platform"
TARGET_POD="netpol-probe-target"
TARGET_URL="http://${TARGET_POD}.${NAMESPACE}.svc.cluster.local:4096/"
API_URL="https://kubernetes.default.svc.cluster.local/version"

PASSED=0
FAILED=0
RESULTS=()

# No escape codes when stdout is not a terminal: pipeline logs should stay
# greppable rather than filling up with \033[32m.
if [ -t 1 ]; then
  red()   { printf '\033[31m%s\033[0m' "$1"; }
  green() { printf '\033[32m%s\033[0m' "$1"; }
else
  red()   { printf '%s' "$1"; }
  green() { printf '%s' "$1"; }
fi

# The focused llama check's default probe target (BITB-362): extracted from the
# committed manifest at runtime so the address lives in exactly one place. A
# broken extraction fails loudly here instead of probing a stale address.
llama_default_target() { # prints host:port
  local cidr port
  cidr="$(sed -n 's/^[[:space:]]*cidr:[[:space:]]*\([^[:space:]#]*\).*/\1/p' "$LLAMA_MANIFEST" | head -n1)"
  port="$(sed -n 's/^[[:space:]]*-[[:space:]]*port:[[:space:]]*\([0-9][0-9]*\).*/\1/p' "$LLAMA_MANIFEST" | head -n1)"
  if [ -z "$cidr" ] || [ -z "$port" ]; then
    echo "cannot extract the llama target from ${LLAMA_MANIFEST} (cidr=${cidr:-none} port=${port:-none})" >&2
    return 1
  fi
  echo "${cidr%/*}:${port}"   # strip the /32 -> bare host
}

cleanup() {
  if [ "$KEEP_PROBES" = "1" ]; then
    echo "KEEP_PROBES=1, leaving probes in $NAMESPACE" >&2
    return
  fi
  kubectl -n "$NAMESPACE" delete pod,svc -l "$PROBE_LABEL" \
    --ignore-not-found --wait=false >/dev/null 2>&1 || true
}
trap cleanup EXIT

record() { # name expectation outcome detail
  local name="$1" expectation="$2" outcome="$3" detail="$4"
  if [ "$expectation" = "$outcome" ]; then
    PASSED=$((PASSED + 1))
    RESULTS+=("$(green PASS)|${name}|${outcome}|${detail}")
  else
    FAILED=$((FAILED + 1))
    RESULTS+=("$(red FAIL)|${name}|want ${expectation}, got ${outcome}|${detail}")
  fi
}

# Maps a curl exit status onto what it says about the network path. The
# distinction that matters: a name that does not resolve (6) is NOT the same as
# a connection the policy dropped (7/28), so a broken-DNS regression can never
# masquerade as a passing "blocked" assertion. A TLS-level error means the TCP
# handshake completed, so it counts as reachable.
classify() {
  case "$1" in
    0)             echo reachable ;;
    6)             echo dns-failure ;;
    7 | 28)        echo blocked ;;
    35 | 56 | 60)  echo reachable ;;
    *)             echo "curl-exit-$1" ;;
  esac
}

probe() { # pod url [curl-flags...]
  local pod="$1" url="$2"
  shift 2
  local out status
  out="$(kubectl -n "$NAMESPACE" exec "$pod" -- \
    sh -c "curl -s -o /dev/null -m ${TIMEOUT} $* -w '%{http_code}' '${url}'; echo \" \$?\"" \
    2>/dev/null)" || true
  # Trailing "<http_code> <curl_exit>"; empty if the exec itself failed.
  if [ -z "$out" ]; then
    echo "exec-failed 0"
    return
  fi
  status="$(echo "$out" | tail -n1)"
  echo "$status"
}

check() { # name pod url expectation [curl-flags...]
  local name="$1" pod="$2" url="$3" expectation="$4"
  shift 4
  local result http_code curl_exit outcome
  result="$(probe "$pod" "$url" "$@")"
  http_code="$(echo "$result" | awk '{print $1}')"
  curl_exit="$(echo "$result" | awk '{print $2}')"
  if [ "$http_code" = "exec-failed" ]; then
    outcome="exec-failed"
  else
    outcome="$(classify "$curl_exit")"
  fi
  record "$name" "$expectation" "$outcome" "http=${http_code} curl_exit=${curl_exit}"
}

# The focused llama check (BITB-362) pins the HTTP status, not just reachability:
# the provider's OpenAI-compatible /v1/models must answer 200. Anything else --
# a 404 from a wrong port mapping, a timeout from a missing policy, a TLS error
# from an https-only listener -- fails the check instead of squeaking by as
# "reachable".
check_llama() { # name pod url
  local name="$1" pod="$2" url="$3" result http_code curl_exit outcome
  result="$(probe "$pod" "$url")"
  http_code="$(echo "$result" | awk '{print $1}')"
  curl_exit="$(echo "$result" | awk '{print $2}')"
  if [ "$http_code" = "exec-failed" ]; then
    outcome="exec-failed"
  elif [ "$curl_exit" = "0" ] && [ "$http_code" = "200" ]; then
    outcome="http-200"
  else
    outcome="$(classify "$curl_exit") http=${http_code}"
  fi
  record "$name" "http-200" "$outcome" "http=${http_code} curl_exit=${curl_exit}"
}

check_rbac() { # name verb resource expectation
  local name="$1" verb="$2" resource="$3" expectation="$4" outcome
  if kubectl auth can-i "$verb" "$resource" \
       -n "$NAMESPACE" --as="$AGENT_SA" >/dev/null 2>&1; then
    outcome=yes
  else
    outcome=no
  fi
  record "$name" "$expectation" "$outcome" "as=${AGENT_SA}"
}

require_policies() {
  local missing=0 np
  for np in default-deny-all agent-egress-strict server-egress-strict allow-server-ingress; do
    if ! kubectl -n "$NAMESPACE" get networkpolicy "$np" >/dev/null 2>&1; then
      echo "missing NetworkPolicy: $np" >&2
      missing=1
    fi
  done
  if [ "$missing" = "1" ]; then
    echo "Apply the manifests in k8s/kubeopencode/ first (see its README)." >&2
    exit 2
  fi
}

# The focused llama check (BITB-362) needs default-deny-all in force -- without
# it "allowed" proves nothing, since an unselected pod egresses freely -- and
# the policy under test applied.
require_llama_policy() {
  local missing=0 np
  for np in default-deny-all agent-egress-llama; do
    if ! kubectl -n "$NAMESPACE" get networkpolicy "$np" >/dev/null 2>&1; then
      echo "missing NetworkPolicy: $np" >&2
      missing=1
    fi
  done
  if [ "$missing" = "1" ]; then
    echo "default-deny-all must be in force and agent-egress-llama applied -- see k8s/kubeopencode/README.md (apply order + pre-merge runbook)." >&2
    exit 2
  fi
}

wait_ready() { # pod
  if ! kubectl -n "$NAMESPACE" wait --for=condition=Ready "pod/$1" --timeout=120s >/dev/null; then
    echo "probe pod $1 never became ready" >&2
    kubectl -n "$NAMESPACE" describe "pod/$1" >&2 || true
    exit 2
  fi
}

start_probes() {
  cleanup
  # A stand-in workspace: carries the workspace label set, so agent-egress-strict
  # governs its egress and allow-server-ingress governs who may reach :4096.
  kubectl -n "$NAMESPACE" run "$TARGET_POD" --image="$LISTENER_IMAGE" \
    --labels="${PROBE_LABEL},app.kubernetes.io/managed-by=kubeopencode,app.kubernetes.io/name=kubeopencode-server" \
    --port=4096 --restart=Never \
    --command -- sh -c 'mkdir -p /w && echo ok > /w/index.html && httpd -f -p 4096 -h /w' >/dev/null
  kubectl -n "$NAMESPACE" expose pod "$TARGET_POD" --port=4096 --target-port=4096 \
    --labels="$PROBE_LABEL" >/dev/null
  kubectl -n "$NAMESPACE" run "$AGENT_POD" --image="$CURL_IMAGE" \
    --labels="${PROBE_LABEL},app.kubernetes.io/managed-by=kubeopencode" \
    --restart=Never --command -- sleep 600 >/dev/null
  # No managed-by: this is what server-egress-strict selects.
  kubectl -n "$NAMESPACE" run "$PLATFORM_POD" --image="$CURL_IMAGE" \
    --labels="${PROBE_LABEL},app.kubernetes.io/name=kubeopencode" \
    --restart=Never --command -- sleep 600 >/dev/null

  local pod
  for pod in "$TARGET_POD" "$AGENT_POD" "$PLATFORM_POD"; do
    wait_ready "$pod"
  done
}

# The focused llama check (BITB-362) needs only the agent-labeled probe: the
# platform/target probes exist for the full suite's cross-tier assertions.
start_agent_probe() {
  cleanup
  kubectl -n "$NAMESPACE" run "$AGENT_POD" --image="$CURL_IMAGE" \
    --labels="${PROBE_LABEL},app.kubernetes.io/managed-by=kubeopencode" \
    --restart=Never --command -- sleep 600 >/dev/null
  wait_ready "$AGENT_POD"
}

summary() {
  echo
  # `column` is util-linux and is missing from some minimal CI images; the
  # summary is the script's whole output, so it must not be what kills the run.
  if command -v column >/dev/null 2>&1; then
    printf '%s\n' "${RESULTS[@]}" | column -t -s '|'
  else
    printf '%s\n' "${RESULTS[@]}" | tr '|' '\t'
  fi
  echo
  echo "passed: ${PASSED}  failed: ${FAILED}"
  [ "$FAILED" -eq 0 ]
}

main() {
  echo "Verifying KubeOpenCode strict tier in namespace '$NAMESPACE'"
  require_policies
  start_probes

  # Platform tier: the gateway must resolve and reach workspaces. This pair is
  # the BITB-152 regression -- the reported failure was the gateway losing DNS
  # and timing out on the workspace lookup.
  check "platform -> workspace :4096"   "$PLATFORM_POD" "$TARGET_URL"  reachable
  check "platform -> kubernetes API"    "$PLATFORM_POD" "$API_URL"     reachable -k

  # Agent tier: works for what agents need.
  check "agent -> kubernetes API"       "$AGENT_POD"    "$API_URL"     reachable -k
  check "agent -> public HTTPS"         "$AGENT_POD"    "$PUBLIC_URL"  reachable

  # Agent tier: denied for everything else.
  check "agent -> LAN ${LAN_TARGET}"    "$AGENT_POD"    "https://${LAN_TARGET}/version" blocked -k
  check "agent -> cloud metadata"       "$AGENT_POD"    "http://169.254.169.254/"       blocked
  check "agent -> other agent :4096"    "$AGENT_POD"    "$TARGET_URL"                   blocked

  # RBAC: network reachability to the API is allowed by design, so the
  # allow-lan trust boundary rests entirely on these.
  check_rbac "agent SA: list pods"           list   pods            yes
  check_rbac "agent SA: patch pods"          patch  pods            no
  check_rbac "agent SA: create networkpolicies" create networkpolicies no
  check_rbac "agent SA: patch agents"        patch  agents.kubeopencode.io no
  check_rbac "agent SA: read secrets"        get    secrets         no

  summary
}

# The focused pre-merge check for the supplemental llama allow (BITB-362):
# ONE agent-labeled probe must get HTTP 200 from the provider's OpenAI-compatible
# /v1/models. Invoked by `make verify-llama-egress`; the full suite above is
# unchanged -- it is also a regression suite, and making it require llama
# reachability would break it for runners without LAN access.
main_llama() {
  if [ -z "$LLAMA_TARGET" ]; then
    LLAMA_TARGET="$(llama_default_target)"
  fi
  echo "Verifying llama.cpp egress allow (agent tier) in namespace '$NAMESPACE' -> ${LLAMA_TARGET}"
  require_llama_policy
  start_agent_probe
  check_llama "agent -> llama ${LLAMA_TARGET}" "$AGENT_POD" "http://${LLAMA_TARGET}/v1/models"
  summary
}

case "${1:-}" in
  --llama-only)        main_llama ;;
  --print-llama-target) llama_default_target ;;
  *)                   main "$@" ;;
esac
