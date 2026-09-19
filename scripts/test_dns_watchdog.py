#!/usr/bin/env python3
"""Tests for the CoreDNS watchdog in k8s/dns-watchdog/ (BITB-155).

These run without a cluster, so CI catches the mistakes a live rollout would
only surface after DNS is already broken -- exactly the failure mode this
watchdog exists to diagnose:

- The bootstrap trap: a watchdog that needs a DNS lookup to report that DNS
  is down is useless. It must build the API server URL from the
  kubelet-injected `KUBERNETES_SERVICE_HOST` / `KUBERNETES_SERVICE_PORT` env
  vars, never a hostname such as `kubernetes.default.svc`.
- TLS must actually be verified (`--cacert`), never skipped with `-k` /
  `--insecure` -- the watchdog authenticates with a ServiceAccount token, so
  an unverified endpoint would hand that token to anything that answers on
  the API server's IP.
- RBAC over-broadening: `patch` is the only write verb this Role may hold,
  and it must be scoped to the `coredns` Deployment by `resourceNames`, or a
  compromised watchdog could patch any Deployment in the namespace. No
  ClusterRole/ClusterRoleBinding, since the watchdog only ever needs
  kube-system.
- A knob wired into the Deployment's env but never read by the script (or
  vice versa) is inert -- `AUTO_RESTART`, `FAILURE_THRESHOLD`, and
  `RESTART_COOLDOWN_SECONDS` must appear on both sides.
- The four diagnostic legs (cluster DNS, internal name, upstream UDP bypass,
  TCP control) are the entire point of the story -- losing one silently
  degrades the failure-time diagnostic bundle back to "reconstruct it later".
- Doc drift: the README's env-var table must cover every variable the
  Deployment actually sets.
"""

import pathlib

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
K8S_DIR = REPO_ROOT / "k8s" / "dns-watchdog"
README = K8S_DIR / "README.md"
MAKEFILE = REPO_ROOT / "Makefile"

CONFIGMAP_PATH = K8S_DIR / "configmap-watchdog.yaml"
RBAC_PATHS = [
    K8S_DIR / "serviceaccount-watchdog.yaml",
    K8S_DIR / "role-watchdog.yaml",
    K8S_DIR / "rolebinding-watchdog.yaml",
]
DEPLOYMENT_PATH = K8S_DIR / "deployment.yaml"

PROBE_ENV_VARS = {
    "PROBE_INTERVAL",
    "PROBE_TIMEOUT",
    "EXTERNAL_NAME",
    "INTERNAL_NAME",
    "UPSTREAM_DNS",
    "TCP_CONTROL_HOST",
    "TCP_CONTROL_PORT",
    "FAILURE_THRESHOLD",
    "AUTO_RESTART",
    "RESTART_COOLDOWN_SECONDS",
}

# Knobs that gate the auto-restart behaviour specifically -- these must be
# wired in *both* the script and the Deployment env, or they are inert.
GATING_ENV_VARS = {"AUTO_RESTART", "FAILURE_THRESHOLD", "RESTART_COOLDOWN_SECONDS"}


def _load_all(path):
    return [doc for doc in yaml.safe_load_all(path.read_text()) if doc]


@pytest.fixture(scope="module")
def configmap_doc():
    docs = _load_all(CONFIGMAP_PATH)
    assert len(docs) == 1, "expected exactly one document in configmap-watchdog.yaml"
    doc = docs[0]
    assert doc["kind"] == "ConfigMap"
    return doc


@pytest.fixture(scope="module")
def watchdog_script(configmap_doc):
    """The literal watchdog.sh text embedded in the ConfigMap."""
    return configmap_doc["data"]["watchdog.sh"]


@pytest.fixture(scope="module")
def rbac_docs():
    """Every RBAC manifest, keyed by (kind, name)."""
    out = {}
    for path in RBAC_PATHS:
        for doc in _load_all(path):
            out[(doc["kind"], doc["metadata"]["name"])] = doc
    return out


@pytest.fixture(scope="module")
def deployment_doc():
    docs = _load_all(DEPLOYMENT_PATH)
    assert len(docs) == 1, "expected exactly one document in deployment.yaml"
    doc = docs[0]
    assert doc["kind"] == "Deployment"
    return doc


@pytest.fixture(scope="module")
def container(deployment_doc):
    containers = deployment_doc["spec"]["template"]["spec"]["containers"]
    assert len(containers) == 1
    return containers[0]


