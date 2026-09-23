#!/usr/bin/env python3
"""Tests for the cluster triage tooling (BITB-160).

The 2026-09-19 outage took most of a day and produced five wrong diagnoses
before the right one. The collector and runbook exist so the next incident
starts from runtime state instead of a conversation. These tests protect the
properties that make them worth reaching for:

- T1: the collector must never dump Secret *contents*. It is run during an
  incident and its output gets pasted into chats and issues. Listing names is
  fine; `-o yaml` on a Secret is a credential leak.
- T2: one failing command must not cost you the other forty. During an
  incident half these commands fail by design (missing binary, RBAC denial,
  a node you are not on), and an abort at command three is useless.
- T3: the collector has to cover the rungs the runbook sends you to, or the
  runbook sends you somewhere the output does not go.
- T4: the traps recorded here were each paid for in hours. A runbook that
  loses them is just a list of kubectl commands.
- T5: the `connection refused` caveat specifically. Believing that a refusal
  could not come from a NetworkPolicy is what ruled out the real culprit for
  several rounds -- kube-router REJECTs rather than drops.
"""

import pathlib
import re

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
COLLECTOR = REPO_ROOT / "scripts" / "collect-k8s-diagnostics.sh"
RUNBOOK = REPO_ROOT / "docs" / "RUNBOOK-CLUSTER-TRIAGE.md"
MAKEFILE = REPO_ROOT / "Makefile"

# `kubectl get secret[s] ... -o yaml|json`, i.e. anything that renders values.
SECRET_DUMP = re.compile(r"get\s+secrets?\b[^\n]*-o\s+(yaml|json)")


@pytest.fixture(scope="module")
def collector_text():
    return COLLECTOR.read_text()


@pytest.fixture(scope="module")
def runbook_text():
    return RUNBOOK.read_text()


# --- T1 -------------------------------------------------------------------


def test_collector_never_dumps_secret_contents(collector_text):
    offenders = SECRET_DUMP.findall(collector_text)
    assert not offenders, f"collector would render Secret values: {offenders}"


def test_collector_lists_secrets_by_name_only(collector_text):
    """Knowing which Secrets exist is useful; their values are never triage."""
    if "get secrets" in collector_text:
        assert "get secrets -o name" in collector_text


# --- T2 -------------------------------------------------------------------


def test_collector_tolerates_individual_command_failure(collector_text):
    """Half these commands fail by design during an incident."""
    assert "|| echo" in collector_text, "run() aborts the collection on first failure"


def test_collector_does_not_abort_on_error(collector_text):
    """`set -e` here would stop at the first RBAC denial."""
    assert "set -e" not in collector_text.replace("set -euo", "").replace("set -uo", "")


# --- T3 -------------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "kubectl get pods -A -o wide",  # rung 1: who is the actor
        "kubectl get netpol -A",  # rung 7: declared state
        "iptables-save",  # rung 7: enforced state
        "ipset list",  # rung 7: enforced state
        "nf_conntrack",  # counters, to rule the race in or out
        "get endpoints kubernetes",  # the DNAT trap
        "resolv.conf",  # upstream resolver config
    ],
)
def test_collector_covers_the_ladder(collector_text, command):
    assert command in collector_text, f"collector does not gather: {command}"


def test_collector_resolves_a_pod_by_ip(collector_text):
    """Rung 1. Every error that day carried an IP, and resolving it to a pod
    was consistently the cheapest step and consistently the one skipped."""
    assert "--pod-ip" in collector_text


# --- T4 / T5 --------------------------------------------------------------


@pytest.mark.parametrize(
    "trap",
    [
        "DNAT",  # ClusterIP ipBlock rules cannot match post-DNAT
        "kubernetes.io/metadata.name",  # bare `name` matches no namespace
        "policy random",  # one dead upstream = intermittent, not an outage
        "no endpoints",  # kube-proxy REJECTs, looks like "refused"
    ],
)
def test_runbook_records_the_traps(runbook_text, trap):
    assert trap in runbook_text, f"runbook lost the {trap!r} trap"


def test_runbook_warns_that_refused_can_be_a_policy(runbook_text):
    """T5: this misread ruled out the real culprit for several rounds."""
    assert "REJECT" in runbook_text
    assert "connection refused" in runbook_text


def test_runbook_covers_every_rung(runbook_text):
    for rung in range(1, 8):
        assert f"### {rung}." in runbook_text, f"runbook is missing rung {rung}"


def test_runbook_points_at_the_collector(runbook_text):
    assert "collect-k8s-diagnostics" in runbook_text


def test_collector_make_target_exists():
    assert "collect-k8s-diagnostics:" in MAKEFILE.read_text()
