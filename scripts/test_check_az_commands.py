"""Tests for scripts/check_az_commands.py (BITB-374). No azure-cli needed: help text is canned."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_az_commands as lint  # noqa: E402

SHOW_USAGE_HELP = """
Command
    az acr show-usage : Get the storage usage for an Azure Container Registry.

Arguments
    --name -n   [Required] : The name of the container registry. It should be specified in lower
                             case. You can configure the default registry name using `az configure
                             --defaults acr=<registry name>`.
    --resource-group -g    : Name of resource group. You can configure the default group using `az
                             configure --defaults group=<name>`.

Global Policy Arguments
    --acquire-policy-token : Acquiring an Azure Policy token automatically for this resource
                             operation.

Global Arguments
    --debug                : Increase logging verbosity to show all debug logs.
    --help -h              : Show this help message and exit.
    --only-show-errors     : Only show errors, suppressing warnings.
    --output -o            : Output format.  Allowed values: json, jsonc, none, table, tsv, yaml,
                             yamlc.  Default: json.
    --query                : JMESPath query string.
    --subscription         : Name or ID of subscription.
    --verbose              : Increase logging verbosity.

Examples
    Get the storage usage for an Azure Container Registry.
        az acr show-usage -n myregistry
"""

ACR_GROUP_HELP = """
Group
    az acr : Manage private registries with Azure Container Registries.

Subgroups:
    agentpool          [Preview] : Manage private Tasks agent pools.
    artifact-streaming [Preview] : Manage artifact streaming for any repositories or supported
                                   images in an ACR.
    repository                   : Manage repositories (image names) for Azure Container Registries.

Commands:
    login                        : Log in to an Azure Container Registry through the Docker CLI.
    show-usage                   : Get the storage usage for an Azure Container Registry.
"""

REPO_SHOW_TAGS_HELP = """
Command
    az acr repository show-tags : Show tags for a repository in an Azure Container Registry.

Arguments
    --name -n   [Required] : The name of the container registry.
    --repository [Required] : The repository to list tags for.
    --orderby              : Order the items in the results.

Global Arguments
    --help -h              : Show this help message and exit.
    --output -o            : Output format.