@pytest.fixture(scope="module")
def deployment_env(container):
    return {e["name"]: e.get("value") for e in container.get("env", [])}


@pytest.fixture(scope="module")
def readme_text():
    return README.read_text()


@pytest.fixture(scope="module")
def all_yaml_paths():
    return sorted(K8S_DIR.glob("*.yaml"))


# --- RBAC scope -------------------------------------------------------------


WRITE_VERBS = {"create", "update", "patch", "delete", "deletecollection"}


def test_only_write_verb_anywhere_is_patch(rbac_docs):
    """Every write verb granted by any rule must be either `create` on
    `events`, or `patch` on `deployments` (checked separately for
    resourceNames scoping below) -- nothing else may write anything."""
    role = rbac_docs[("Role", "dns-watchdog")]
    for rule in role["rules"]:
        verbs = set(rule["verbs"])
        resources = set(rule.get("resources", []))
        write_verbs = verbs & WRITE_VERBS
        if not write_verbs:
            continue
        if resources == {"events"}:
            assert write_verbs == {"create"}, f"events rule grants more than create: {rule}"
        elif resources == {"deployments"}:
            assert write_verbs == {"patch"}, f"deployments rule grants more than patch: {rule}"
        else:
            pytest.fail(f"unexpected write verb(s) {write_verbs} on resources {resources}")


def test_every_patch_rule_is_scoped_to_coredns_by_resource_names(rbac_docs):
    role = rbac_docs[("Role", "dns-watchdog")]
    patch_rules = [rule for rule in role["rules"] if "patch" in rule["verbs"]]
    assert patch_rules, "no rule grants patch at all -- restart could never work"
    for rule in patch_rules:
        assert rule.get("resourceNames") == [
            "coredns"
        ], f"patch rule not scoped to resourceNames: ['coredns']: {rule}"


def test_events_rule_grants_create_only(rbac_docs):
    role = rbac_docs[("Role", "dns-watchdog")]
    events_rules = [rule for rule in role["rules"] if "events" in rule.get("resources", [])]
    assert events_rules, "no rule grants access to events"
    for rule in events_rules:
        assert set(rule["verbs"]) == {"create"}, f"events rule grants: {rule['verbs']}"


def test_no_cluster_scoped_rbac_anywhere(all_yaml_paths):
    """The watchdog only ever needs kube-system. A ClusterRole or
    ClusterRoleBinding here would be an unnecessary escalation."""
    for path in all_yaml_paths:
        for doc in _load_all(path):
            assert doc["kind"] not in (
                "ClusterRole",
                "ClusterRoleBinding",
            ), f"{path.name} defines a {doc['kind']}, which is cluster-scoped"


def test_role_and_binding_are_namespaced_to_kube_system(rbac_docs):
    for (kind, _name), doc in rbac_docs.items():
        if kind in ("Role", "RoleBinding", "ServiceAccount"):
            assert doc["metadata"]["namespace"] == "kube-system"


# --- Bootstrap trap ----------------------------------------------------------


def test_script_never_reaches_api_server_by_dns_name(watchdog_script):
    """The whole point of BITB-155: a watchdog that needs DNS to report DNS
    is down is useless. It must build the API URL from the kubelet-injected
    IP/port env vars, never a hostname."""
    assert "kubernetes.default" not in watchdog_script, (
        "script references kubernetes.default -- that is a DNS name and this "
        "watchdog must never depend on DNS to reach the API server"
    )
    assert "KUBERNETES_SERVICE_HOST" in watchdog_script
    assert "KUBERNETES_SERVICE_PORT" in watchdog_script


def test_script_never_disables_tls_verification(watchdog_script):
    for insecure_flag in (" -k ", " -k\n", "--insecure"):
        assert insecure_flag not in watchdog_script, (
            f"script passes {insecure_flag.strip()!r} to curl -- TLS "
            "verification must never be skipped for API server calls"
        )
    assert "--cacert" in watchdog_script


def test_script_authenticates_with_projected_serviceaccount_token(watchdog_script):
    assert "/var/run/secrets/kubernetes.io/serviceaccount/token" in watchdog_script
    assert "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt" in watchdog_script


# --- Four diagnostic legs ----------------------------------------------------


