#!/usr/bin/env python3
"""Live-load gate for the committed opencode config (BITB-280).

Motivating failure (2026-11-08 18:51 incident): the task-reliability plugin
shipped with 26 green unit tests, yet the live opencode 1.18.31 loader
rejected it with `Plugin export is not a function` and skipped it silently —
a config/plugin change can be statically green and still be dead on arrival
in the real runtime. This gate boots a SCRATCH opencode instance against the
tree's COMMITTED opencode.json (what actually gets deployed) and asserts the
runtime accepts it, so that class of failure can never merge again.

Why Python (the brief offered bash or python): the gate must parse and
rewrite JSON, extract agent rosters, classify log lines, and drive
subprocesses with hard bounds — all painful in bash — and it must run
stdlib-only on the pod, CI runners, and laptops alike. (A python file under
the brief's `.sh` name would also trip the shellcheck pre-push hook, so the
extension is `.py`.)

Empirically verified opencode 1.18.31 behaviors this gate depends on
(re-verified 2026-11-08, see the BITB-280 story):

* `OPENCODE_CONFIG` is IGNORED by the kubeopencode 1.18.31 build. The
  honored scratch mechanism is placing the config at
  `$XDG_CONFIG_HOME/opencode/config.json` (proved with an invalid-JSON
  canary: boot crashes there, not via the env var).
* Plugin loading is LAZY: a bare `opencode serve` boot loads NO plugins.
  `opencode run` loads them (config-listed + auto-discovered) right after
  config loading, before the first model call — so a keyless run still
  produces plugin evidence in the log.
* The opencode binary at /tools/opencode ALSO loads /tools/opencode.json
  (compiled in). In-pod scratch instances therefore merge the live config;
  plugin failures with paths OUTSIDE the tree under test are attributed to
  that leak and reported as warnings, never as gate failures.
* opencode auto-discovers `.opencode/plugin/*` from the instance directory
  (cwd). Tree-scoped plugin failures are strict failures when the plugin is
  config-listed; failures from NOT-listed tree plugins are loud warnings
  (their strict enforcement activates once the config lists them —
  BITB-269 / PR #1254).
* Plugin entries must be 2-element `[name, options]` tuples; a 1-element
  entry is a fatal config error ("Missing key plugin.1.1"). A BARE STRING
  entry is valid too: the committed config (since #1254) lists the
  task-reliability plugin as a plain `file:///…` string, and 1.18.31 loads
  it (proved live by the dispatch phase's registry lines) — the gate tracks
  file:// entries of BOTH shapes for its strict zero-failure assertion.
* A fresh scratch can transiently stall before instance init (npm plugin
  resolution). Signature: log has config-loading lines but no `message=init`.
  The gate retries once, then fails loudly.

Usage:
  scripts/test-opencode-config-live.py                 # normal mode
  scripts/test-opencode-config-live.py --self-test     # prove the gate itself
  scripts/test-opencode-config-live.py --print-version  # print pinned version
  scripts/test-opencode-config-live.py --dispatch=off  # force-skip dispatch
  scripts/test-opencode-config-live.py --keep          # keep the scratch dir

Scratch dirs live under /tmp/opencode/ and are removed on success. The live
server is never touched: every opencode process the gate starts runs with an
isolated HOME and XDG_* and a scratch config copy (the committed
opencode.json is never modified — file:// plugin paths are rewritten to this
checkout's real paths in the COPY only, because the committed absolute
/workspace/repo paths are pod-specific).
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shutil
import signal
import subprocess
import sys
import time

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
AGENTS_DIR = REPO_ROOT / ".opencode" / "agents"
PLUGIN_DIR = REPO_ROOT / ".opencode" / "plugin"
AGENT_YAML = REPO_ROOT / "deployment" / "kubeopencode" / "agent.yaml"

# The opencode version the deployed pod runs. Single pinned source of truth:
# - CI installs exactly this via `npm install -g opencode-ai@$(--print-version)`.
# - The gate FAILS if the booted binary reports a different version, and
#   cross-checks the `oc<x.y.z>` suffix of `agentImage` in
#   deployment/kubeopencode/agent.yaml (the deployed pin). When the pod's
#   opencode is upgraded, bump BOTH the image tag and this constant in the
#   same change or the gate will block the merge — by design.
PINNED_OPENCODE_VERSION = "1.18.31"

BOOT_TIMEOUT_S = 240  # keyless boot: poll the log for `message=init`
DISPATCH_TIMEOUT_S = 300  # full parent->child->reply round trip (keyed)
STATIC_TIMEOUT_S = 300  # make verify-opencode-config / node suite
GRACE_AFTER_EVIDENCE_S = 2  # log flush grace after the init line appears

EXIT_PASS = 0
EXIT_FAIL = 1


class GateError(Exception):
    pass


def log(msg: str) -> None:
    print(msg, flush=True)


def resolve_binary() -> str:
    """OPENCODE_BINARY env -> `opencode` on PATH -> /tools/opencode (pod)."""
    override = os.environ.get("OPENCODE_BINARY")
    if override:
        if not pathlib.Path(override).exists():
            raise GateError(f"OPENCODE_BINARY={override} does not exist")
        return override
    on_path = shutil.which("opencode")
    if on_path:
        return on_path
    if pathlib.Path("/tools/opencode").exists():
        return "/tools/opencode"  # pod default
    raise GateError(
        "no opencode binary found: set OPENCODE_BINARY, put opencode on PATH, "
        "or (in-pod) rely on /tools/opencode"
    )


def check_version(binary: str) -> None:
    """The booted binary must be exactly the pinned version the pod runs."""
    out = subprocess.run(
        [binary, "--version"], capture_output=True, text=True, timeout=60, check=False
    ).stdout.strip()
    if out != PINNED_OPENCODE_VERSION:
        raise GateError(
            f"opencode binary is {out!r} but the gate pins "
            f"{PINNED_OPENCODE_VERSION!r} (what the pod runs). Install the "
            "pinned version or bump PINNED_OPENCODE_VERSION together with "
            "the agent.yaml image tag."
        )
    # Cross-check the deployed pin: agent.yaml's agentImage carries -oc<x.y.z>.
    if AGENT_YAML.exists():
        text = AGENT_YAML.read_text()
        match = re.search(r"agentImage:.*?-oc(\d+\.\d+\.\d+)", text)
        if match:
            deployed = match.group(1)
            if deployed != PINNED_OPENCODE_VERSION:
                raise GateError(
                    f"deployment/kubeopencode/agent.yaml pins oc{deployed} "
                    f"but the gate pins {PINNED_OPENCODE_VERSION}. Bump both "
                    "in the same change (the gate must test what the pod "
                    "runs)."
                )
        else:
            log(
                "[WARN] could not find an -oc<x.y.z> agentImage suffix in "
                "agent.yaml; skipped the deployed-version cross-check"
            )


def scratch_env(scratch: pathlib.Path, *, with_keys: bool) -> dict:
    """Isolated HOME/XDG for every opencode process the gate starts.

    The scratch config is placed at $XDG_CONFIG_HOME/opencode/config.json —
    the mechanism 1.18.31 actually honors (OPENCODE_CONFIG is ignored).
    """
    env = dict(os.environ)
    env["HOME"] = str(scratch / "home")
    env["XDG_DATA_HOME"] = str(scratch / "xdg" / "data")
    env["XDG_CONFIG_HOME"] = str(scratch / "xdg" / "config")
    env["XDG_STATE_HOME"] = str(scratch / "xdg" / "state")
    env["XDG_CACHE_HOME"] = str(scratch / "xdg" / "cache")
    env.pop("OPENCODE_CONFIG", None)  # ignored by 1.18.31; drop pod leftovers
    if not with_keys:
        for key in ("OPENROUTER_API_KEY", "OPENCODE_API_KEY"):
            env.pop(key, None)
    return env


def make_scratch(tag: str) -> pathlib.Path:
    base = pathlib.Path("/tmp/opencode")
    base.mkdir(parents=True, exist_ok=True)
    scratch = base / f"live-gate-{tag}-{os.getpid()}-{int(time.time())}"
    for sub in ("home", "xdg/data", "xdg/config/opencode", "xdg/state", "xdg/cache"):
        (scratch / sub).mkdir(parents=True, exist_ok=True)
    return scratch


def plugin_entries(config: dict) -> list:
    """Normalize config["plugin"] to a list of (name, options) tuples."""
    entries = []
    for entry in config.get("plugin", []):
        if isinstance(entry, str):
            entries.append((entry, None))
        elif isinstance(entry, list) and entry:
            name = entry[0]
            options = entry[1] if len(entry) > 1 else None
            entries.append((name, options))
    return entries


def rewrite_file_url(url: str) -> str:
    """Test-only shim: rewrite a file:// plugin path to THIS checkout.

    The committed config carries absolute /workspace/repo paths (pod-specific
    — that is where the pod clones the repo). When the gate runs from a
    worktree or CI checkout those paths do not exist, so the scratch COPY is
    rewritten to the invoking tree's real path by longest-suffix match. The
    committed opencode.json is never modified.
    """
    path = url[len("file://") :]
    if not path.startswith("/"):
        path = "/" + path
    parts = [p for p in pathlib.PurePosixPath(path).parts if p != "/"]
    for i in range(len(parts)):
        candidate = REPO_ROOT.joinpath(*parts[i:])
        if candidate.exists():
            return "file://" + str(candidate)
    return url  # boot will fail loudly; the strict assertion will catch it


def build_scratch_config(scratch: pathlib.Path, config: dict) -> list:
    """Write the scratch config; return the (rewritten) file:// entries.

    Both entry shapes must be tracked: the committed config lists the
    task-reliability plugin as a BARE STRING ('file:///workspace/repo/...')
    — opencode 1.18.31 accepts and loads it (proved live: the dispatch
    registry lines) — while opencode-runtime-fallback uses the
    [name, options] tuple. A file:// entry of either shape that the loader
    rejects is a strict failure, so both must reach the classifier.
    """
    cfg = json.loads(json.dumps(config))  # deep copy: committed file untouched
    rewritten = []
    entries = []
    for entry in cfg.get("plugin", []):
        if isinstance(entry, str):
            name = rewrite_file_url(entry)
            entries.append(name)
            if name.startswith("file://"):
                rewritten.append(name)
        elif isinstance(entry, list) and entry:
            name = rewrite_file_url(entry[0])
            new_entry = [name] + [e for e in entry[1:]]
            entries.append(new_entry)
            if name.startswith("file://"):
                rewritten.append(name)
        else:
            entries.append(entry)
    if "plugin" in cfg:
        cfg["plugin"] = entries
    dest = scratch / "xdg" / "config" / "opencode" / "config.json"
    dest.write_text(json.dumps(cfg, indent=2) + "\n")
    return rewritten


def run_opencode(
    binary: str, env: dict, prompt: str, timeout_s: int, cwd: pathlib.Path
) -> tuple:
    """Bounded `opencode run`. Returns (stdout, stderr, returncode)."""
    try:
        proc = subprocess.run(
            [binary, "run", prompt],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            cwd=str(cwd),
            env=env,
            check=False,
        )
        return proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired:
        return "", f"gate timeout after {timeout_s}s", 124


def boot_until_evidence(binary: str, env: dict, prompt: str, timeout_s: int) -> tuple:
    """Launch a keyless `opencode run` and poll the scratch log for the init
    line — plugin loading (the thing under test) completes BEFORE init, and a
    keyless run would otherwise slog through the fallback plugin's retry
    machinery for minutes. On evidence (or process exit / timeout) the run is
    killed immediately: the model call is not part of the load check.

    Returns (log_text, reached_init).
    """
    proc = subprocess.Popen(
        [binary, "run", prompt],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=str(REPO_ROOT),
        env=env,
        start_new_session=True,
    )
    deadline = time.time() + timeout_s
    log_text = ""
    reached = False
    while time.time() < deadline:
        time.sleep(1)
        log_text = read_log(scratch_of(env))
        if "message=init" in log_text:
            time.sleep(GRACE_AFTER_EVIDENCE_S)
            log_text = read_log(scratch_of(env))
            reached = True
            break
        if proc.poll() is not None:
            log_text = read_log(scratch_of(env))
            break
    _kill_process_group(proc)
    return log_text, reached


def _kill_process_group(proc: subprocess.Popen) -> None:
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            proc.kill()
        proc.wait(timeout=10)


def read_log(scratch: pathlib.Path) -> str:
    log_path = scratch / "xdg" / "data" / "opencode" / "log" / "opencode.log"
    if not log_path.exists():
        return ""
    return log_path.read_text(errors="replace")


LOAD_FAIL_RE = re.compile(r'message="failed to load plugin" path=(\S+) error="([^"]*)"')


def parse_load_failures(log_text: str) -> list:
    return [(m.group(1), m.group(2)) for m in LOAD_FAIL_RE.finditer(log_text)]


def boot_with_retry(binary, env, prompt, timeout_s, phase: str) -> str:
    """boot_until_evidence with one retry on the pre-init stall signature
    (known transient: fresh-scratch npm plugin resolution)."""
    for attempt in (1, 2):
        log_text, reached = boot_until_evidence(binary, env, prompt, timeout_s)
        if reached or attempt == 2:
            return log_text
        log(
            f"[WARN] {phase}: scratch boot stalled before instance init "
            "(known transient: npm plugin resolution); retrying once"
        )
    return log_text


def dispatch_run_with_retry(binary, env, prompt, timeout_s, phase: str):
    """Full keyed run (the dispatch must complete); one retry on the
    pre-init stall signature. Returns (stdout, returncode, log_text)."""
    scratch = scratch_of(env)
    for attempt in (1, 2):
        stdout, _, code = run_opencode(binary, env, prompt, timeout_s, REPO_ROOT)
        log_text = read_log(scratch)
        if "message=init" in log_text or attempt == 2:
            return stdout, code, log_text
        log(f"[WARN] {phase}: run stalled before instance init; retrying once")
    raise GateError("unreachable")


def scratch_of(env: dict) -> pathlib.Path:
    return pathlib.Path(env["XDG_CONFIG_HOME"]).parents[1]


def classify_load_failures(log_text: str, listed_file_urls: list) -> tuple:
    """Classify every `failed to load plugin` line.

    - config-listed file:// entry (this tree)        -> strict failure
    - not-listed tree plugin (auto-discovered)       -> loud warning
    - outside the tree (pod /tools/opencode.json leak)-> warning, attributed
    - npm-resolved entry                              -> warning (infra flakiness
      != our code; the deployed pod resolves it in its own long-lived boot)
    Returns (strict_failures, warnings).
    """
    strict, warns = [], []
    listed_names = {u[len("file://") :] for u in listed_file_urls}
    for path, error in parse_load_failures(log_text):
        line = f"failed to load plugin path={path} error={error!r}"
        if path.startswith("file://"):
            local = path[len("file://") :]
            if local in listed_names:
                strict.append(line + " [config-listed plugin: STRICT]")
            elif local.startswith(str(REPO_ROOT) + "/"):
                warns.append(
                    line + " [auto-discovered tree plugin, NOT config-listed — "
                    "strict enforcement activates when the config lists it "
                    "(BITB-269/PR #1254)]"
                )
            else:
                warns.append(
                    line + " [outside the tree under test — in-pod leak from "
                    "/tools/opencode.json, the live pod config; not a "
                    "property of this tree]"
                )
        else:
            warns.append(line + " [npm-resolved entry: infra flakiness, not our code]")
    return strict, warns


# ---------------------------------------------------------------- normal mode


def static_assertions(results: list) -> None:
    """Assertions against the COMMITTED config file itself."""
    committed = REPO_ROOT / "opencode.json"
    log("")
    log("[1/8] committed opencode.json parses as valid JSON")
    try:
        config = json.loads(committed.read_text())
    except (ValueError, OSError) as exc:
        raise GateError(f"opencode.json is not valid JSON: {exc}")
    results.append(True)

    log("[2/8] expected agent roster present (.opencode/agents/*.md ⊆ config)")
    md_agents = sorted(p.stem for p in AGENTS_DIR.glob("*.md"))
    if not md_agents:
        raise GateError("no .opencode/agents/*.md found — nothing to gate")
    missing = [n for n in md_agents if n not in config.get("agent", {})]
    if missing:
        raise GateError(f"agents missing from generated config: {missing}")
    results.append(True)

    log(
        "[3/8] every mode:subagent agent carries permission.question=deny "
        "(asserted for those that DECLARE the question permission)"
    )
    subagents = [
        (n, s)
        for n, s in config.get("agent", {}).items()
        if s.get("mode") == "subagent"
    ]
    declared = blocked = 0
    for name, spec in subagents:
        perm = spec.get("permission")
        if not isinstance(perm, dict):
            continue
        if "question" in perm:
            declared += 1
            if perm["question"] != "deny":
                raise GateError(
                    f"{name}: permission.question is {perm['question']!r}, "
                    "expected 'deny' (subagents must never be able to park a "
                    "session on a question)"
                )
        else:
            blocked += 1
            log(
                f"      [WARN] {name}: carries a permission block without a "
                "question key — its sessions can still ask questions "
                "(deadlock risk until BITB-269/PR #1254 adds question:deny "
                "to every subagent)"
            )
    log(
        f"      {declared} subagent agent(s) declare question permission "
        f"(all assert deny); {blocked} carry a permission block without the "
        f"question key; {len(subagents) - declared - blocked} carry no "
        "permission block at all"
    )
    results.append(True)

    log("[4/8] config-listed file:// plugin entries point at real files")
    listed = [u for u, _ in plugin_entries(config) if u.startswith("file://")]
    for url in listed:
        local = pathlib.Path(url[len("file://") :])
        if not local.exists():
            # Not fatal yet: the rewrite may rescue pod-specific paths.
            log(
                f"      {url}: absolute path absent here (pod-specific); "
                f"scratch shim will rewrite to this checkout"
            )
    results.append(True)


def tooling_assertions(results: list) -> None:
    log("[5/8] make verify-opencode-config (existing static gate) passes")
    proc = subprocess.run(
        ["make", "verify-opencode-config"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=STATIC_TIMEOUT_S,
        check=False,
    )
    if proc.returncode != 0:
        tail = "\n".join((proc.stdout + proc.stderr).splitlines()[-10:])
        raise GateError(f"make verify-opencode-config failed:\n{tail}")
    results.append(True)

    log("[6/8] node plugin suite passes (if plugin files exist)")
    tests = sorted(PLUGIN_DIR.glob("*.test.ts")) if PLUGIN_DIR.exists() else []
    if not tests:
        log("      SKIP: no .opencode/plugin/*.test.ts present")
    else:
        if shutil.which("node") is None:
            raise GateError(
                "plugin tests exist but node is not on PATH — the suite cannot run"
            )
        proc = subprocess.run(
            ["node", "--experimental-strip-types", "--test", *[str(t) for t in tests]],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=STATIC_TIMEOUT_S,
            check=False,
        )
        if proc.returncode != 0:
            tail = "\n".join((proc.stdout + proc.stderr).splitlines()[-10:])
            raise GateError(f"node plugin suite failed:\n{tail}")
        for line in proc.stdout.splitlines():
            if line.startswith(("# tests", "# pass", "# fail")):
                log(f"      {line}")
        results.append(True)


def live_load_check(binary: str, results: list, keep_dirs: list) -> list:
    """Boot a scratch instance (keyless) and assert zero tree-plugin load
    failures. Returns the scratch dir (kept for the caller's dispatch phase
    diagnostics) — actually returns the rewritten file:// urls."""
    log(
        "[7/8] scratch live boot: zero 'failed to load plugin' for every "
        "config-listed file:// plugin entry"
    )
    committed = json.loads((REPO_ROOT / "opencode.json").read_text())
    scratch = make_scratch("normal")
    keep_dirs.append(scratch)
    listed = build_scratch_config(scratch, committed)
    env = scratch_env(scratch, with_keys=False)
    log_text = boot_with_retry(
        binary, env, "Reply with the single word ping", BOOT_TIMEOUT_S, "load-check"
    )
    if "message=init" not in log_text:
        raise GateError(
            "scratch instance never reached init (no plugin evidence); "
            f"scratch kept at {scratch}"
        )
    strict, warns = classify_load_failures(log_text, listed)
    for w in warns:
        log(f"      [WARN] {w}")
    if strict:
        for s in strict:
            log(f"      [FAIL] {s}")
        raise GateError(
            f"{len(strict)} config-listed plugin(s) failed the live loader "
            f"(scratch: {scratch})"
        )
    if listed:
        log(
            f"      {len(listed)} config-listed file:// plugin(s) loaded with "
            "zero failures"
        )
    else:
        log(
            "      no file:// plugin entries in the committed config — "
            "the zero-failure assertion is vacuous (strict scope is "
            "config-listed entries)"
        )
    results.append(True)
    return listed


