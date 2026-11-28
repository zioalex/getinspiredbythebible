#!/usr/bin/env python3
"""Lint every ``az`` invocation in the repo against the real Azure CLI (BITB-374).

Why: BITB-372's ``acr-purge.yml`` shipped ``az acr show-usage --registry X`` (the command only
accepts ``--name/-n``) and failed in production; substring tests and static reviews missed it.
This script extracts every ``az ...`` call from the places the repo runs it and asks the CLI
itself (``az <command> --help``) whether the command and each flag exist.

Scanned:

* ``.github/workflows/*.yml`` and ``.github/actions/**/action.yml`` -- ``run:`` scripts
* ``scripts/**/*.sh``, ``deployment/**/*.sh``, ``Makefile`` (recipe lines)
* ``scripts/**/*.py`` and ``api/**/*.py`` -- ``["az", ...]`` list/tuple literals (AST)

Only ``az`` in *command position* counts (start of a command, after ``$(``, ``|``, ``&&``, ``||``,
``;``, ``then``/``do``/``if``/``!``/``time``/``timeout N``/``env VAR=..``); prose, ``echo`` strings
and comments never do. Heredoc bodies are ignored, and ``--cmd`` values (the ACR task DSL) are
ordinary single-word values so they are never linted.

Allowlist: ``scripts/az-lint-allowlist.txt``, ``path:pattern  # reason``. Every entry needs a reason
and an entry that no longer matches a finding fails the run as stale.

Exit codes: 0 clean, 1 findings, 2 environment error (no ``az`` binary, help timeout).

Standard library only (PyYAML is used for ``run:`` extraction when importable, with a text
fallback). Parsing and validation are pure: ``run_lint`` takes an injectable help provider, so the
tests run without azure-cli.
"""

from __future__ import annotations

import argparse
import ast
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path

try:  # PyYAML is in the api test deps; the text fallback covers its absence.
    import yaml
except ImportError:  # pragma: no cover - exercised via monkeypatch in tests
    yaml = None  # type: ignore[assignment]

REPO_ROOT = Path(__file__).resolve().parent.parent
ALLOWLIST_PATH = "scripts/az-lint-allowlist.txt"
EXTENSIONS_PATH = "scripts/az-extensions.txt"

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_ENV = 2

HELP_TIMEOUT = 90
MAX_PATH_LEN = 6

# Flags every command accepts (the Global Arguments section of any `az ... --help`).
GLOBAL_FLAGS = frozenset(
    "--debug --help -h --only-show-errors --output -o --query --query-examples "
    "--subscription --verbose".split()
)

# Command groups that live in Azure CLI extensions. With dynamic install off the CLI reports a
# missing extension exactly like a typo ("'x' is misspelled"), so the linter needs this hint to
# tell the two apart. Keep in sync with scripts/az-extensions.txt.
KNOWN_EXTENSION_PREFIXES: dict[tuple[str, ...], str] = {
    ("monitor", "app-insights"): "application-insights",
    ("monitor", "log-analytics", "query"): "log-analytics",
}

PATH_WORD_RE = re.compile(r"[a-z][a-z0-9-]*")
ASSIGNMENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
GHA_EXPR_RE = re.compile(r"\$\{\{.*?\}\}", re.DOTALL)
HEREDOC_RE = re.compile(r"(?<!<)<<(?!<)-?\s*([\"']?)([A-Za-z_][\w-]*)\1")
EXT_REQUIRED_RE = re.compile(r"requires the extension[\s'\"`]+([A-Za-z0-9_-]+)")
EXT_ADD_RE = re.compile(r"az extension add\s+(?:--name|-n)\s+([A-Za-z0-9_-]+)")
SKIP_PREFIX_WORDS = frozenset(
    {"then", "do", "else", "elif", "if", "while", "until", "!", "time", "{", "}", "sudo", "exec",
     "command", "nohup", "nice"}
)  # fmt: skip
SKIP_DIRS = frozenset(
    {".git", "node_modules", ".venv", "venv", "__pycache__", "worktrees", ".next", "dist", "build",
     ".mypy_cache", ".ruff_cache", ".pytest_cache"}
)  # fmt: skip


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Word:
    """One shell word after quote removal."""

    text: str
    offset: int
    quoted: bool = False


@dataclass(frozen=True)
class Invocation:
    """One extracted ``az`` call: ``args`` are the words after ``az``."""

    file: str
    line: int
    args: tuple[Word, ...]

    @property
    def command_line(self) -> str:
        return " ".join(["az", *(w.text for w in self.args)])


@dataclass
class Finding:
    file: str
    line: int
    kind: str  # unknown-command | incomplete-command | unknown-flag | unknown-short-flag |
    #            missing-extension | skipped-extension | allowlist-no-reason | stale-allowlist
    message: str
    command: str = ""
    allowlisted: str = ""  # the allowlist reason when suppressed


