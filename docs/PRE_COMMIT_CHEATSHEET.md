# Pre-Commit Quick Reference Card

## 🚀 First Time Setup (2 minutes)

```bash
# Option 1: Automated (Recommended)
./scripts/setup-pre-commit.sh

# Option 2: Using Makefile
make setup-dev

# Option 3: Manual
pip install pre-commit
pre-commit install
```

## ⚡ Daily Workflow

### Standard Commit

```bash
# 1. Make changes
vim api/main.py

# 2. Stage changes
git add .

# 3. Commit (hooks run automatically)
git commit -m "Add new feature"
# ↓ Pre-commit runs (2-10 seconds)
# ↓ Auto-fixes code
# ↓ Either passes ✅ or shows issues ❌

# 4. If files were modified, stage and commit again
git add .
git commit -m "Add new feature"
```

### Recommended Workflow (Faster)

```bash
# 1. Make changes
vim api/main.py

# 2. Auto-format everything first
make format

# 3. Commit (passes immediately)
git add .
git commit -m "Add new feature"  # ✅ Passes!
```

## 📋 Common Commands

| Command | What It Does | When to Use |
|---------|--------------|-------------|
| `make format` | Auto-fix all formatting | Before committing |
| `make lint` | Check code quality | Check for issues |
| `make type-check` | Validate types | Fix type errors |
| `make security` | Security scan | Before pushing |
| `make test` | Run all tests | Verify functionality |
| `make check-all` | Run everything | Before pushing |
| `make pre-commit` | Run hooks manually | Test on all files |
| `make help` | Show all commands | Learn available commands |

## 🛠️ Pre-Commit Commands

```bash
# Run on staged files only
pre-commit run

# Run on all files
pre-commit run --all-files

# Run specific hook
pre-commit run black --all-files
pre-commit run ruff --all-files
pre-commit run eslint --all-files

# Skip hooks (emergency only!)
git commit --no-verify -m "Emergency fix"

# Update to latest versions
pre-commit autoupdate
```

## 🐛 Troubleshooting

### Hooks Run Forever

```bash
# Kill and reinstall
pre-commit clean
pre-commit install
```

### "Files were modified by this hook"

```bash
# Normal! Just stage and commit again
git add .
git commit -m "Same message"
```

### Need to Skip Specific Hook

```bash
# Skip mypy only
SKIP=mypy git commit -m "WIP: type errors"

# Skip multiple hooks
SKIP=mypy,bandit,eslint git commit -m "WIP"
```

### False Positive Secret Detection

```bash
# Update baseline to ignore it
make update-baseline
```

## 🎯 What Gets Checked

### Python (2-5 seconds)

- ✅ Black (auto-format)
- ✅ isort (organize imports)
- ✅ Ruff (lint)
- ✅ MyPy (type check)
- ✅ Bandit (security)

### Frontend (3-8 seconds)

- ✅ Prettier (auto-format)
- ✅ ESLint (lint)

### General (1-2 seconds)

- ✅ YAML/JSON syntax
- ✅ Trailing whitespace
- ✅ Large files
- ✅ Secrets detection
- ✅ Merge conflicts

## 💡 Pro Tips

### Tip #1: Format Before Commit

```bash
make format && git add . && git commit -m "Feature"
```

### Tip #2: Alias Common Commands

```bash
# Add to ~/.bashrc or ~/.zshrc
alias gcf='make format && git add . && git commit'
alias gcheck='make check-all'

# Usage
gcf -m "Add feature"  # Format + commit
gcheck                # Run all checks
```

### Tip #3: IDE Integration

**VS Code**: Install extensions for real-time checking

- Python: Black, Ruff
- TypeScript: ESLint, Prettier

**Settings.json**:

```json
{
  "editor.formatOnSave": true,
  "[python]": {
    "editor.defaultFormatter": "ms-python.black-formatter"
  }
}
```

### Tip #4: Pre-Push Checklist

```bash
make check-all  # Runs everything locally
git push        # Confident it will pass CI
```

## 📊 Performance

| Stage | Time | What Runs |
|-------|------|-----------|
| IDE | 0 sec | Real-time checks |
| Pre-commit | 2-10 sec | All quality checks |
| CI | 3-5 min | Tests + multi-env |

**Save**: ~5 min per commit by catching issues locally! ⚡

## 🆘 Emergency Bypass

Only use in true emergencies (production down, critical hotfix):

```bash
# Skip ALL hooks
git commit --no-verify -m "HOTFIX: critical bug"

# Then fix properly later
make check-all
git commit -m "Fix quality issues from hotfix"
```

## 📚 Documentation

- [PRE_COMMIT_SETUP.md](./PRE_COMMIT_SETUP.md) - Full setup guide
- [SHIFT_LEFT.md](./SHIFT_LEFT.md) - Benefits & strategy
- [TESTING.md](./TESTING.md) - CI/CD testing

## ✅ Best Practices

1. ✅ Run `make format` before committing
2. ✅ Let hooks fail and fix issues
3. ✅ Don't skip hooks frequently
4. ✅ Update hooks monthly: `pre-commit autoupdate`
5. ✅ Run `make check-all` before pushing

## ❌ Anti-Patterns

1. ❌ Constantly using `--no-verify`
2. ❌ Skipping type checking to "fix later"
3. ❌ Committing without running tests
4. ❌ Ignoring security warnings
5. ❌ Not installing hooks as new dev

---

**Questions?** See full docs in `docs/PRE_COMMIT_SETUP.md`

**Setup?** Run: `./scripts/setup-pre-commit.sh`

**Help?** Run: `make help`
