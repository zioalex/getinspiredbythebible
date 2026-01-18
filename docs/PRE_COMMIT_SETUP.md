# Pre-Commit Hooks Setup Guide

This guide explains how to use pre-commit hooks to shift-left quality checks in the development workflow.

## What is "Shift Left"?

**Shift Left** means moving quality checks earlier in the development cycle:

```text
Traditional Flow:
Code → Commit → Push → CI Fails ❌ → Fix → Repeat

Shift Left Flow:
Code → Pre-commit Checks → ✓ Pass → Commit → Push → CI Passes ✅
```

Benefits:

- ⚡ **Faster feedback** - Catch issues in seconds, not minutes
- 💰 **Save CI resources** - Don't waste GitHub Actions minutes on trivial issues
- 🎯 **Better quality** - Enforce standards before code leaves your machine
- 🚀 **Faster reviews** - Reviewers see clean, formatted code

## Quick Start

### 1. Install Pre-Commit

```bash
# Using pip
pip install pre-commit

# Or using Homebrew (macOS)
brew install pre-commit
```

### 2. Install Hooks

```bash
# From project root
cd /home/asurace/github/getinspiredbythebible

# Install the git hooks
pre-commit install

# Also install commit-msg hook (optional)
pre-commit install --hook-type commit-msg
```

### 3. Done! Hooks Run Automatically

Now every `git commit` will run checks automatically:

```bash
git add .
git commit -m "Add new feature"

# Pre-commit hooks run here automatically!
# If any fail, commit is blocked until fixed
```

## Using the Makefile (Recommended)

We provide a Makefile for common tasks:

```bash
# Setup everything (hooks + dependencies)
make setup-dev

# Run pre-commit manually on all files
make pre-commit

# Auto-format all code
make format

# Run all linters
make lint

# Run type checkers
make type-check

# Run security checks
make security

# Run all tests
make test

# Run ALL checks (before pushing)
make check-all

# Clean build artifacts
make clean

# See all available commands
make help
```

## What Gets Checked?

### 🐍 Python (Backend API)

| Check | Tool | What it Does | Auto-Fix |
|-------|------|--------------|----------|
| **Code Style** | Black | Formats code to PEP 8 standard | ✅ Yes |
| **Import Sorting** | isort | Organizes imports alphabetically | ✅ Yes |
| **Linting** | Ruff | Catches bugs, style issues, complexity | ⚠️ Partial |
| **Type Checking** | MyPy | Validates type hints | ❌ No |
| **Security** | Bandit | Finds security vulnerabilities | ❌ No |

### 🎨 Frontend (Next.js)

| Check | Tool | What it Does | Auto-Fix |
|-------|------|--------------|----------|
| **Code Style** | Prettier | Formats JS/TS/CSS/JSON/MD | ✅ Yes |
| **Linting** | ESLint | Catches bugs and enforces patterns | ⚠️ Partial |
| **Type Checking** | TypeScript | Validates types (separate step) | ❌ No |

### 📦 General

| Check | Tool | What it Does |
|-------|------|--------------|
| **Trailing Whitespace** | pre-commit-hooks | Removes trailing spaces |
| **File Endings** | pre-commit-hooks | Adds newline at end of files |
| **YAML Syntax** | yamllint | Validates YAML files |
| **JSON Syntax** | pre-commit-hooks | Validates JSON files |
| **Large Files** | pre-commit-hooks | Blocks files >1MB |
| **Merge Conflicts** | pre-commit-hooks | Detects unresolved conflicts |
| **Private Keys** | pre-commit-hooks | Blocks committed secrets |
| **Secrets** | detect-secrets | AI-powered secret detection |
| **Dockerfiles** | hadolint | Lints Dockerfiles |
| **Shell Scripts** | shellcheck | Lints bash scripts |
| **Markdown** | markdownlint | Lints markdown files |

## Manual Usage

### Run on Staged Files Only

```bash
pre-commit run
```

### Run on All Files

```bash
pre-commit run --all-files
```

### Run Specific Hook

```bash
# Just run Black
pre-commit run black --all-files

# Just run Ruff
pre-commit run ruff --all-files

# Just run ESLint
pre-commit run eslint --all-files
```

### Skip Hooks (Emergency Only)