@dataclass(frozen=True)
class HelpText:
    """Raw result of ``az <path> --help``."""

    returncode: int
    output: str


@dataclass
class ParsedHelp:
    kind: str  # command | group | unknown | extension
    specific: list[tuple[str, ...]] = field(default_factory=list)  # (--name, -n) alias groups
    options: set[str] = field(default_factory=set)  # every accepted flag incl. globals
    children: list[str] = field(default_factory=list)
    extension: str = ""


HelpProvider = Callable[[tuple[str, ...]], HelpText]


class EnvError(Exception):
    """The environment cannot run the check (no az binary, help timeout): exit code 2."""


# ---------------------------------------------------------------------------
# Shell scanner
# ---------------------------------------------------------------------------
class _Scanner:
    """Quote/substitution-aware scanner turning shell text into lists of simple commands.

    Every simple command found anywhere (including inside ``$( )``, backticks and process
    substitutions) is appended to ``commands`` as a list of ``Word``.
    """

    def __init__(self, text: str) -> None:
        self.s = text
        self.commands: list[list[Word]] = []

    def scan(self, i: int, end: str | None) -> int:  # noqa: C901 - one flat state machine
        s, n = self.s, len(self.s)
        cmd: list[Word] = []
        buf: list[str] = []
        state = {"start": -1, "quoted": False, "redir": False}
        depth = 0

        def begin(pos: int) -> None:
            if state["start"] < 0:
                state["start"] = pos

        def flush_word() -> None:
            if state["start"] >= 0:
                if state["redir"]:
                    state["redir"] = False  # redirection target / heredoc delimiter: drop
                else:
                    cmd.append(Word("".join(buf), int(state["start"]), bool(state["quoted"])))
            buf.clear()
            state["start"], state["quoted"] = -1, False

        def flush_cmd() -> None:
            nonlocal cmd
            flush_word()
            if cmd:
                self.commands.append(cmd)
            cmd = []

        def substitution(start_i: int, closer: str) -> int:
            begin(start_i)
            buf.append("$SUBST")
            return self.scan(start_i, closer)

        while i < n:
            c = s[i]
            if c in " \t":
                flush_word()
                i += 1
            elif c == "\n":
                flush_cmd()
                i += 1
            elif c == "\\":
                if i + 1 < n and s[i + 1] == "\n":
                    i += 2
                elif i + 1 < n:
                    begin(i)
                    state["quoted"] = True
                    buf.append(s[i + 1])
                    i += 2
                else:
                    i += 1
            elif c == "#" and state["start"] < 0:
                while i < n and s[i] != "\n":
                    i += 1
            elif c == "'":
                begin(i)
                state["quoted"] = True
                j = s.find("'", i + 1)
                j = n if j < 0 else j
                buf.append(s[i + 1 : j])
                i = j + 1
            elif c == '"':
                begin(i)
                state["quoted"] = True
                i += 1
                while i < n and s[i] != '"':
                    d = s[i]
                    if d == "\\" and i + 1 < n:
                        if s[i + 1] in '"\\$`':
                            buf.append(s[i + 1])
                        elif s[i + 1] != "\n":
                            buf.append("\\" + s[i + 1])
                        i += 2
                    elif d == "$" and s.startswith("$(", i) and not s.startswith("$((", i):
                        i = substitution(i + 2, ")")
                    elif d == "$" and s.startswith("${", i):
                        j = self._brace_end(i + 1)
                        buf.append(s[i:j])
                        i = j
                    elif d == "`":
                        i = substitution(i + 1, "`")
                    else:
                        buf.append(d)
                        i += 1
                i += 1  # closing quote
            elif c == "`":
                if end == "`":
                    flush_cmd()
                    return i + 1
                i = substitution(i + 1, "`")
            elif c == "$":
                if s.startswith("$((", i):
                    begin(i)
                    buf.append("$ARITH")
                    i = self._paren_end(i + 2)
                elif s.startswith("$(", i):
                    i = substitution(i + 2, ")")
                elif s.startswith("${", i):
                    begin(i)
                    j = self._brace_end(i + 1)
                    buf.append(s[i:j])
                    i = j
                else:
                    begin(i)
                    buf.append("$")
                    i += 1
            elif c in "<>" or (c == "&" and s.startswith("&>", i)):
                if state["start"] >= 0 and "".join(buf).isdigit():
                    buf.clear()
                    state["start"] = -1  # fd number of `2>`
                else:
                    flush_word()
                j = i
                while j < n and s[j] in "<>&":
                    j += 1
                if j < n and s[j] == "(":  # process substitution <( ) / >( )
                    begin(i)
                    buf.append("$PROCSUB")
                    i = self.scan(j + 1, ")")
                else:
                    if j < n and s[j] == "|":
                        j += 1
                    state["redir"] = True
                    i = j
            elif c in "|&;":
                flush_cmd()
                i += 1
                while i < n and s[i] in "|&;":
                    i += 1
            elif c == "(":
                flush_cmd()
                depth += 1
                i += 1
            elif c == ")":
                flush_cmd()
                i += 1
                if depth > 0:
                    depth -= 1
                elif end == ")":
                    return i
            else:
                begin(i)
                buf.append(c)
                i += 1
        flush_cmd()
        return n

    def _brace_end(self, i: int) -> int:
        """Index just past the ``}`` matching the ``{`` at ``i`` (or end of text)."""
        depth = 0
        for j in range(i, len(self.s)):
            if self.s[j] == "{":
                depth += 1
            elif self.s[j] == "}":
                depth -= 1
                if depth == 0:
                    return j + 1
        return len(self.s)

    def _paren_end(self, i: int) -> int:
        depth = 0
        for j in range(i, len(self.s)):
            if self.s[j] == "(":
                depth += 1
            elif self.s[j] == ")":
                depth -= 1
                if depth == 0:
                    return j + 1
        return len(self.s)


