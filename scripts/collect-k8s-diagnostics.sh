#!/bin/bash
# One-pass cluster state collector for incident triage (BITB-156).
#
# Usage (normally via the Makefile — `make collect-k8s-diagnostics`):
#   bash scripts/collect-k8s-diagnostics.sh [--namespace NS] [--pod-ip IP] [--out FILE]
#
# Writes one annotated text file. Read it with docs/RUNBOOK-CLUSTER-TRIAGE.md
# open alongside — the section names match the rungs of that ladder.
#
# Why this exists: the 2026-09-19 outage took most of a day, and every wrong
# turn came from reasoning about what the manifests *should* do. Every real
# answer came from runtime state — which pod owned an IP, what the error body
# actually said, what iptables was enforcing as opposed to what was declared.
# Collecting all of it up front costs 30 seconds and removes the temptation.
#
# Secrets: this never dumps Secret contents. Secrets are listed by name only.
# Everything else is your cluster's config, so skim before sharing it.

set -uo pipefail

NAMESPACE=""
POD_IP=""
OUT="/tmp/k8s-diagnostics-$(date +%Y%m%d-%H%M%S).txt"

while [ $# -gt 0 ]; do
  case "$1" in
    --namespace) NAMESPACE="$2"; shift 2 ;;
    --pod-ip)    POD_IP="$2";    shift 2 ;;
    --out)       OUT="$2";       shift 2 ;;
    -h|--help)   sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

: > "$OUT"

section() { printf '\n\n########## %s ##########\n' "$*" >> "$OUT"; }

# Never aborts the run: a missing binary or an RBAC denial on one command must
# not cost you the other forty.
run() { section "$*"; eval "$*" >> "$OUT" 2>&1 || echo "[command failed, continuing]" >> "$OUT"; }

# --- rung 1: who is the actor -------------------------------------------
# Resolving the IP in an error message to a pod is the cheapest step there is,
# and the one skipped most often.
run "kubectl get pods -A -o wide"
if [ -n "$POD_IP" ]; then
  section "OWNER OF $POD_IP"
  kubectl get pods -A -o wide 2>/dev/null | awk -v ip="$POD_IP" 'NR==1 || $7==ip' >> "$OUT"
fi

# --- cluster and node ----------------------------------------------------
run "kubectl version"
run "kubectl get nodes -o wide"
run "kubectl get events -A --sort-by=.lastTimestamp | tail -60"
run "cat /etc/rancher/k3s/config.yaml"
run "timedatectl"
run "df -h /"
run "free -h"

# --- rung 3: blast radius ------------------------------------------------
# Namespace-by-namespace workload health: if the symptom appears outside the
# namespace you changed, your config is not the cause.
run "kubectl get pods -A --field-selector=status.phase!=Running"
if [ -n "$NAMESPACE" ]; then
  run "kubectl -n $NAMESPACE get pods -o wide --show-labels"
  run "kubectl -n $NAMESPACE get svc,endpoints"
  run "kubectl -n $NAMESPACE get netpol -o yaml"
  run "kubectl -n $NAMESPACE get rolebinding,role,serviceaccount -o name"
  # Names only. Never -o yaml on a Secret.
  run "kubectl -n $NAMESPACE get secrets -o name"
fi

# --- rung 7: declared state vs enforced state ----------------------------
# kubectl tells you what was asked for. iptables and ipset tell you what is
# actually being enforced. When those disagree, that gap is the bug.
run "kubectl get netpol -A"
run "kubectl get ns --show-labels"
run "sudo iptables-save"
run "sudo ipset list -t"
run "sudo iptables -t nat -S KUBE-SERVICES"
run "ip route"
run "ip -br addr"
run "sudo sysctl net.ipv4.ip_forward net.ipv4.conf.all.rp_filter net.bridge.bridge-nf-call-iptables net.netfilter.nf_conntrack_max"
run "cat /proc/net/stat/nf_conntrack"

# --- DNS -----------------------------------------------------------------
run "cat /etc/resolv.conf"
run "kubectl -n kube-system get cm coredns -o yaml"
run "kubectl -n kube-system get cm coredns-custom -o yaml"
run "kubectl -n kube-system get pods -l k8s-app=kube-dns -o wide --show-labels"
run "kubectl -n kube-system logs -l k8s-app=kube-dns --tail=120"
run "kubectl get endpoints kubernetes"

printf '\nwrote %s (%s lines, %s)\n' \
  "$OUT" "$(wc -l < "$OUT")" "$(du -h "$OUT" | cut -f1)"
