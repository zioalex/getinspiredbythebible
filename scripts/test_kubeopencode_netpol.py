#!/usr/bin/env python3
"""Tests for the KubeOpenCode strict-tier NetworkPolicies in k8s/kubeopencode/.

BITB-152. These run without a cluster, so CI catches the regressions that a
live check (`scripts/verify-kubeopencode-netpol.sh`) can only catch after a
rollout has already broken something. Every gap below is one that shipped:

- T1: `default-deny-all` uses `podSelector: {}`, so a pod selected by no
  allow-policy has NO egress -- not even DNS. The first cut selected agents by
  `managed-by` and nothing else, leaving the gateway and controller dead:
  `dial tcp: lookup <workspace>... on 10.43.0.10:53: i/o timeout`. The two
  egress policies must therefore PARTITION the namespace.
- T2: the fix for T1 then selected `app.kubernetes.io/name: kubeopencode-server`
  -- which is the *workspace* pods, not the gateway (the gateway is
  `name: kubeopencode`). Same outage, second rollout. No policy may key on that
  label again.
- T3: cluster DNS was selected via `namespaceSelector: {name: kube-system}`. The
  API server sets `kubernetes.io/metadata.name`; a bare `name` label is not set
  by default on k3s or upstream k8s, so the rule matched zero peers.
- T4: an egress policy that forgets port 53 is an outage for whatever it selects,
  because the public `0.0.0.0/0:53` rule excludes the in-cluster resolver.
- T5: `allow-server-ingress` sourced from `name: kubeopencode-server`, i.e. the
  workspace pods -- opening the agent-to-agent `:4096` path the tier exists to
  deny, while still not letting the gateway through.
- T6: the deny-by-`except` construction is the whole strict tier; losing a range
  silently un-hardens it.
- T7/T8: the runbook's own verify commands were wrong in ways that always
  "pass" -- `/dev/tcp` is a bash builtin that the pods' `sh` (dash/busybox) does
  not have, and `kubectl auth can-i` without `--as=` tests the reader's admin
  rights instead of the agent's.
"""

import pathlib
import re

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
K8S_DIR = REPO_ROOT / "k8s" / "kubeopencode"
SECURITY_DOC = REPO_ROOT / "docs" / "SECURITY-KUBEOPENCODE.md"
MAKEFILE = REPO_ROOT / "Makefile"

MANAGED_BY = "app.kubernetes.io/managed-by"
NAME = "app.kubernetes.io/name"

# The label sets actually observed in kubeopencode-system. Pinning them here is
# the point: T1 and T2 were both "the selector named the wrong thing", and only
# real labels catch that.
PLATFORM_GATEWAY = {
    NAME: "kubeopencode",
    "app.kubernetes.io/instance": "kubeopencode",
    "app.kubernetes.io/component": "server",
}
PLATFORM_CONTROLLER = {
    NAME: "kubeopencode",
    "app.kubernetes.io/instance": "kubeopencode",
    "app.kubernetes.io/component": "controller",
}
WORKSPACE = {
    NAME: "kubeopencode-server",
    "app.kubernetes.io/instance": "default-wf2",
    "app.kubernetes.io/component": "server",
    MANAGED_BY: "kubeopencode",
    "kubeopencode.io/agent": "default-wf2",
}
ALL_PODS = {
    "platform gateway": PLATFORM_GATEWAY,
    "platform controller": PLATFORM_CONTROLLER,
    "workspace": WORKSPACE,
}

# The broken probe: a redirect into /dev/tcp, not a mention of the path.
DEV_TCP_PROBE = re.compile(r">\s*/dev/tcp/\S+")

REQUIRED_EXCEPT_RANGES = {
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "169.254.0.0/16",
}


def load(name):
    return yaml.safe_load((K8S_DIR / f"{name}.yaml").read_text())


@pytest.fixture(scope="module")
def policies():
    """Every NetworkPolicy in k8s/kubeopencode/, keyed by metadata.name."""
    out = {}
    for path in sorted(K8S_DIR.glob("networkpolicy-*.yaml")):
        doc = yaml.safe_load(path.read_text())
        assert doc["kind"] == "NetworkPolicy", path
        out[doc["metadata"]["name"]] = doc
    return out


@pytest.fixture(scope="module")
def doc_text():
    return SECURITY_DOC.read_text()