def blank_heredocs(text: str) -> str:
    """Replace heredoc bodies (and their terminators) with empty lines, keeping line numbers."""
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        delimiters = [m.group(2) for m in HEREDOC_RE.finditer(lines[i])]
        i += 1
        for delim in delimiters:
            while i < len(lines):
                done = lines[i].strip() == delim
                lines[i] = ""
                i += 1
                if done:
                    break
    return "\n".join(lines)


def _find_az(cmd: list[Word]) -> int | None:
    """Index of the ``az`` word if the command *is* an az call, else None."""
    i = 0
    while i < len(cmd):
        t = cmd[i].text
        if cmd[i].quoted:
            return None
        if t in SKIP_PREFIX_WORDS or ASSIGNMENT_RE.match(t):
            i += 1
        elif t == "timeout":
            i += 1
            while i < len(cmd) and cmd[i].text.startswith("-"):
                i += 1
            while i < len(cmd) and re.fullmatch(r"\d+[smhd]?", cmd[i].text):
                i += 1  # `-k 5` value and the duration itself
        elif t == "env":
            i += 1
            while i < len(cmd) and (
                cmd[i].text.startswith("-") or ASSIGNMENT_RE.match(cmd[i].text)
            ):
                i += 1
        elif t == "az":
            return i
        else:
            return None
    return None


def extract_from_shell(text: str, file: str, base_line: int = 1) -> list[Invocation]:
    """Extract ``az`` invocations from shell script text. ``base_line`` is the line of its first line."""
    text = blank_heredocs(GHA_EXPR_RE.sub("${GHA}", text))
    scanner = _Scanner(text)
    scanner.scan(0, None)
    found = []
    for cmd in scanner.commands:
        idx = _find_az(cmd)
        if idx is not None:
            line = base_line + text.count("\n", 0, cmd[idx].offset)
            found.append(Invocation(file, line, tuple(cmd[idx + 1 :])))
    return sorted(found, key=lambda inv: inv.line)


def extract_from_makefile(text: str, file: str) -> list[Invocation]:
    """Recipe lines only: strip ``@ - +`` prefixes, turn ``$$`` into ``$`` and ``$(VAR)`` into text."""
    out: list[str] = []
    in_recipe = False
    for raw in text.split("\n"):
        if raw.startswith("\t") or (in_recipe and raw.strip()):
            first = not in_recipe
            line = raw[1:] if raw.startswith("\t") else raw
            if first:
                line = re.sub(r"^[@\-+\s]+", "", line)
            line = line.replace("$$", "\x00")
            line = line.replace("$(shell ", "$(")
            line = re.sub(r"\$\(([A-Za-z_][\w.-]*)\)", r"${MK_\1}", line)
            line = line.replace("\x00", "$")
            out.append(line)
            in_recipe = raw.rstrip().endswith("\\")
        else:
            out.append("")
            in_recipe = False
    return extract_from_shell("\n".join(out), file)


# ---------------------------------------------------------------------------
# YAML (workflows and composite actions)
# ---------------------------------------------------------------------------
def _yaml_run_blocks(text: str) -> list[tuple[int, str]]:
    """(first content line, script) for every ``run:`` scalar, via PyYAML when available."""
    assert yaml is not None
    root = yaml.compose(text)
    blocks: list[tuple[int, str]] = []

    def walk(node: object) -> None:
        if isinstance(node, yaml.MappingNode):
            for key, value in node.value:
                if (
                    isinstance(key, yaml.ScalarNode)
                    and key.value == "run"
                    and isinstance(value, yaml.ScalarNode)
                ):
                    start = value.start_mark.line + 1  # 1-based line of the scalar / indicator
                    if value.style in ("|", ">"):
                        start += 1
                    blocks.append((start, value.value))
                else:
                    walk(value)
        elif isinstance(node, yaml.SequenceNode):
            for item in node.value:
                walk(item)

    if root is not None:
        walk(root)
    return blocks