"""

MISSPELLED = (
    "ERROR: 'foo' is misspelled or not recognized by the system.\n\nhttps://aka.ms/cli_ref\n"
)

HELPS: dict[tuple[str, ...], str] = {
    ("acr",): ACR_GROUP_HELP,
    ("acr", "show-usage"): SHOW_USAGE_HELP,
    ("acr", "repository", "show-tags"): REPO_SHOW_TAGS_HELP,
}


def provider(path: tuple[str, ...]) -> lint.HelpText:
    """Canned ``az <path> --help``: anything not in HELPS is 'misspelled', like the real CLI."""
    if path in HELPS:
        return lint.HelpText(0, HELPS[path])
    return lint.HelpText(2, MISSPELLED)


def invocations(text: str, file: str = "x.sh") -> list[lint.Invocation]:
    return lint.extract_from_shell(text, file)


def lines_of(text: str) -> list[str]:
    return [inv.command_line for inv in invocations(text)]


def findings_for(text: str, allowlist: str = "", **kwargs: object) -> list[lint.Finding]:
    return lint.run_lint(invocations(text), provider, allowlist, **kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Extraction: shell
# ---------------------------------------------------------------------------
def test_plain_command_and_line_number() -> None:
    inv = invocations("echo hi\n\naz acr login --name foo\n")
    assert [(i.line, i.command_line) for i in inv] == [(3, "az acr login --name foo")]


def test_backslash_continuation_is_one_invocation() -> None:
    text = "az acr show-usage \\\n  --name foo \\\n  -o table\n"
    assert lines_of(text) == ["az acr show-usage --name foo -o table"]


def test_nested_command_substitution_in_assignment() -> None:
    text = 'ws=$(az monitor workspace show --name "$(az monitor list -g rg)")\n'
    assert sorted(lines_of(text)) == [
        "az monitor list -g rg",
        "az monitor workspace show --name $SUBST",
    ]


def test_backtick_substitution() -> None:
    assert lines_of("x=`az account show -o tsv`\n") == ["az account show -o tsv"]


def test_pipes_logical_operators_and_semicolons() -> None:
    text = "az a b | jq . && az c d || true; az e f\naz g h | az i j\n"
    assert lines_of(text) == ["az a b", "az c d", "az e f", "az g h", "az i j"]


def test_or_true_does_not_leak_into_args() -> None:
    (inv,) = invocations("az acr show-usage --name x || true\n")
    assert [w.text for w in inv.args] == ["acr", "show-usage", "--name", "x"]


def test_flag_equals_value() -> None:
    (inv,) = invocations("az acr show-usage --name=foo --output=table\n")
    assert [w.text for w in inv.args][2:] == ["--name=foo", "--output=table"]


def test_quoted_hash_and_pipe_are_not_comment_or_separator() -> None:
    text = (
        "az acr repository show-tags --name x --query \"[?name=='a#b' | [0]]\" -o tsv # trailing\n"
    )
    (inv,) = invocations(text)
    words = [w.text for w in inv.args]
    assert "[?name=='a#b' | [0]]" in words
    assert words[-1] == "tsv"  # the trailing comment is dropped


def test_comment_lines_are_skipped() -> None:
    assert lines_of("# az acr show-usage --registry x\n  # az login\n") == []


def test_heredoc_body_is_ignored() -> None:
    text = "cat <<'EOF'\naz acr show-usage --registry x\nEOF\naz acr login --name y\n"
    inv = invocations(text)
    assert [(i.line, i.command_line) for i in inv] == [(4, "az acr login --name y")]


def test_dash_heredoc_with_indented_terminator() -> None:
    text = "cat <<-EOF\n\taz login\n\tEOF\naz account show\n"
    assert lines_of(text) == ["az account show"]


def test_az_in_prose_echo_and_quotes_is_not_a_command() -> None:
    text = (
        'echo "run az acr show-usage"\n'
        "echo 'then az login'\n"
        "printf '%s' \"az account show\"\n"
        "grep -q az file.txt\n"
        "xargs az foo\n"
    )
    assert lines_of(text) == []


def test_az_inside_substitution_in_echo_counts() -> None:
    assert lines_of('echo "tenant: $(az account show --query tenantId -o tsv)"\n') == [
        "az account show --query tenantId -o tsv"
    ]


@pytest.mark.parametrize(
    "prefix",
    ["if ", "if ! ", "then ", "do ", "while ! ", "time ", "timeout 30 ", "env FOO=1 ", "FOO=bar ",
     "sudo ", "! ", "{ ", "elif "],
)  # fmt: skip
def test_command_position_prefixes(prefix: str) -> None:
    assert lines_of(f"{prefix}az account show\n") == ["az account show"]


def test_timeout_with_flags() -> None:
    assert lines_of("timeout -k 5 60 az account show\n") == ["az account show"]


def test_redirections_are_dropped() -> None:
    (inv,) = invocations("az account show -o none 2>&1 >/dev/null\n")
    assert [w.text for w in inv.args] == ["account", "show", "-o", "none"]
    (inv,) = invocations("az account show > out.txt --output tsv\n")
    assert [w.text for w in inv.args] == ["account", "show", "--output", "tsv"]


def test_variable_expansions_as_values() -> None:
    (inv,) = invocations('az acr show-usage --name "$ACR" --subscription ${SUB:-x}\n')
    assert [w.text for w in inv.args][2:] == ["--name", "$ACR", "--subscription", "${SUB:-x}"]


def test_github_expression_in_run_text() -> None:
    (inv,) = invocations("az acr login --name ${{ secrets.ACR_NAME }}\n")
    assert [w.text for w in inv.args][-1] == "${GHA}"


def test_case_pattern_does_not_hide_command() -> None:
    text = 'case "$x" in\n  a) az account show ;;\n  b) az login ;;\nesac\n'
    assert lines_of(text) == ["az account show", "az login"]


def test_multiline_quoted_value_keeps_line_numbers() -> None:
    text = 'q="line one\nline two"\naz account show\n'
    (inv,) = invocations(text)
    assert inv.line == 3


# ---------------------------------------------------------------------------
# Extraction: Makefile, YAML, Python
# ---------------------------------------------------------------------------
MAKEFILE = """\
NAME := foo
demo: ## demo
\t@az acr login --name $(ACR_NAME)
\t-az containerapp show --name $$APP \\
\t  --query "x" -o tsv
\t@echo "az not a command"
\tTAG=$$(az acr repository show-tags --name $(ACR) --repository r)
other:
\t@echo done
"""


def test_makefile_recipes() -> None:
    inv = lint.extract_from_makefile(MAKEFILE, "Makefile")
    assert [(i.line, i.command_line) for i in inv] == [
        (3, "az acr login --name ${MK_ACR_NAME}"),
        (4, "az containerapp show --name $APP --query x -o tsv"),
        (7, "az acr repository show-tags --name ${MK_ACR} --repository r"),
    ]


WORKFLOW = """\
name: demo
jobs:
  a:
    steps:
      - name: one
        run: az account show -o none
      - name: two
        run: |
          set -e
          az acr show-usage \\
            --name "$ACR" -o table
          echo "az is not run here"
      - name: three
        run: >-
          az login --output none
      - uses: actions/checkout@v7
        with:
          script: az not a step