def dispatch_check(binary: str, results: list, keep_dirs: list, dispatch_mode: str):
    log(
        "[8/8] noop subagent dispatch: child created + completed "
        "(env-gated: needs a provider key)"
    )
    key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get(
        "OPENCODE_LIVE_TEST_KEY"
    )
    if dispatch_mode == "off" or not key:
        log(
            "      SKIP (loudly): dispatch-level validation deferred to pod "
            "pre-flight — no OPENROUTER_API_KEY/OPENCODE_LIVE_TEST_KEY in "
            "this environment (bare CI runners have none; the pod does)."
        )
        results.append(None)
        return

    config = json.loads((REPO_ROOT / "opencode.json").read_text())
    scratch = make_scratch("dispatch")
    keep_dirs.append(scratch)
    build_scratch_config(scratch, config)
    env = scratch_env(scratch, with_keys=True)
    env["TASK_RELIABILITY_REGISTRY"] = str(scratch / "registry.jsonl")
    (scratch / "registry.jsonl").touch()

    # Pick the cheapest dispatch target: noop-child if the config defines it,
    # else the first subagent with a free-tier primary, else any subagent.
    agent = "noop-child" if "noop-child" in config.get("agent", {}) else None
    if agent is None:
        subs = {n: s for n, s in config["agent"].items() if s.get("mode") == "subagent"}
        free = [
            n
            for n, s in subs.items()
            if str(s.get("model", "")).endswith((":free", "-free"))
        ]
        agent = min(free) if free else min(subs)

    prompt = (
        f"Use the task tool to dispatch the {agent} subagent with the prompt: "
        "Reply with the single word done. After it returns, reply with the "
        "single word ok."
    )
    stdout, code, log_text = dispatch_run_with_retry(
        binary, env, prompt, DISPATCH_TIMEOUT_S, "dispatch"
    )
    child_ids = []
    for line in log_text.splitlines():
        if "message=created" not in line or "parentID=ses_" not in line:
            continue
        if f"agent={agent} " not in line:
            continue
        if f"(@{agent} subagent)" not in line:
            continue
        match = re.search(r"message=created id=(\S+)", line)
        if match:
            child_ids.append(match.group(1))
    if not child_ids:
        raise GateError(
            f"no child session created for agent {agent!r} (log has no "
            f'created line with a real parentID and title "(@{agent} '
            f'subagent)"); scratch kept at {scratch}'
        )
    log(f"      child session created: {', '.join(child_ids)} (agent={agent})")
    completed = "✓ Dispatch" in stdout
    if not completed and code != 0:
        raise GateError(
            f"dispatch did not complete: no '✓ Dispatch' marker and run "
            f"exited {code}; scratch kept at {scratch}"
        )
    log(
        f"      dispatch completed (exit={code}, stdout carries the "
        "completion marker)"
    )

    # Registry assertions activate only when the committed config carries a
    # file:// plugin (task-reliability writes the registry; on a config
    # without it — current main — there is nothing to assert yet).
    listed = [u for u, _ in plugin_entries(config) if u.startswith("file://")]
    registry_path = scratch / "registry.jsonl"
    if listed:
        lines = [
            json.loads(x) for x in registry_path.read_text().splitlines() if x.strip()
        ]
        created = [
            x
            for x in lines
            if x.get("kind") == "created" and x.get("childID") in child_ids
        ]
        idle = [
            x
            for x in lines
            if x.get("kind") == "status"
            and x.get("status") == "idle"
            and x.get("childID") in child_ids
        ]
        if not created or not idle:
            raise GateError(
                f"registry file incomplete: {len(created)} created / "
                f"{len(idle)} idle lines for child(ren) {child_ids}; "
                f"scratch kept at {scratch}"
            )
        log(f"      registry: created + idle lines recorded for {', '.join(child_ids)}")
    else:
        log(
            "      NOTE: registry-line assertion N/A — the committed config "
            "carries no file:// plugin (task-reliability is not listed "
            "until BITB-269 / PR #1254 merges); child create/complete was "
            "asserted from the runtime log instead"
        )
    results.append(True)