def _text_run_blocks(text: str) -> list[tuple[int, str]]:
    """Fallback ``run:`` extraction without PyYAML (block scalars and single-line values)."""
    lines = text.split("\n")
    blocks: list[tuple[int, str]] = []
    key_re = re.compile(r"^(\s*)(?:-\s+)?run:\s*(.*)$")
    i = 0
    while i < len(lines):
        m = key_re.match(lines[i])
        i += 1
        if not m:
            continue
        indent, value = len(m.group(1)), m.group(2).strip()
        if re.match(r"^[|>][+-]?\d*$", value):
            body: list[str] = []
            first = i + 1
            block_indent: int | None = None
            while i < len(lines):
                ln = lines[i]
                if ln.strip():
                    cur = len(ln) - len(ln.lstrip())
                    if cur <= indent:
                        break
                    if block_indent is None:
                        block_indent = cur
                    body.append(ln[block_indent:])
                else:
                    body.append("")
                i += 1
            blocks.append((first, "\n".join(body)))
        elif value:
            if value[0] in "\"'" and value[-1] == value[0]:
                value = value[1:-1]
            blocks.append((i, value))
    return blocks


def extract_from_yaml(text: str, file: str) -> list[Invocation]:
    blocks = None
    if yaml is not None:
        try:
            blocks = _yaml_run_blocks(text)
        except yaml.YAMLError:
            blocks = None
    if blocks is None:
        blocks = _text_run_blocks(text)
    found: list[Invocation] = []
    for line, script in blocks:
        found.extend(extract_from_shell(script, file, base_line=line))
    return sorted(found, key=lambda inv: inv.line)


# ---------------------------------------------------------------------------
# Python (subprocess argv literals)
# ---------------------------------------------------------------------------
def _argv_words(elts: list[ast.expr]) -> tuple[Word, ...]:
    words = []
    for elt in elts:
        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
            words.append(Word(elt.value, 0))
        else:
            words.append(Word("$EXPR", 0))
    return tuple(words)


def _is_az_head(node: ast.AST) -> bool:
    return (
        isinstance(node, (ast.List, ast.Tuple))
        and bool(node.elts)
        and isinstance(node.elts[0], ast.Constant)
        and node.elts[0].value == "az"
    )


def _wrapper_param(func: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[int, str] | None:
    """(positional index, name) of the parameter a wrapper splices into ``["az", *param]``."""
    params = [a.arg for a in func.args.args]
    for node in ast.walk(func):
        name = None
        if isinstance(node, (ast.List, ast.Tuple)) and _is_az_head(node):
            rest = node.elts[1:]  # bare ["az", *param] only: literal words make it a real call
            if len(rest) == 1 and isinstance(rest[0], ast.Starred):
                if isinstance(rest[0].value, ast.Name):
                    name = rest[0].value.id
        elif (
            isinstance(node, ast.BinOp)
            and isinstance(node.op, ast.Add)
            and _is_az_head(node.left)
            and isinstance(node.right, ast.Name)
        ):
            name = node.right.id
        if name in params:
            return params.index(name), name
    return None


def _find_wrappers(tree: ast.AST) -> tuple[dict[str, tuple[int, str]], set[int]]:
    """Wrapper functions (name -> (arg index, param name)) and the ids of their internal argv lists."""
    wrappers: dict[str, tuple[int, str]] = {}
    internal: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        found_param = _wrapper_param(node)
        if found_param:
            idx, pname = found_param
            if node.args.args and node.args.args[0].arg in ("self", "cls"):
                idx -= 1
            wrappers[node.name] = (idx, pname)
            internal.update(id(n) for n in ast.walk(node) if _is_az_head(n))
    return wrappers, internal


def _call_site_argv(node: ast.Call, wrappers: dict[str, tuple[int, str]]) -> list[ast.expr] | None:
    """The argv list literal a wrapper call passes, if it is one."""
    fn = node.func
    name = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", "")
    if name not in wrappers:
        return None
    idx, pname = wrappers[name]
    arg = node.args[idx] if 0 <= idx < len(node.args) else None
    for kw in node.keywords:
        if kw.arg == pname:
            arg = kw.value
    return arg.elts if isinstance(arg, (ast.List, ast.Tuple)) else None


def extract_from_python(text: str, file: str) -> list[Invocation]:
    """argv list/tuple literals starting with ``"az"``, plus wrapper call sites.

    A function whose body builds ``["az", *param]`` (or ``["az"] + param``) is a wrapper: the list
    literal passed as that parameter at each call site in the module is an argv list too. Other
    non-literal elements become ``$EXPR``.
    """
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    wrappers, internal = _find_wrappers(tree)
    found = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.List, ast.Tuple)) and _is_az_head(node):
            if id(node) not in internal:
                found.append(Invocation(file, node.lineno, _argv_words(node.elts[1:])))
        elif isinstance(node, ast.Call) and wrappers:
            elts = _call_site_argv(node, wrappers)
            if elts is not None:
                found.append(Invocation(file, node.lineno, _argv_words(elts)))
    return sorted(found, key=lambda inv: inv.line)