@pytest.mark.parametrize(
    "leg_marker",
    [
        "EXTERNAL_NAME",  # primary probe / cluster_dns
        "INTERNAL_NAME",  # internal_name leg
        "UPSTREAM_DNS",  # upstream_udp leg, bypasses CoreDNS
        "TCP_CONTROL_HOST",  # tcp_control leg, no DNS at all
    ],
)
def test_script_references_every_probe_target(watchdog_script, leg_marker):
    assert leg_marker in watchdog_script


def test_script_has_all_four_result_fields_in_the_failure_log_line(watchdog_script):
    """The failure-time diagnostic bundle: losing any one of these silently
    degrades back to after-the-fact reconstruction."""
    for field in ("cluster_dns=", "internal_name=", "upstream_udp=", "tcp_control="):
        assert field in watchdog_script, f"missing result field {field!r} in script"


def test_script_uses_nc_for_tcp_control_and_nslookup_for_dns_legs(watchdog_script):
    assert "nslookup" in watchdog_script
    assert "nc " in watchdog_script or "\nnc" in watchdog_script


def test_script_emits_failed_and_recovered_events(watchdog_script):
    assert "dns_probe_failed" in watchdog_script
    assert "dns_probe_recovered" in watchdog_script
    assert "Warning" in watchdog_script
    assert "Normal" in watchdog_script


def test_script_restarts_coredns_via_strategic_merge_patch(watchdog_script):
    assert "strategic-merge-patch+json" in watchdog_script
    assert "kubectl.kubernetes.io/restartedAt" in watchdog_script
    assert "/apis/apps/v1/namespaces/kube-system/deployments/coredns" in watchdog_script


def test_script_posts_events_with_involved_object_referencing_coredns(watchdog_script):
    assert "/api/v1/namespaces/kube-system/events" in watchdog_script
    # The JSON body is built as a shell string with backslash-escaped
    # quotes; strip the escaping to check the JSON shape itself.
    unescaped = watchdog_script.replace('\\"', '"')
    assert '"kind":"Deployment"' in unescaped
    assert '"name":"coredns"' in unescaped
    assert '"apiVersion":"apps/v1"' in unescaped


def test_script_guards_probes_with_timeout(watchdog_script):
    assert "timeout" in watchdog_script


def test_script_is_posix_sh_not_bash(watchdog_script):
    assert watchdog_script.lstrip().startswith("#!/bin/sh")
    assert "bash" not in watchdog_script
    assert "[[" not in watchdog_script, "[[ is a bashism; ash/dash only support [ ]"


# --- Knobs wired in both places ----------------------------------------------


@pytest.mark.parametrize("var", sorted(GATING_ENV_VARS))
def test_gating_env_var_wired_in_script_and_deployment(watchdog_script, deployment_env, var):
    assert var in watchdog_script, f"{var} is read nowhere in watchdog.sh"
    assert var in deployment_env, f"{var} is not set in the Deployment env"


def test_all_probe_env_vars_set_on_deployment(deployment_env):
    missing = PROBE_ENV_VARS - set(deployment_env)
    assert not missing, f"Deployment env is missing: {missing}"


def test_deployment_env_defaults_match_story(deployment_env):
    expected = {
        "PROBE_INTERVAL": "30",
        "PROBE_TIMEOUT": "5",
        "EXTERNAL_NAME": "cloudflare.com",
        "INTERNAL_NAME": "kubernetes.default.svc.cluster.local",
        "UPSTREAM_DNS": "8.8.8.8",
        "TCP_CONTROL_HOST": "1.1.1.1",
        "TCP_CONTROL_PORT": "443",
        "FAILURE_THRESHOLD": "3",
        "AUTO_RESTART": "false",
        "RESTART_COOLDOWN_SECONDS": "1800",
    }
    for key, value in expected.items():
        assert deployment_env.get(key) == value, f"{key} default is {deployment_env.get(key)!r}"


# --- ConfigMap volume wiring --------------------------------------------------


def test_deployment_mounts_the_configmap_that_actually_exists(
    deployment_doc, configmap_doc, container
):
    volumes = deployment_doc["spec"]["template"]["spec"]["volumes"]
    cm_volumes = [v for v in volumes if "configMap" in v]
    assert cm_volumes, "no ConfigMap volume defined on the Deployment"
    names_referenced = {v["configMap"]["name"] for v in cm_volumes}
    assert configmap_doc["metadata"]["name"] in names_referenced, (
        f"Deployment references ConfigMap(s) {names_referenced}, but "
        f"configmap-watchdog.yaml defines {configmap_doc['metadata']['name']!r}"
    )

    volume_names = {v["name"] for v in cm_volumes}
    mount_volume_names = {m["name"] for m in container.get("volumeMounts", [])}
    assert volume_names & mount_volume_names, "ConfigMap volume is defined but never mounted"

    command = " ".join(container.get("command", []))
    assert "watchdog.sh" in command, "container command does not run watchdog.sh"
    assert "watchdog.sh" in configmap_doc["data"], "ConfigMap has no watchdog.sh key"