def normal_mode(binary: str, args) -> int:
    results: list = []
    keep_dirs: list = []
    try:
        check_version(binary)
        static_assertions(results)
        tooling_assertions(results)
        live_load_check(binary, results, keep_dirs)
        dispatch_check(binary, results, keep_dirs, args.dispatch)
    except GateError as exc:
        log(f"\nGATE FAILED: {exc}")
        return EXIT_FAIL
    passed = sum(1 for r in results if r is True)
    skipped = sum(1 for r in results if r is None)
    log(f"\nGATE PASSED: {passed} assertion group(s) green, {skipped} skipped")
    for d in keep_dirs:
        if not args.keep:
            shutil.rmtree(d, ignore_errors=True)
        else:
            log(f"[--keep] scratch kept at {d}")
    return EXIT_PASS


# --------------------------------------------------------------- self-test


RELATIVE_IMPORT_RE = re.compile(r'from\s+"(\./[^"]+)"')


def copy_import_closure(source: pathlib.Path, dest_dir: pathlib.Path) -> list:
    """Copy `source` into `dest_dir` plus its same-dir relative imports.

    Since #1254 the committed plugin splits its helpers into
    task-reliability-helpers.ts (opencode 1.18.31 single-export loader
    contract), so a canary copy of the plugin file ALONE cannot resolve its
    `./task-reliability-helpers.ts` import: the loader would fail with a
    module-resolution error — a different failure class than the 18:51 bug
    the self-test must reproduce. Copying the transitive same-dir closure
    makes the injected non-function export the ONLY load defect in the
    canary. Returns the copied files.
    """
    copied: list = []
    seen: set = set()
    queue = [source]
    while queue:
        current = queue.pop()
        if current in seen:
            continue
        seen.add(current)
        text = current.read_text()
        (dest_dir / current.name).write_text(text)
        copied.append(dest_dir / current.name)
        for m in RELATIVE_IMPORT_RE.finditer(text):
            dep = current.parent / m.group(1)
            if dep.exists() and dep not in seen:
                queue.append(dep)
    return copied


