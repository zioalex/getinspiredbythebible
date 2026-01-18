# Virtual Environment Guide

## Why Virtual Environments?

Using a virtual environment is **essential** for Python development:

✅ **Isolation**: Dependencies are isolated from system Python
✅ **Reproducibility**: Exact package versions for all developers
✅ **No Conflicts**: Different projects can use different package versions
✅ **Clean System**: Keeps your system Python installation pristine
✅ **Easy Cleanup**: Delete `.venv` folder to remove everything

## Quick Start

The Makefile automatically creates and uses a virtual environment:

```bash
# Setup everything (creates .venv automatically)
make setup-dev

# Or just create the virtual environment
make venv
```

## Manual Virtual Environment Usage

### Activate

```bash
# Linux/macOS
source .venv/bin/activate

# Windows (Git Bash)
source .venv/Scripts/activate

# Windows (PowerShell)
.venv\Scripts\Activate.ps1
```

When activated, you'll see `(.venv)` in your prompt:

```bash
(.venv) user@machine:~/project$
```

### Deactivate

```bash
deactivate
```

### Verify Activation

```bash
# Should point to .venv/bin/python
which python

# Should show virtual environment path
echo $VIRTUAL_ENV
```

## Using with Makefile (Recommended)

The Makefile handles the virtual environment automatically:

```bash
# No need to activate! These commands use .venv automatically:
make format        # Uses .venv/bin/python
make lint          # Uses .venv/bin/python
make test          # Uses .venv/bin/python
make check-all     # Uses .venv/bin/python
```

**How it works**: The Makefile defines:

```makefile
VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
```

All commands use `$(PYTHON)` which points to `.venv/bin/python`.

## Using with VS Code

VS Code automatically detects the virtual environment:

1. **Open project in VS Code**
2. **Select Python interpreter**:
   - Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on macOS)
   - Type "Python: Select Interpreter"
   - Choose `.venv/bin/python`

3. **Verify** - Bottom left of VS Code shows: `Python 3.12.x ('.venv': venv)`

VS Code will now:

- Use the correct Python interpreter
- Show installed packages
- Run tests in the virtual environment
- Enable IntelliSense for installed packages

## Installing Packages

### Using Makefile (Recommended)

```bash
# Installs all dependencies into .venv
make setup-dev
```

### Manual Installation

```bash
# Activate first
source .venv/bin/activate

# Install from requirements
pip install -r api/requirements.txt

# Install development tools
pip install ruff black mypy pytest

# Install individual package
pip install httpx
```

## Checking Installed Packages

```bash
# Using Makefile (works without activation)
.venv/bin/pip list

# Or activate first
source .venv/bin/activate
pip list
pip freeze  # Show versions
```

## Updating Dependencies

```bash
# Activate environment
source .venv/bin/activate

# Update all packages
pip install --upgrade -r api/requirements.txt

# Update individual package
pip install --upgrade httpx

# Save exact versions
pip freeze > api/requirements.txt
```

## Recreating Virtual Environment

If your virtual environment gets corrupted:

```bash
# Clean everything
make clean-all

# Recreate
make setup-dev
```

Or manually:

```bash
# Remove old environment
rm -rf .venv

# Create new one
python3 -m venv .venv

# Install everything
source .venv/bin/activate
pip install -r api/requirements.txt
```

## Troubleshooting

### "python: command not found"

```bash
# Try python3 instead
python3 -m venv .venv
```

### "No module named 'venv'"

```bash
# Install venv module (Ubuntu/Debian)
sudo apt-get install python3-venv

# Or use virtualenv
pip install virtualenv
virtualenv .venv
```

### "Permission denied"

```bash
# Don't use sudo! Virtual environments should be user-owned
# If .venv is owned by root, remove and recreate:
rm -rf .venv
python3 -m venv .venv
```

### Pre-commit hooks not working

```bash
# Reinstall hooks in virtual environment
source .venv/bin/activate
pip install pre-commit
pre-commit install
```

### IDE doesn't recognize packages

```bash
# In VS Code:
# 1. Reload window (Ctrl+Shift+P → "Reload Window")
# 2. Select interpreter (Ctrl+Shift+P → "Python: Select Interpreter" → .venv)
```

## Workflow Examples

### Standard Development Workflow

```bash
# One-time setup
make setup-dev

# Daily work (no activation needed!)
make format
git add .
git commit -m "Add feature"
make test
git push
```

### If You Prefer Manual Activation

```bash
# Activate once per terminal session
source .venv/bin/activate

# Now use normal commands
python -m pytest
black .
ruff check .

# Deactivate when done
deactivate
```

### Running Scripts

```bash
# Using Makefile (no activation needed)
.venv/bin/python scripts/load_bible.py

# Or activate first
source .venv/bin/activate
python scripts/load_bible.py
```

## Best Practices

1. ✅ **Never commit `.venv/`** (already in `.gitignore`)
2. ✅ **One virtual environment per project**
3. ✅ **Use `make setup-dev`** for consistency
4. ✅ **Pin exact versions** in `requirements.txt`
5. ✅ **Document Python version** (we use Python 3.12)
6. ✅ **Use Makefile commands** (handles venv automatically)
7. ✅ **Recreate if corrupted** (`make clean-all && make setup-dev`)

## Don't

1. ❌ Don't use `sudo pip install` (defeats the purpose!)
2. ❌ Don't install packages globally
3. ❌ Don't commit the `.venv/` directory
4. ❌ Don't mix conda and venv in same project
5. ❌ Don't modify `.venv/` contents directly

## Virtual Environment vs Docker

**Virtual Environment** (for development):

- ✅ Fast (no container overhead)
- ✅ IDE integration works perfectly
- ✅ Easy debugging
- ✅ Direct file access

**Docker** (for production/CI):

- ✅ Includes system dependencies
- ✅ Exact OS environment
- ✅ Database, Redis, etc.
- ✅ Production-like

**Use both**:

- Development: `.venv` for Python, Docker for services (postgres, ollama)
- CI/CD: Docker for everything
- Production: Docker containers

## Summary

The project now uses `.venv` for all Python development:

```bash
# Setup once
make setup-dev

# Daily workflow (automatic venv usage)
make format
make lint
make test
make check-all

# Manual scripts (if needed)
.venv/bin/python scripts/my_script.py

# Or activate for longer sessions
source .venv/bin/activate
```

**Result**: Clean system Python, reproducible environment, happy developers! 🎉

---

See also:

- [PRE_COMMIT_SETUP.md](PRE_COMMIT_SETUP.md) - Pre-commit hooks guide
- [TESTING.md](TESTING.md) - Testing guide
- [SHIFT_LEFT.md](SHIFT_LEFT.md) - Quality gates strategy