```bash
# Skip ALL hooks (not recommended!)
git commit --no-verify -m "Emergency fix"

# Skip specific hook
SKIP=mypy git commit -m "WIP: type errors to fix later"
```

## Auto-Formatting Workflow

### Option 1: Let Pre-Commit Fix It

```bash
git add .
git commit -m "Add feature"
# Hooks run, auto-fix issues
# Commit fails with "files were modified"

git add .  # Stage the auto-fixed files
git commit -m "Add feature"  # Commit again
# ✅ Passes!
```

### Option 2: Format Before Committing

```bash
# Format everything first
make format

# Then commit
git add .
git commit -m "Add feature"
# ✅ Passes immediately!
```

## Common Issues & Solutions

### Hook Installation Failed

```bash
# Update pre-commit
pip install --upgrade pre-commit

# Reinstall hooks
pre-commit uninstall
pre-commit install
```

### Hooks Too Slow

```bash
# Run only on changed files (default)
pre-commit run

# Skip expensive checks during development
SKIP=mypy,eslint git commit -m "WIP"
```

### False Positives in Secret Detection

```bash
# Update baseline to ignore false positives
make update-baseline

# Or manually
detect-secrets scan --baseline .secrets.baseline --update
```

### ESLint Fails to Find Config

```bash
# Install frontend dependencies
cd frontend
npm install
```

### Need to Commit Anyway

```bash
# Only in emergencies!
git commit --no-verify -m "Hotfix: critical bug"
```

## CI Integration

Pre-commit hooks complement (not replace) CI:

- **Pre-Commit**: Fast, local, auto-fix capable
- **CI (GitHub Actions)**: Comprehensive, multiple environments, integration tests

The CI workflow ([.github/workflows/test_update.yml](../.github/workflows/test_update.yml)) runs the same checks plus:

- Tests on multiple Node.js versions
- Docker integration tests
- Dependency vulnerability scans
- Full test suites

## Updating Hooks

```bash
# Update to latest versions
pre-commit autoupdate

# Review changes
git diff .pre-commit-config.yaml

# Test
pre-commit run --all-files
```

## Configuration Files

- [.pre-commit-config.yaml](../.pre-commit-config.yaml) - Main hook configuration
- [api/pyproject.toml](../api/pyproject.toml) - Python tool settings
- [api/.flake8](../api/.flake8) - Flake8 rules
- [frontend/.prettierrc](../frontend/.prettierrc) - Prettier formatting
- [.markdownlint.json](../.markdownlint.json) - Markdown rules
- [.secrets.baseline](../.secrets.baseline) - Known secrets to ignore

## Best Practices

### ✅ Do

- Install hooks immediately when joining project
- Run `make format` before committing
- Fix issues locally, don't push broken code
- Use `make check-all` before pushing
- Update hooks regularly with `pre-commit autoupdate`

### ❌ Don't

- Skip hooks frequently (defeats the purpose)
- Commit with `--no-verify` except emergencies
- Ignore type errors or security warnings
- Push without running checks locally first

## Performance Tips

Pre-commit hooks run in parallel automatically. To speed up:

1. **Cache dependencies**: Already configured in `.pre-commit-config.yaml`
2. **Run only on changed files**: Default behavior
3. **Skip optional checks during development**:

   ```bash
   SKIP=mypy,bandit,hadolint git commit -m "WIP"
   ```

4. **Use `make format` first**: Auto-fixes most issues before commit

## IDE Integration

### VS Code

Install extensions for real-time feedback:

```bash
# Python
code --install-extension ms-python.python
code --install-extension ms-python.black-formatter
code --install-extension charliermarsh.ruff

# TypeScript/React
code --install-extension dbaeumer.vscode-eslint
code --install-extension esbenp.prettier-vscode
```

Add to `.vscode/settings.json`:

```json
{
  "editor.formatOnSave": true,
  "[python]": {
    "editor.defaultFormatter": "ms-python.black-formatter",
    "editor.formatOnSave": true
  },
  "[typescript]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode"
  }
}
```

## Summary

Pre-commit hooks provide:

- ⚡ **Instant feedback** on code quality
- 🤖 **Automatic formatting** for consistent style
- 🔒 **Security scanning** before code leaves your machine
- 💰 **Reduced CI costs** by catching issues early
- 🎯 **Enforced standards** across the team

Install with `make setup-dev` and enjoy faster, cleaner development! 🚀