"""


def test_yaml_run_block_lines() -> None:
    inv = lint.extract_from_yaml(WORKFLOW, "w.yml")
    assert [(i.line, i.command_line.split(" ")[1]) for i in inv] == [
        (6, "account"),
        (10, "acr"),
        (15, "login"),
    ]


def test_yaml_text_fallback_matches_pyyaml(monkeypatch: pytest.MonkeyPatch) -> None:
    with_yaml = lint.extract_from_yaml(WORKFLOW, "w.yml")
    monkeypatch.setattr(lint, "yaml", None)
    without = lint.extract_from_yaml(WORKFLOW, "w.yml")
    assert [(i.line, i.command_line) for i in without] == [
        (i.line, i.command_line) for i in with_yaml
    ]


def test_python_argv_literals() -> None:
    src = (
        "import subprocess\n"
        "def f(rg, extra):\n"
        '    subprocess.run(["az", "resource", "list", "--resource-group", rg, "-o", "json"])\n'
        '    cmd = ("az", "account", "show", *extra)\n'
        '    other = ["not-az", "x"]\n'
        '    prose = "az account show"\n'
    )
    inv = lint.extract_from_python(src, "s.py")
    assert [(i.line, i.command_line) for i in inv] == [
        (3, "az resource list --resource-group $EXPR -o json"),
        (4, "az account show $EXPR"),
    ]


def test_python_syntax_error_is_ignored() -> None:
    assert lint.extract_from_python("def (:\n", "bad.py") == []


def test_discover_and_extract_all(tmp_path: Path) -> None:
    (tmp_path / ".github/workflows").mkdir(parents=True)
    (tmp_path / ".github/workflows/w.yml").write_text(WORKFLOW)
    (tmp_path / ".github/actions/x").mkdir(parents=True)
    (tmp_path / ".github/actions/x/action.yml").write_text(
        "runs:\n  using: composite\n  steps:\n    - run: az account show\n      shell: bash\n"
    )
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/a.sh").write_text("az login\n")
    (tmp_path / "scripts/node_modules").mkdir()
    (tmp_path / "scripts/node_modules/b.sh").write_text("az login\n")
    (tmp_path / "api").mkdir()
    (tmp_path / "api/c.py").write_text('x = ["az", "account", "show"]\n')
    (tmp_path / "Makefile").write_text("t:\n\t@az account show\n")
    files = {i.file for i in lint.extract_all(tmp_path)}
    assert files == {
        ".github/workflows/w.yml",
        ".github/actions/x/action.yml",
        "scripts/a.sh",
        "api/c.py",
        "Makefile",
    }


# ---------------------------------------------------------------------------
# Help parsing and command path
# ---------------------------------------------------------------------------
def test_parse_help_command_collects_aliases_and_globals() -> None:
    parsed = lint.parse_help(lint.HelpText(0, SHOW_USAGE_HELP))
    assert parsed.kind == "command"
    assert parsed.specific == [("--name", "-n"), ("--resource-group", "-g")]
    assert {"--name", "-n", "--resource-group", "-g"} <= parsed.options
    assert {"--acquire-policy-token", "--output", "-o", "--query-examples"} <= parsed.options


def test_parse_help_group_lists_children() -> None:
    parsed = lint.parse_help(lint.HelpText(0, ACR_GROUP_HELP))
    assert parsed.kind == "group"
    assert parsed.children == [
        "agentpool",
        "artifact-streaming",
        "repository",
        "login",
        "show-usage",
    ]


def test_parse_help_unknown_and_extension() -> None:
    assert lint.parse_help(lint.HelpText(2, MISSPELLED)).kind == "unknown"
    ext = lint.parse_help(
        lint.HelpText(
            1, "The command requires the extension foo-bar. Run `az extension add -n foo-bar`."
        )
    )
    assert (ext.kind, ext.extension) == ("extension", "foo-bar")


def test_command_path_stops_at_flags_expansions_and_quotes() -> None:
    def path(text: str) -> list[str]:
        (inv,) = invocations(text)
        return lint.command_path(inv.args)

    assert path("az acr show-usage --name x\n") == ["acr", "show-usage"]
    assert path('az acr "show" x\n') == ["acr"]
    assert path("az acr $SUB show\n") == ["acr"]
    assert path("az config set a=b\n") == ["config", "set"]
    assert path("az rest --method get\n") == ["rest"]
    assert path("az\n") == []


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def test_regression_show_usage_registry_flag_fails() -> None:
    """BITB-374: `az acr show-usage --registry` (the BITB-372 production failure) must be caught."""
    (f,) = findings_for('az acr show-usage --registry "$ACR_NAME" -o table\n')
    assert f.kind == "unknown-flag"
    assert "--registry" in f.message
    assert "--name/-n" in f.message and "--resource-group/-g" in f.message
    assert f.line == 1


def test_regression_show_usage_name_flag_passes() -> None:
    assert findings_for('az acr show-usage --name "$ACR_NAME" -o table\n') == []


def test_short_alias_and_globals_pass() -> None:
    text = (
        "az acr show-usage -n x -g rg -o json --query q --subscription s --verbose --debug "
        "--only-show-errors -h\n"
    )
    assert findings_for(text) == []


def test_unknown_short_flag() -> None:
    (f,) = findings_for("az acr show-usage -n x -z 1\n")
    assert f.kind == "unknown-short-flag" and "-z" in f.message


def test_attached_short_value_is_ok_and_negative_numbers_ignored() -> None:
    assert findings_for("az acr show-usage -nfoo --query -1\n") == []


def test_flag_with_equals_is_checked() -> None:
    (f,) = findings_for("az acr show-usage --registry=x\n")
    assert f.kind == "unknown-flag"
    assert findings_for("az acr show-usage --name=x\n") == []


def test_double_dash_stops_flag_checking() -> None:
    assert findings_for("az acr show-usage --name x -- --registry\n") == []


def test_expansion_flag_names_are_skipped() -> None:
    assert findings_for("az acr show-usage --name x --$FLAG v\n") == []


def test_did_you_mean_hint() -> None:
    (f,) = findings_for("az acr show-usage --resource-grp rg\n")
    assert "Did you mean --resource-group?" in f.message


def test_group_instead_of_command_is_incomplete() -> None:
    (f,) = findings_for("az acr --name x\n")
    assert f.kind == "incomplete-command"
    assert "show-usage" in f.message and "login" in f.message


def test_group_with_help_flag_is_fine() -> None:
    assert findings_for("az acr --help\n") == []
    assert findings_for("az acr -h\n") == []


def test_unknown_subcommand_of_known_group() -> None:
    (f,) = findings_for("az acr show-usages --name x\n")
    assert f.kind == "unknown-command"
    assert "az acr show-usages" in f.message and "login" in f.message


def test_unknown_top_level_command() -> None:
    (f,) = findings_for("az frobnicate now --x\n")
    assert f.kind == "unknown-command" and "az frobnicate" in f.message


def test_positional_after_command_is_not_part_of_the_path() -> None:
    assert findings_for("az acr show-usage thing --name x\n") == []


def test_missing_extension_from_help_text() -> None:
    def prov(path: tuple[str, ...]) -> lint.HelpText:
        return lint.HelpText(
            1, "The command requires the extension widgets. Run `az extension add -n widgets`."
        )

    (f,) = lint.run_lint(invocations("az widgets list\n"), prov)
    assert f.kind == "missing-extension" and "'widgets'" in f.message
    assert "scripts/az-extensions.txt" in f.message


def test_missing_extension_known_prefix_names_the_extension() -> None:
    (f,) = findings_for("az monitor log-analytics query --workspace w\n")
    assert f.kind == "missing-extension" and "'log-analytics'" in f.message
    (g,) = findings_for("az monitor app-insights web-test list\n")
    assert g.kind == "missing-extension" and "'application-insights'" in g.message


def test_skip_missing_extensions_does_not_fail() -> None:
    (f,) = findings_for("az monitor app-insights web-test list\n", skip_missing_extensions=True)
    assert f.kind == "skipped-extension"
    assert not lint.is_failure(f)


def test_incomplete_and_unknown_do_fail() -> None:
    assert all(lint.is_failure(f) for f in findings_for("az acr\naz nope\n"))


def test_acr_run_cmd_content_is_not_linted() -> None:
    def prov(path: tuple[str, ...]) -> lint.HelpText:
        if path == ("acr", "run"):
            return lint.HelpText(
                0,
                "Command\n    az acr run : x\n\nArguments\n    --registry -r [Required] : r\n"
                "    --cmd : c\n\nGlobal Arguments\n    --help -h : h\n",
            )
        return lint.HelpText(2, MISSPELLED)

    text = 'az acr run --registry "$R" --cmd "acr purge --filter x:.* --ago 30d --untagged" /dev/null\n'
    assert lint.run_lint(invocations(text), prov) == []


def test_help_provider_called_once_per_path() -> None:
    calls: list[tuple[str, ...]] = []

    def counting(path: tuple[str, ...]) -> lint.HelpText:
        calls.append(path)
        return provider(path)

    text = "az acr show-usage -n a\naz acr show-usage -n b\naz acr show-usage -n c\n"
    lint.run_lint(invocations(text), counting)
    assert calls == [("acr", "show-usage")]


def test_parallel_prewarm_gives_same_findings() -> None:
    text = "az acr show-usage --registry x\naz acr login\naz nope\n"
    a = findings_for(text)
    b = findings_for(text, jobs=4)
    assert [(f.kind, f.line) for f in a] == [(f.kind, f.line) for f in b]


# ---------------------------------------------------------------------------
# Allowlist
# ---------------------------------------------------------------------------
BAD = 'az acr show-usage --registry "$ACR_NAME" -o table\n'


def test_allowlist_match_suppresses_finding() -> None:
    allow = "x.sh:az acr show-usage --registry  # fixed in #1353\n"
    findings = findings_for(BAD, allow)
    assert [f.allowlisted for f in findings] == ["fixed in #1353"]
    assert not any(lint.is_failure(f) for f in findings)


def test_allowlist_is_per_file() -> None:
    allow = "other.sh:az acr show-usage --registry  # reason\n"
    kinds = sorted(f.kind for f in findings_for(BAD, allow))
    assert kinds == ["stale-allowlist", "unknown-flag"]
    assert all(lint.is_failure(f) for f in findings_for(BAD, allow))


def test_allowlist_missing_reason_is_a_finding() -> None:
    entries, problems = lint.parse_allowlist("x.sh:az acr show-usage --registry\n")
    assert entries == []
    assert [p.kind for p in problems] == ["allowlist-no-reason"]
    findings = findings_for(BAD, "x.sh:az acr show-usage --registry\n")
    assert any(f.kind == "allowlist-no-reason" for f in findings)
    assert any(lint.is_failure(f) for f in findings)


def test_allowlist_empty_reason_is_a_finding() -> None:
    _, problems = lint.parse_allowlist("x.sh:az acr show-usage --registry  #   \n")
    assert [p.kind for p in problems] == ["allowlist-no-reason"]


def test_allowlist_malformed_entry() -> None:
    _, problems = lint.parse_allowlist("no-colon-here  # reason\n")
    assert [p.kind for p in problems] == ["allowlist-no-reason"]


def test_stale_allowlist_entry_fails() -> None:
    """Once #1353 fixes acr-purge.yml the entry matches nothing and must be deleted."""
    allow = "x.sh:az acr show-usage --registry  # fixed in #1353\n"
    findings = findings_for('az acr show-usage --name "$ACR_NAME" -o table\n', allow)
    assert [f.kind for f in findings] == ["stale-allowlist"]
    assert lint.is_failure(findings[0])
    assert findings[0].file == lint.ALLOWLIST_PATH