def selector_matches(selector, labels):
    """Minimal LabelSelector evaluation -- matchLabels plus the four operators.

    `{}` selects everything, which is exactly what makes default-deny-all
    dangerous and is why T1 matters.
    """
    if selector is None:
        return False
    for key, value in (selector.get("matchLabels") or {}).items():
        if labels.get(key) != value:
            return False
    for expr in selector.get("matchExpressions") or []:
        key, op = expr["key"], expr["operator"]
        values = expr.get("values", [])
        present = key in labels
        if op == "Exists" and not present:
            return False
        if op == "DoesNotExist" and present:
            return False
        if op == "In" and labels.get(key) not in values:
            return False
        if op == "NotIn" and labels.get(key) in values:
            return False
    return True


def egress_policies(policies):
    """Allow-policies with egress rules, i.e. everything except default-deny."""
    return {
        name: p
        for name, p in policies.items()
        if p["spec"].get("egress") and "Egress" in p["spec"]["policyTypes"]
    }


def allowed_ports(rules):
    return {port["port"] for rule in rules for port in rule.get("ports", [])}


# --- T1 -------------------------------------------------------------------


def test_default_deny_selects_every_pod(policies):
    """The premise of T1: if this stops selecting everything, the partition
    tests below stop meaning anything."""
    assert policies["default-deny-all"]["spec"]["podSelector"] == {}


def test_default_deny_is_egress_only(policies):
    """An Ingress deny would drop kubelet probes -- the node IP matches no
    podSelector, so readiness on :4096 never recovers."""
    assert policies["default-deny-all"]["spec"]["policyTypes"] == ["Egress"]


@pytest.mark.parametrize("pod_name", sorted(ALL_PODS))
def test_every_pod_is_covered_by_exactly_one_egress_policy(policies, pod_name):
    """The T1 regression, stated directly: under a default-deny that selects
    everything, a pod selected by no allow-policy has no DNS and no egress."""
    labels = ALL_PODS[pod_name]
    selecting = [
        name
        for name, policy in egress_policies(policies).items()
        if selector_matches(policy["spec"]["podSelector"], labels)
    ]
    assert selecting, (
        f"{pod_name} {labels} is selected by no egress policy -- "
        "default-deny-all leaves it with no egress at all, not even DNS"
    )
    assert len(selecting) == 1, f"{pod_name} is selected by several: {selecting}"


# --- T2 -------------------------------------------------------------------


def test_no_policy_selects_pods_by_app_name(policies):
    """`name: kubeopencode-server` is the workspace pods and `name: kubeopencode`
    is the platform -- a distinction that has been got wrong twice. The
    policies key on `managed-by` presence instead."""
    for name, policy in policies.items():
        selector = policy["spec"]["podSelector"]
        assert NAME not in (
            selector.get("matchLabels") or {}
        ), f"{name} selects pods by {NAME}; use {MANAGED_BY} presence instead"


def test_platform_policy_selects_by_absent_managed_by(policies):
    exprs = policies["server-egress-strict"]["spec"]["podSelector"]["matchExpressions"]
    assert {"key": MANAGED_BY, "operator": "DoesNotExist"} in exprs


def test_agent_policy_selects_by_present_managed_by(policies):
    selector = policies["agent-egress-strict"]["spec"]["podSelector"]
    assert selector["matchLabels"][MANAGED_BY] == "kubeopencode"


# --- T3 / T4 --------------------------------------------------------------


def _namespace_selectors(policy):
    rules = policy["spec"].get("egress", []) + policy["spec"].get("ingress", [])
    for rule in rules:
        for peer in rule.get("to", []) + rule.get("from", []):
            if "namespaceSelector" in peer:
                yield peer["namespaceSelector"]


def test_namespace_peers_use_the_label_that_exists(policies):
    """A bare `name:` label is not set on namespaces by default, so a peer keyed
    on it silently matches nothing."""
    for name, policy in policies.items():
        for selector in _namespace_selectors(policy):
            labels = selector.get("matchLabels") or {}
            assert "name" not in labels, (
                f"{name} selects a namespace by bare `name`; "
                "use kubernetes.io/metadata.name"
            )