def unresolved_invocations(invocations: Iterable[Invocation]) -> list[Invocation]:
    """Python ``az`` calls with no literal command path (cannot be validated)."""
    return [i for i in invocations if i.file.endswith(".py") and not command_path(i.args)]


# ---------------------------------------------------------------------------
# Terraform local-exec
# ---------------------------------------------------------------------------
TF_HEREDOC_RE = re.compile(r"^\s*command\s*=\s*<<-?\s*([A-Za-z_]\w*)\s*$")
TF_INLINE_RE = re.compile(r'^\s*command\s*=\s*"((?:[^"\\]|\\.)*)"\s*$')


def extract_from_terraform(text: str, file: str) -> list[Invocation]:
    """``command = <<-EOT ... EOT`` bodies and single-line ``command = "..."`` as shell.

    Terraform ``${...}`` interpolations read as shell variables; ``$${`` is a literal ``${``.
    """
    lines = text.split("\n")
    found: list[Invocation] = []
    i = 0
    while i < len(lines):
        m = TF_HEREDOC_RE.match(lines[i])
        inline = TF_INLINE_RE.match(lines[i])
        if m:
            start = i + 2  # 1-based line of the first body line
            body: list[str] = []
            i += 1
            while i < len(lines) and lines[i].strip() != m.group(1):
                body.append(lines[i])
                i += 1
            script = "\n".join(body).replace("$${", "${")
            found.extend(extract_from_shell(script, file, base_line=start))
        elif inline:
            script = inline.group(1).replace('\\"', '"').replace("$${", "${")
            found.extend(extract_from_shell(script, file, base_line=i + 1))
        i += 1
    return sorted(found, key=lambda inv: inv.line)


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------
def _walk(root: Path, sub: str, suffix: str) -> Iterable[Path]:
    base = root / sub
    if not base.is_dir():
        return
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            if name.endswith(suffix):
                yield Path(dirpath) / name


def _discover_yaml(root: Path) -> list[tuple[str, str]]:
    found = []
    wf = root / ".github" / "workflows"
    if wf.is_dir():
        found += [("yaml", p.relative_to(root).as_posix()) for p in sorted(wf.iterdir())
                  if p.suffix in (".yml", ".yaml")]  # fmt: skip
    found += [("yaml", p.relative_to(root).as_posix()) for p in _walk(root, ".github/actions", "")
              if p.name in ("action.yml", "action.yaml")]  # fmt: skip
    return found


def discover_files(root: Path) -> list[tuple[str, str]]:
    """(kind, relative posix path) for every file the linter reads."""
    files = _discover_yaml(root)
    for sub in ("scripts", "deployment"):
        files += [("shell", p.relative_to(root).as_posix()) for p in _walk(root, sub, ".sh")]
    if (root / "Makefile").is_file():
        files.append(("make", "Makefile"))
    files += [
        ("terraform", p.relative_to(root).as_posix()) for p in _walk(root, "deployment", ".tf")
    ]
    for sub in ("scripts", "api"):
        files += [("python", p.relative_to(root).as_posix()) for p in _walk(root, sub, ".py")]
    return files


def extract_all(root: Path, only: list[str] | None = None) -> list[Invocation]:
    found: list[Invocation] = []
    for kind, rel in discover_files(root):
        if only and not any(rel == o or rel.startswith(o.rstrip("/") + "/") for o in only):
            continue
        if rel == "scripts/check_az_commands.py":
            continue  # its ["az", *path] lists format messages, they are not subprocess calls
        text = (root / rel).read_text(encoding="utf-8", errors="replace")
        if kind == "yaml":
            found.extend(extract_from_yaml(text, rel))
        elif kind == "shell":
            found.extend(extract_from_shell(text, rel))
        elif kind == "make":
            found.extend(extract_from_makefile(text, rel))
        elif kind == "terraform":
            found.extend(extract_from_terraform(text, rel))
        else:
            found.extend(extract_from_python(text, rel))
    return found