def test_allowlist_comments_and_blank_lines_ignored() -> None:
    assert lint.parse_allowlist("# header\n\n   \n") == ([], [])


def test_allowlist_pattern_may_contain_colon_and_hash_reason_split() -> None:
    entries, problems = lint.parse_allowlist("a/b.yml:az rest --uri https://x/y  # why: because\n")
    assert problems == []
    assert (entries[0].path, entries[0].pattern, entries[0].reason) == (
        "a/b.yml",
        "az rest --uri https://x/y",
        "why: because",
    )


def test_skipped_extension_still_counts_as_matched_for_allowlist() -> None:
    allow = "x.sh:az monitor log-analytics query  # ext not installed locally\n"
    findings = findings_for(
        "az monitor log-analytics query --workspace w\n", allow, skip_missing_extensions=True
    )
    assert [f.kind for f in findings] == ["skipped-extension"]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _repo(tmp_path: Path, script: str, allowlist: str | None = None) -> Path:
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/t.sh").write_text(script)
    if allowlist is not None:
        (tmp_path / "scripts/az-lint-allowlist.txt").write_text(allowlist)
    return tmp_path


def test_main_exit_codes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = _repo(tmp_path, BAD)
    assert lint.main(["--root", str(root)], provider=provider) == lint.EXIT_FINDINGS
    out = capsys.readouterr().out
    assert "scripts/t.sh:1: [unknown-flag]" in out

    (root / "scripts/t.sh").write_text('az acr show-usage --name "$A"\n')
    assert lint.main(["--root", str(root)], provider=provider) == lint.EXIT_OK