@pytest.mark.parametrize("policy_name", ["agent-egress-strict", "server-egress-strict"])
def test_egress_policy_allows_cluster_dns(policies, policy_name):
    """Both tiers must reach the in-cluster resolver. The public 0.0.0.0/0:53
    rule does not cover it -- CoreDNS sits inside the excluded 10.0.0.0/8."""
    policy = policies[policy_name]
    dns_rules = [
        rule
        for rule in policy["spec"]["egress"]
        if 53 in allowed_ports([rule])
        and any(
            peer.get("podSelector", {}).get("matchLabels", {}).get("k8s-app")
            == "kube-dns"
            or "ipBlock" in peer
            and not peer["ipBlock"].get("except")
            for peer in rule.get("to", [])
        )
    ]
    assert dns_rules, f"{policy_name} has no rule reaching the cluster resolver on :53"


# --- T5 -------------------------------------------------------------------


def test_workspace_ingress_comes_from_platform_not_other_agents(policies):
    """Workspaces accept :4096 from the platform only. A peer that also matches
    workspace pods opens the agent-to-agent path the strict tier denies."""
    policy = policies["allow-server-ingress"]
    assert selector_matches(policy["spec"]["podSelector"], WORKSPACE)
    pod_peers = [
        peer["podSelector"]
        for rule in policy["spec"]["ingress"]
        for peer in rule.get("from", [])
        if "podSelector" in peer
    ]
    assert pod_peers, "no pod peer: the gateway cannot reach workspaces"
    for peer in pod_peers:
        assert not selector_matches(peer, WORKSPACE), (
            "ingress peer matches workspace pods -- this is the agent-to-agent "
            ":4096 path the tier denies"
        )
        assert selector_matches(peer, PLATFORM_GATEWAY), (
            "ingress peer does not match the gateway, which is the one thing "
            "that must reach workspaces"
        )


def test_platform_can_egress_to_workspaces_on_4096(policies):
    """The egress half of the rule above. NetworkPolicy needs both sides, and an
    ipBlock cannot express this peer -- workspace pod IPs are inside the denied
    10.0.0.0/8."""
    rules = [
        rule
        for rule in policies["server-egress-strict"]["spec"]["egress"]
        if 4096 in allowed_ports([rule])
    ]
    assert rules, "gateway has no egress to workspaces on :4096"
    for rule in rules:
        assert any(
            selector_matches(peer.get("podSelector"), WORKSPACE)
            for peer in rule.get("to", [])
            if "podSelector" in peer
        )


# --- T6 -------------------------------------------------------------------


@pytest.mark.parametrize("policy_name", ["agent-egress-strict", "server-egress-strict"])
def test_public_egress_still_denies_private_ranges(policies, policy_name):
    wide = [
        peer["ipBlock"]
        for rule in policies[policy_name]["spec"]["egress"]
        for peer in rule.get("to", [])
        if peer.get("ipBlock", {}).get("cidr") == "0.0.0.0/0"
    ]
    assert wide, f"{policy_name} has no public egress rule"
    for block in wide:
        missing = REQUIRED_EXCEPT_RANGES - set(block.get("except", []))
        assert not missing, f"{policy_name} public egress no longer denies {missing}"


# --- T7 / T8 --------------------------------------------------------------


def test_runbook_has_no_dev_tcp_probes(doc_text):
    """`/dev/tcp` is a bash builtin. The pods' sh is dash/busybox, where it fails
    with "Directory nonexistent" whatever the policy does -- a check that can
    never fail is worse than no check.

    Matches the redirect form only, so the runbook can still name the construct
    when explaining why not to use it.
    """
    offenders = DEV_TCP_PROBE.findall(doc_text)
    assert not offenders, f"/dev/tcp probe in the runbook: {offenders}"


def test_runbook_auth_checks_impersonate_the_agent(doc_text):
    """`kubectl auth can-i` without --as= answers for whoever runs it, which in
    practice is a cluster admin -- every answer is yes."""
    for line in doc_text.splitlines():
        if "auth can-i" in line and not line.lstrip().startswith(("#", ">", "|")):
            assert "--as=" in line, f"auth can-i without --as=: {line.strip()}"


def test_runbook_points_at_the_verify_script(doc_text):
    assert "verify-kubeopencode-netpol" in doc_text


def test_verify_make_target_exists():
    assert "verify-kubeopencode-netpol:" in MAKEFILE.read_text()