def test_configmap_volume_is_read_only_and_executable(deployment_doc):
    volumes = deployment_doc["spec"]["template"]["spec"]["volumes"]
    cm_volume = next(v for v in volumes if "configMap" in v)
    assert cm_volume["configMap"].get("defaultMode") == 0o755, (
        "defaultMode must make watchdog.sh executable (0755); got "
        f"{cm_volume['configMap'].get('defaultMode')!r}"
    )


# --- securityContext hardening ------------------------------------------------


def test_container_security_context_is_hardened(container):
    sc = container.get("securityContext")
    assert sc, "container has no securityContext"
    assert sc.get("runAsNonRoot") is True
    assert isinstance(sc.get("runAsUser"), int) and sc["runAsUser"] != 0
    assert sc.get("allowPrivilegeEscalation") is False
    assert sc.get("readOnlyRootFilesystem") is True
    assert sc.get("capabilities", {}).get("drop") == ["ALL"]
    assert sc.get("seccompProfile", {}).get("type") == "RuntimeDefault"


def test_deployment_uses_least_privilege_service_account(deployment_doc, rbac_docs):
    spec = deployment_doc["spec"]["template"]["spec"]
    assert spec.get("serviceAccountName") == "dns-watchdog"
    assert ("ServiceAccount", "dns-watchdog") in rbac_docs


def test_deployment_has_resource_limits(container):
    resources = container.get("resources", {})
    assert "requests" in resources and "limits" in resources
    for block in (resources["requests"], resources["limits"]):
        assert "cpu" in block and "memory" in block


def test_deployment_sets_priority_class(deployment_doc):
    spec = deployment_doc["spec"]["template"]["spec"]
    assert spec.get("priorityClassName") == "system-cluster-critical"


# --- Doc drift ---------------------------------------------------------------


@pytest.mark.parametrize("var", sorted(PROBE_ENV_VARS))
def test_readme_documents_every_deployment_env_var(readme_text, var):
    assert var in readme_text, f"README does not document {var}"


def test_readme_documents_how_to_enable_auto_restart(readme_text):
    """Restart is off by default, so the README owes the reader the opt-in."""
    assert "AUTO_RESTART=true" in readme_text


def test_auto_restart_is_off_by_default(deployment_env):
    """The 2026-09-19 incident: the upstream resolver had stopped answering and
    CoreDNS was picking it at random for ~half of all queries. Restarting
    CoreDNS would have changed nothing -- it was the messenger, and an
    auto-restart would have fired repeatedly against a healthy pod. Shipping
    this on by default makes the tool add churn to an incident it cannot fix."""
    assert deployment_env["AUTO_RESTART"] == "false"


def test_readme_justifies_the_auto_restart_default(readme_text):
    """A surprising default with no stated reason gets flipped by the next
    person who reads it."""
    assert "Why restart is off by default" in readme_text


def test_readme_documents_verification_commands(readme_text):
    assert "kubectl -n kube-system logs deploy/dns-watchdog" in readme_text
    assert "get events" in readme_text
    assert "coredns" in readme_text


def test_readme_documents_deploy_command(readme_text):
    assert "role-watchdog.yaml" in readme_text
    assert "configmap-watchdog.yaml" in readme_text
    assert "deployment.yaml" in readme_text


# --- Make target --------------------------------------------------------------


def test_make_targets_exist():
    text = MAKEFILE.read_text()
    assert "test-dns-watchdog:" in text
    assert "deploy-dns-watchdog:" in text


@pytest.mark.parametrize("path", sorted(K8S_DIR.glob("*.yaml")), ids=lambda p: p.name)
def test_every_manifest_is_a_single_document(path):
    """The repo's check-yaml pre-commit hook runs without
    --allow-multiple-documents, so a `---`-separated manifest fails CI even
    though yamllint and kubectl both accept it. One object per file, matching
    the k8s/kubeopencode/ convention."""
    docs = list(yaml.safe_load_all(path.read_text()))
    assert len(docs) == 1, f"{path.name} has {len(docs)} documents; split it"