def test_main_list_mode_needs_no_az(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = _repo(tmp_path, "az login\naz acr login --name x\n")
    assert lint.main(["--root", str(root), "--list"]) == lint.EXIT_OK
    out = capsys.readouterr().out
    assert "scripts/t.sh:1: az login" in out and "scripts/t.sh:2: az acr login --name x" in out


def test_main_json_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = _repo(tmp_path, BAD)
    assert lint.main(["--root", str(root), "--json"], provider=provider) == lint.EXIT_FINDINGS
    data = json.loads(capsys.readouterr().out)
    assert data[0]["kind"] == "unknown-flag" and data[0]["file"] == "scripts/t.sh"


def test_main_allowlist_and_stale(tmp_path: Path) -> None:
    root = _repo(tmp_path, BAD, "scripts/t.sh:az acr show-usage --registry  # fixed in #1353\n")
    assert lint.main(["--root", str(root)], provider=provider) == lint.EXIT_OK
    (root / "scripts/t.sh").write_text('az acr show-usage --name "$A"\n')
    assert lint.main(["--root", str(root)], provider=provider) == lint.EXIT_FINDINGS


def test_main_no_az_binary_is_environment_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _repo(tmp_path, BAD)
    code = lint.main(["--root", str(root), "--az", "/nonexistent/az-binary"])
    assert code == lint.EXIT_ENV
    assert "not found" in capsys.readouterr().err


def test_main_if_az_available_skips_when_az_is_missing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _repo(tmp_path, BAD)
    argv = ["--root", str(root), "--az", "/nonexistent/az-binary", "--if-az-available"]
    assert lint.main(argv) == lint.EXIT_OK
    assert "skipped" in capsys.readouterr().err


def test_main_path_filter_only_judges_given_files(tmp_path: Path) -> None:
    root = _repo(tmp_path, BAD, "scripts/other.sh:az x y  # reason\n")
    (root / "scripts/ok.sh").write_text("az acr show-usage --name x\n")
    # the stale `other.sh` entry is not judged when only some files are linted
    assert lint.main(["--root", str(root), "scripts/t.sh"], provider=provider) == lint.EXIT_FINDINGS
    assert lint.main(["--root", str(root), "scripts/ok.sh"], provider=provider) == lint.EXIT_OK
    (root / "scripts/t.sh").write_text('az acr show-usage --name "$A"\n')
    assert lint.main(["--root", str(root), "scripts/t.sh"], provider=provider) == lint.EXIT_OK


def test_make_az_provider_env_is_hardened(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def fake_run(cmd: list[str], **kw: object) -> object:
        seen["cmd"], seen["env"] = cmd, kw["env"]

        class R:
            returncode = 0
            stdout = "Command\n"
            stderr = ""

        return R()

    monkeypatch.setattr(lint.subprocess, "run", fake_run)
    out = lint.make_az_provider("az-bin", timeout=5)(("acr", "show-usage"))
    assert seen["cmd"] == ["az-bin", "acr", "show-usage", "--help"]
    env = seen["env"]
    assert env["AZURE_EXTENSION_USE_DYNAMIC_INSTALL"] == "no"  # type: ignore[index]
    assert env["AZURE_CORE_ONLY_SHOW_ERRORS"] == "true"  # type: ignore[index]
    assert env["AZURE_CORE_COLLECT_TELEMETRY"] == "no"  # type: ignore[index]
    assert out.returncode == 0


def test_repo_extensions_file_is_pinned() -> None:
    path = Path(__file__).resolve().parent / "az-extensions.txt"
    lines = [ln.strip() for ln in path.read_text().splitlines()]
    pins = [ln for ln in lines if ln and not ln.startswith("#")]
    assert pins and all("==" in p for p in pins)
    names = {p.split("==")[0] for p in pins}
    assert set(lint.KNOWN_EXTENSION_PREFIXES.values()) & names  # at least one mapped ext is pinned


def test_repo_allowlist_entries_have_reasons() -> None:
    path = Path(__file__).resolve().parent / "az-lint-allowlist.txt"
    _, problems = lint.parse_allowlist(path.read_text())
    assert problems == []


def test_main_zero_invocations_is_environment_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert lint.main(["--root", str(tmp_path)], provider=provider) == lint.EXIT_ENV
    assert "nothing extracted" in capsys.readouterr().err


def test_partial_run_reports_real_allowlist_line_numbers(tmp_path: Path) -> None:
    allow = "# c\nscripts/other.sh:az x y  # r\nscripts/t.sh:az nothing  # stale one\n"
    root = _repo(tmp_path, 'az acr show-usage --name "$A"\n', allow)
    findings = lint.run_lint(
        lint.extract_all(root, ["scripts/t.sh"]),
        provider,
        allow,
        only_paths=["scripts/t.sh"],
    )
    stale = [f for f in findings if f.kind == "stale-allowlist"]
    assert [f.line for f in stale] == [3]


WRAPPER_SRC = """\
import subprocess

def _az(args):
    return subprocess.run(["az", *args])

def _az2(cmd, extra=None):
    return subprocess.run(["az"] + cmd)

class C:
    def go(self, argv):
        return subprocess.run(("az", *argv))

def use(x):
    _az(["resource", "list", "-g", x])
    _az2(cmd=["account", "show"])
    _az(some_variable)
    C().go(["acr", "login"])
"""


def test_python_wrapper_call_sites_become_invocations() -> None:
    inv = lint.extract_from_python(WRAPPER_SRC, "w.py")
    assert [(i.line, i.command_line) for i in inv] == [
        (14, "az resource list -g $EXPR"),
        (15, "az account show"),
        (17, "az acr login"),
    ]


def test_python_wrapper_internal_list_is_not_unresolved() -> None:
    inv = lint.extract_from_python(WRAPPER_SRC, "w.py")
    assert lint.unresolved_invocations(inv) == []


def test_unresolved_python_az_is_reported_not_failed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/u.py").write_text("import subprocess\nsubprocess.run(['az', *argv])\n")
    (tmp_path / "scripts/t.sh").write_text('az acr show-usage --name "$A"\n')
    assert lint.main(["--root", str(tmp_path)], provider=provider) == lint.EXIT_OK
    assert "scripts/u.py:2" in capsys.readouterr().err


TF_SRC = """\
resource "null_resource" "x" {
  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    command     = <<-EOT
      set -euo pipefail
      APP="${azurerm_container_app.frontend.name}"
      echo "az not a command: $${HOME}"
      az acr show-usage --registry "${var.acr}" -o table
    EOT
  }
  provisioner "local-exec" {
    command = "az acr login --name ${var.acr}"
  }
  provisioner "local-exec" {
    command = "echo \\"az acr bogus\\" && az account show"
  }
}
"""


def test_terraform_local_exec_commands() -> None:
    inv = lint.extract_from_terraform(TF_SRC, "m.tf")
    assert [(i.line, i.command_line) for i in inv] == [
        (8, "az acr show-usage --registry ${var.acr} -o table"),
        (12, "az acr login --name ${var.acr}"),
        (15, "az account show"),
    ]


def test_terraform_findings_flow_through_the_linter(tmp_path: Path) -> None:
    (tmp_path / "deployment").mkdir()
    (tmp_path / "deployment/m.tf").write_text(TF_SRC)
    findings = lint.run_lint(lint.extract_all(tmp_path), provider)
    bad = [f for f in findings if lint.is_failure(f)]
    assert ("deployment/m.tf", 8, "unknown-flag") in [(f.file, f.line, f.kind) for f in bad]