# ---------------------------------------------------------------------------
# Help parsing and validation
# ---------------------------------------------------------------------------
def _parse_command_help(lines: list[str]) -> ParsedHelp:
    parsed = ParsedHelp("command", options=set(GLOBAL_FLAGS))
    in_args = in_global = False
    for ln in lines:
        if re.match(r"^[A-Z][A-Za-z ]*:?$", ln) and ln.strip() != "Command":
            title = ln.strip().rstrip(":")
            in_args = title.endswith("Arguments")
            in_global = title.startswith("Global")
            continue
        m = re.match(r"^ {4}(-\S.*?)(?: +:(?: |$).*)?$", ln) if in_args else None
        if not m:
            continue
        flags = tuple(t for t in m.group(1).split() if re.fullmatch(r"-{1,2}[A-Za-z][\w-]*", t))
        parsed.options.update(flags)
        if flags and not in_global:
            parsed.specific.append(flags)
    return parsed


def _parse_group_help(lines: list[str]) -> ParsedHelp:
    parsed = ParsedHelp("group")
    section = ""
    for ln in lines:
        if re.match(r"^(Subgroups|Commands):\s*$", ln):
            section = ln.strip()
        elif re.match(r"^[A-Z]", ln):
            section = ""
        elif section and (m := re.match(r"^ {4}([a-z][a-z0-9-]*)\b", ln)):
            parsed.children.append(m.group(1))
    return parsed


def parse_help(help_text: HelpText) -> ParsedHelp:
    """Classify ``az <path> --help`` output and collect the accepted flags."""
    text = ANSI_RE.sub("", help_text.output)
    lines = text.splitlines()
    header = next((ln.strip() for ln in lines if ln.strip() in ("Command", "Group")), "")
    ext = EXT_REQUIRED_RE.search(text) or EXT_ADD_RE.search(text)
    if ext and header != "Command":
        return ParsedHelp("extension", extension=ext.group(1))
    if header == "Command":
        return _parse_command_help(lines)
    if header == "Group":
        return _parse_group_help(lines)
    return ParsedHelp("unknown")


def command_path(args: Iterable[Word]) -> list[str]:
    """Leading lowercase words after ``az`` (stops at flags, quotes, ``$``, ``=``, ``/``, ``.``)."""
    path: list[str] = []
    for w in args:
        if w.quoted or not PATH_WORD_RE.fullmatch(w.text) or len(path) >= MAX_PATH_LEN:
            break
        path.append(w.text)
    return path


class HelpCache:
    """Memoises ``provider(path)`` -> ParsedHelp (thread-safe)."""

    def __init__(self, provider: HelpProvider) -> None:
        self._provider = provider
        self._cache: dict[tuple[str, ...], ParsedHelp] = {}
        self._lock = threading.Lock()

    def get(self, path: tuple[str, ...]) -> ParsedHelp:
        with self._lock:
            hit = self._cache.get(path)
        if hit is not None:
            return hit
        parsed = parse_help(self._provider(path))
        with self._lock:
            self._cache[path] = parsed
        return parsed


def _extension_for(path: list[str]) -> str:
    for prefix, ext in KNOWN_EXTENSION_PREFIXES.items():
        if tuple(path[: len(prefix)]) == prefix:
            return ext
    return ""


def _missing_extension(inv: Invocation, shown: str, ext: str) -> Finding:
    msg = (
        f"'{shown}' needs the Azure CLI extension '{ext}' (az extension add --name {ext}); "
        f"pin it as '{ext}==<version>' in {EXTENSIONS_PATH}"
    )
    return Finding(inv.file, inv.line, "missing-extension", msg, inv.command_line)


def _format_flags(groups: list[tuple[str, ...]]) -> str:
    return " ".join("/".join(g) for g in groups) or "(none)"


def _check_flags(inv: Invocation, path: list[str], help_: ParsedHelp) -> list[Finding]:
    findings: list[Finding] = []
    cmd = " ".join(["az", *path])
    skip = len(path)
    for w in inv.args[skip:]:
        tok = w.text
        if w.quoted and not tok.startswith("-"):
            continue
        if tok == "--":
            break
        if tok.startswith("--") and len(tok) > 2:
            name = tok.split("=", 1)[0]
            if "$" in name or name in help_.options:
                continue
            near = difflib.get_close_matches(name, sorted(help_.options), n=1)
            hint = f" Did you mean {near[0]}?" if near else ""
            findings.append(
                Finding(inv.file, inv.line, "unknown-flag",
                        f"'{name}' is not a flag of '{cmd}'.{hint} "
                        f"Valid flags: {_format_flags(help_.specific)} "
                        f"(plus global: {' '.join(sorted(GLOBAL_FLAGS))})",
                        inv.command_line)
            )  # fmt: skip
        elif re.match(r"^-[A-Za-z]", tok):
            short = tok[:2]
            if short not in help_.options and "$" not in tok:
                findings.append(
                    Finding(inv.file, inv.line, "unknown-short-flag",
                            f"short flag '{short}' is not accepted by '{cmd}'. "
                            f"Valid flags: {_format_flags(help_.specific)}",
                            inv.command_line)
                )  # fmt: skip
    return findings