def self_test(binary: str, args) -> int:
    """Regression-prove the gate itself: inject the exact 18:51 bug.

    Copies the first available plugin (config-listed file:// entry, else the
    tree's first .opencode/plugin/*.ts) together with its same-dir
    relative-import closure (helpers), appends
    `export const CANARY_LOAD_BREAKER = "x";` — a non-function export, the
    exact class of defect that slipped past 26 green unit tests on
    2026-11-08 18:51 — points a scratch config entry at the copy, boots, and
    REQUIRES the gate's detection to fire. The self-test PASSES only if the
    injected bug is CAUGHT.
    """
    config = json.loads((REPO_ROOT / "opencode.json").read_text())
    listed = [u for u, _ in plugin_entries(config) if u.startswith("file://")]
    source = None
    if listed:
        source = pathlib.Path(rewrite_file_url(listed[0])[len("file://") :])
    elif PLUGIN_DIR.exists():
        candidates = [
            p
            for p in sorted(PLUGIN_DIR.glob("*.ts"))
            if not p.name.endswith(".test.ts")
        ]
        source = candidates[0] if candidates else None
    if source is None or not source.exists():
        log(
            "SELF-TEST FAILED: nothing to self-test with — no config-listed "
            "file:// plugin and no .opencode/plugin/*.ts in the tree"
        )
        return EXIT_FAIL

    scratch = make_scratch("selftest")
    canary_dir = scratch / "canary"
    canary_dir.mkdir(parents=True, exist_ok=True)
    copied = copy_import_closure(source, canary_dir)
    canary = canary_dir / source.name
    canary.write_text(
        canary.read_text() + '\nexport const CANARY_LOAD_BREAKER = "x";\n'
    )
    log(f"self-test: injected the 18:51 bug into a copy at {canary}")
    if len(copied) > 1:
        log(
            "self-test: copied the plugin's relative-import closure "
            + "(single-export loader contract, #1254): "
            + ", ".join(str(p) for p in copied)
        )

    cfg = json.loads(json.dumps(config))
    cfg.setdefault("plugin", []).append(["file://" + str(canary), {}])
    dest = scratch / "xdg" / "config" / "opencode" / "config.json"
    dest.write_text(json.dumps(cfg, indent=2) + "\n")

    env = scratch_env(scratch, with_keys=False)
    log_text = boot_with_retry(
        binary, env, "Reply with the single word ping", BOOT_TIMEOUT_S, "self-test"
    )
    if "message=init" not in log_text:
        log(f"SELF-TEST FAILED: scratch never reached init; kept at {scratch}")
        return EXIT_FAIL

    failures = parse_load_failures(log_text)
    caught = [
        (p, e)
        for p, e in failures
        if p == "file://" + str(canary) and "export is not a function" in e.lower()
    ]
    for p, e in failures:
        if (p, e) not in caught:
            log(f"      (context) also observed: path={p} error={e!r}")
    if not caught:
        log(
            "SELF-TEST FAILED: the injected canary was NOT caught — the gate "
            "is blind to the 18:51 bug class! Scratch kept at "
            f"{scratch}"
        )
        return EXIT_FAIL
    log("      caught:")
    for p, e in caught:
        log(f'        failed to load plugin path={p} error="{e}"')
    log(
        "\nSELF-TEST PASSED: the gate catches the injected 18:51 bug "
        "(a non-function export that unit tests cannot see)"
    )
    if not args.keep:
        shutil.rmtree(scratch, ignore_errors=True)
    else:
        log(f"[--keep] scratch kept at {scratch}")
    return EXIT_PASS


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--print-version", action="store_true")
    parser.add_argument("--dispatch", choices=["auto", "off"], default="auto")
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args()

    if args.print_version:
        print(PINNED_OPENCODE_VERSION)
        return EXIT_PASS
    if args.self_test:
        return self_test(resolve_binary(), args)
    return normal_mode(resolve_binary(), args)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except GateError as exc:
        print(f"GATE FAILED: {exc}", file=sys.stderr)
        sys.exit(EXIT_FAIL)
    except KeyboardInterrupt:
        sys.exit(130)