def validate_invocation(inv: Invocation, helps: HelpCache) -> list[Finding]:
    """Check one invocation's command path and flags against the CLI's help."""
    path = command_path(inv.args)
    if not path:
        return []
    asked_help = any(w.text in ("-h", "--help") for w in inv.args)
    for k in range(len(path), 0, -1):
        prefix = tuple(path[:k])
        help_ = helps.get(prefix)
        cmd = " ".join(["az", *prefix])
        if help_.kind == "command":
            return _check_flags(inv, list(prefix), help_)
        if help_.kind == "extension":
            return [_missing_extension(inv, cmd, help_.extension)]
        if help_.kind == "group":
            if k == len(path):
                if asked_help:
                    return []
                return [Finding(inv.file, inv.line, "incomplete-command",
                                f"'{cmd}' is a command group, not a command. Choose one of: "
                                f"{' '.join(help_.children)}",
                                inv.command_line)]  # fmt: skip
            bad = " ".join(["az", *path[: k + 1]])
            ext = _extension_for(path[: k + 1])
            if ext:
                return [_missing_extension(inv, bad, ext)]
            return [Finding(inv.file, inv.line, "unknown-command",
                            f"unknown command '{bad}'. '{cmd}' has: {' '.join(help_.children)}",
                            inv.command_line)]  # fmt: skip
    ext = _extension_for(path)
    if ext:
        return [_missing_extension(inv, " ".join(["az", *path]), ext)]
    return [Finding(inv.file, inv.line, "unknown-command",
                    f"unknown command 'az {path[0]}' (if it belongs to an Azure CLI extension, "
                    f"add '<name>==<version>' to {EXTENSIONS_PATH})",
                    inv.command_line)]  # fmt: skip


# ---------------------------------------------------------------------------
# Allowlist
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class AllowEntry:
    path: str
    pattern: str
    reason: str
    lineno: int


def parse_allowlist(
    text: str, source: str = ALLOWLIST_PATH
) -> tuple[list[AllowEntry], list[Finding]]:
    """Parse ``path:pattern  # reason`` lines; entries without a reason become findings."""
    entries: list[AllowEntry] = []
    problems: list[Finding] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = re.search(r"\s+#\s*", line)
        body, reason = (line[: m.start()], line[m.end() :]) if m else (line, "")
        path, colon, pattern = body.partition(":")
        if not colon or not path.strip() or not pattern.strip():
            problems.append(Finding(source, lineno, "allowlist-no-reason",
                                    f"malformed allowlist entry (want 'path:pattern  # reason'): {line}"))  # fmt: skip
            continue
        if not reason.strip():
            problems.append(Finding(source, lineno, "allowlist-no-reason",
                                    f"allowlist entry has no reason (append '  # why'): {line}"))  # fmt: skip
            continue
        entries.append(AllowEntry(path.strip(), pattern.strip(), reason.strip(), lineno))
    return entries, problems


def apply_allowlist(
    findings: list[Finding], entries: list[AllowEntry], source: str = ALLOWLIST_PATH
) -> list[Finding]:
    """Mark matching findings as allowlisted; add a stale finding for every unused entry."""
    used: set[int] = set()
    for f in findings:
        for idx, e in enumerate(entries):
            if f.file == e.path and e.pattern in f.command:
                f.allowlisted = f.allowlisted or e.reason
                used.add(idx)
    stale = [
        Finding(source, e.lineno, "stale-allowlist",
                f"stale allowlist entry (matches no finding; delete it): {e.path}:{e.pattern}")
        for idx, e in enumerate(entries) if idx not in used
    ]  # fmt: skip
    return findings + stale


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------
def run_lint(
    invocations: list[Invocation],
    provider: HelpProvider,
    allowlist_text: str = "",
    skip_missing_extensions: bool = False,
    jobs: int = 1,
    only_paths: list[str] | None = None,
) -> list[Finding]:
    """Validate every invocation; returns all findings (allowlisted ones flagged, not removed)."""
    helps = HelpCache(provider)
    if jobs > 1:  # warm the cache with the full path of each distinct command in parallel
        paths = sorted({tuple(command_path(i.args)) for i in invocations} - {()})
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            list(pool.map(helps.get, paths))
    findings: list[Finding] = []
    for inv in invocations:
        for f in validate_invocation(inv, helps):
            if f.kind == "missing-extension" and skip_missing_extensions:
                f.kind = "skipped-extension"
                f.message = "skipped: extension not installed (" + f.message + ")"
            findings.append(f)
    entries, problems = parse_allowlist(allowlist_text)
    if only_paths:  # a partial run cannot judge staleness of entries for files it did not read
        entries = [e for e in entries if any(e.path.startswith(p) for p in only_paths)]
    return apply_allowlist(findings, entries) + problems


def is_failure(f: Finding) -> bool:
    return not f.allowlisted and f.kind != "skipped-extension"


def make_az_provider(az: str = "az", timeout: int = HELP_TIMEOUT) -> HelpProvider:
    env = {
        **os.environ,
        "AZURE_EXTENSION_USE_DYNAMIC_INSTALL": "no",
        "AZURE_CORE_ONLY_SHOW_ERRORS": "true",
        "AZURE_CORE_COLLECT_TELEMETRY": "no",
        "AZURE_CORE_NO_COLOR": "true",
        "PYTHONWARNINGS": "ignore",
    }

    def provider(path: tuple[str, ...]) -> HelpText:
        try:
            proc = subprocess.run(
                [az, *path, "--help"],
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
                stdin=subprocess.DEVNULL,
                check=False,
            )
        except FileNotFoundError as exc:
            raise EnvError(f"the Azure CLI binary '{az}' was not found on PATH") from exc
        except subprocess.TimeoutExpired as exc:
            raise EnvError(f"'{az} {' '.join(path)} --help' timed out after {timeout}s") from exc
        return HelpText(proc.returncode, proc.stdout + "\n" + proc.stderr)

    return provider


def _print_findings(findings: list[Finding]) -> None:
    for f in findings:
        if f.allowlisted:
            continue
        print(f"{f.file}:{f.line}: [{f.kind}] {f.message}")
        if f.command:
            print(f"    {f.command}")


def main(argv: list[str] | None = None, provider: HelpProvider | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("paths", nargs="*", help="limit to these repo-relative files/dirs")
    ap.add_argument("--root", type=Path, default=REPO_ROOT)
    ap.add_argument("--allowlist", default=ALLOWLIST_PATH)
    ap.add_argument("--list", action="store_true", help="print every extracted az invocation")
    ap.add_argument("--json", action="store_true", help="machine-readable findings")
    ap.add_argument("--skip-missing-extensions", action="store_true",
                    help="local runs: report extension commands as skipped instead of failing")  # fmt: skip
    ap.add_argument("--if-az-available", action="store_true",
                    help="exit 0 with a notice instead of an error when az is not on PATH (pre-push hook)")  # fmt: skip
    ap.add_argument("--jobs", type=int, default=4, help="parallel `az --help` calls")
    ap.add_argument("--az", default="az", help="path to the az binary")
    args = ap.parse_args(argv)

    if args.if_az_available and not args.list and provider is None and not shutil.which(args.az):
        print("az-lint: skipped (the az CLI is not on PATH; CI runs this check)", file=sys.stderr)
        return EXIT_OK

    root = args.root.resolve()
    invocations = extract_all(root, args.paths or None)
    if not invocations:
        print("check_az_commands: nothing extracted - misconfigured root?", file=sys.stderr)
        return EXIT_ENV
    unresolved = unresolved_invocations(invocations)
    if unresolved:
        print(
            f"note: {len(unresolved)} Python az call(s) have no literal command path and cannot "
            "be validated: " + ", ".join(f"{i.file}:{i.line}" for i in unresolved),
            file=sys.stderr,
        )
    if args.list:
        for inv in invocations:
            print(f"{inv.file}:{inv.line}: {inv.command_line}")
        print(f"{len(invocations)} az invocations", file=sys.stderr)
        return EXIT_OK

    allow_file = root / args.allowlist
    allow_text = allow_file.read_text(encoding="utf-8") if allow_file.is_file() else ""
    try:
        findings = run_lint(
            invocations,
            provider or make_az_provider(args.az),
            allow_text,
            skip_missing_extensions=args.skip_missing_extensions,
            jobs=args.jobs,
            only_paths=args.paths or None,
        )
    except EnvError as exc:
        print(f"check_az_commands: environment error: {exc}", file=sys.stderr)
        return EXIT_ENV

    failures = [f for f in findings if is_failure(f)]
    if args.json:
        print(json.dumps([asdict(f) for f in findings], indent=2))
    else:
        _print_findings(findings)
        allowed = sum(1 for f in findings if f.allowlisted)
        skipped = sum(1 for f in findings if f.kind == "skipped-extension")
        print(
            f"checked {len(invocations)} az invocations: {len(failures)} finding(s), "
            f"{allowed} allowlisted, {skipped} skipped",
            file=sys.stderr,
        )
    return EXIT_FINDINGS if failures else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
