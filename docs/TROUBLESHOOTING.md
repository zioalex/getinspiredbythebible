# Common Issues & Solutions

## Permission Errors

### Problem: `EACCES: permission denied` when running `make setup-dev`

**Symptom:**

```bash
npm ERR! Error: EACCES: permission denied, mkdir '/home/user/project/frontend/node_modules/@types'
```

**Cause:**
Docker (or another process run with `sudo`) created files/folders owned by `root`.

**Solution 1 - Quick Fix:**

```bash
# Remove root-owned directories
sudo rm -rf frontend/node_modules frontend/.next

# Run setup again
make setup-dev
```

**Solution 2 - Use Makefile:**

```bash
# The Makefile now auto-detects and fixes this
make setup-dev  # Will automatically fix permissions if needed
```

**Solution 3 - Manual Fix:**

```bash
# Fix ownership of existing directories
make fix-permissions

# Then continue
make setup-dev
```

**Prevention:**
Never run `npm install` or `docker-compose` with `sudo` in the project directory.

---

## Virtual Environment Issues

### Problem: `python: command not found`

**Solution:**

```bash
# Use python3 instead
python3 -m venv .venv

# Or update Makefile PYTHON_VERSION variable
PYTHON_VERSION := python3.12  # or python3.11
```

### Problem: Virtual environment not activating

**Symptom:**

```bash
source .venv/bin/activate
# No (.venv) in prompt
```

**Solutions:**

```bash
# 1. Check if venv exists
ls -la .venv/bin/activate

# 2. Recreate if corrupted
make clean-all
make venv

# 3. Use absolute path
source /full/path/to/project/.venv/bin/activate
```

### Problem: `ModuleNotFoundError` even after installation

**Solution:**

```bash
# Verify you're using venv Python
which python  # Should show .venv/bin/python

# If not, activate venv
source .venv/bin/activate

# Or use Makefile (automatic)
make test  # Uses .venv automatically
```

---

## Docker Issues

### Problem: Docker containers created as root

**Symptom:**
Containers create files owned by `root:root` in mounted volumes.

**Solution:**

```bash
# Add user mapping to docker-compose.yml
services:
  frontend:
    user: "${UID}:${GID}"  # Use host user ID

# Set in .env file
UID=1000
GID=1000

# Or find your IDs
id -u  # Your UID
id -g  # Your GID
```

### Problem: Docker volumes persist old data

**Solution:**

```bash
# Clean Docker volumes
docker-compose down -v

# Remove specific volumes
docker volume ls
docker volume rm <volume_name>

# Nuclear option (removes ALL Docker data)
docker system prune -a --volumes
```

---

## Pre-Commit Hook Issues

### Problem: Pre-commit hooks not running

**Solution:**

```bash
# Reinstall hooks
make install-hooks

# Or manually
source .venv/bin/activate
pre-commit install
pre-commit install --hook-type commit-msg
```

### Problem: `pre-commit: command not found`

**Solution:**

```bash
# Install in venv
source .venv/bin/activate
pip install pre-commit

# Or use Makefile
make install-hooks
```

### Problem: Hooks run forever / timeout

**Solution:**

```bash
# Clean pre-commit cache
pre-commit clean

# Update hooks
pre-commit autoupdate

# Reinstall
pre-commit uninstall
pre-commit install
```

---

## Node.js / Frontend Issues

### Problem: `npm ERR! code ERESOLVE` dependency conflicts

**Solution:**

```bash
# Clear npm cache
cd frontend
npm cache clean --force

# Remove lock file and node_modules
rm -rf node_modules package-lock.json

# Fresh install
npm install
```

### Problem: Next.js build fails

**Symptoms:**

```bash
Error: ENOENT: no such file or directory
```

**Solution:**

```bash
# Clean Next.js cache
cd frontend
rm -rf .next

# Rebuild
npm run build
```

### Problem: TypeScript errors in editor but build succeeds

**Solution:**

```bash
# Restart TypeScript server in VS Code
# Ctrl+Shift+P → "TypeScript: Restart TS Server"

# Or rebuild
cd frontend
npx tsc --noEmit
```

---

## Python / Backend Issues

### Problem: Import errors when running tests

**Solution:**

```bash
# Ensure pytest is in venv
source .venv/bin/activate
pip install pytest pytest-asyncio

# Or use Makefile
make test-backend
```

### Problem: Database connection errors

**Symptom:**

```bash
sqlalchemy.exc.OperationalError: could not connect to server
```

**Solution:**

```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Start if needed
docker-compose up -d postgres

# Check connection
docker-compose exec postgres pg_isready -U bible -d bibledb

# View logs
docker-compose logs postgres
```

### Problem: `ruff: command not found`

**Solution:**

```bash
# Install in venv
source .venv/bin/activate
pip install ruff

# Or use Makefile (automatic)
make lint  # Uses .venv/bin/ruff automatically
```

---

## Git Issues

### Problem: Large files rejected by pre-commit

**Symptom:**

```bash
- hook id: check-added-large-files
- exit code: 1
File exceeds 1000 KB
```

**Solution:**

```bash
# Option 1: Remove the large file
git rm --cached path/to/large/file

# Option 2: Use Git LFS
git lfs install
git lfs track "*.pdf"
git add .gitattributes

# Option 3: Skip check (emergency only)
SKIP=check-added-large-files git commit -m "..."
```

### Problem: Secrets detected in commit

**Symptom:**

```bash
Detect secrets...........................Failed
- hook id: detect-secrets
```

**Solution:**

```bash
# Option 1: Remove the secret
# Edit the file and remove the secret

# Option 2: Update baseline (if false positive)
make update-baseline

# Option 3: Skip check (emergency only - NOT RECOMMENDED)
git commit --no-verify -m "..."
```

---

## CI/CD Issues

### Problem: GitHub Actions fails but local tests pass

**Possible causes:**

1. **Different Python/Node versions**

   ```yaml
   # Check .github/workflows/*.yml
   python-version: '3.12'  # Must match local
   node-version: '18.x'    # Must match local
   ```

2. **Environment variables missing**

   ```bash
   # Add to GitHub Secrets
   Settings → Secrets → Actions → New repository secret
   ```

3. **Dependencies not cached**

   ```yaml
   # Add caching to workflow
   - uses: actions/cache@v4
     with:
       path: ~/.cache/pip
   ```

### Problem: Docker build fails in CI

**Solution:**

```bash
# Test Docker build locally first
docker-compose build api frontend

# Check Docker logs
docker-compose logs api

# Verify Dockerfiles
docker build -f api/Dockerfile .
docker build -f frontend/Dockerfile .
```

---

## Clean Slate Solutions

### Nuclear Option 1: Fresh Python Environment

```bash
make clean-all  # Removes .venv
make setup-dev  # Recreates everything
```

### Nuclear Option 2: Fresh Node Environment

```bash
cd frontend
sudo rm -rf node_modules .next package-lock.json
npm install
```

### Nuclear Option 3: Fresh Docker Environment

```bash
docker-compose down -v          # Stop and remove volumes
docker system prune -a --volumes  # Remove all Docker data
docker-compose up --build       # Rebuild everything
```

### Nuclear Option 4: Complete Reset

```bash
# Clean everything
make clean-all
sudo rm -rf frontend/node_modules frontend/.next
docker-compose down -v
docker system prune -a --volumes

# Start fresh
make setup-dev
docker-compose up --build
```

---

## Debugging Tips

### Check What's Running

```bash
# Python version
python --version
which python

# Node version
node --version
npm --version

# Virtual environment active?
echo $VIRTUAL_ENV

# Docker containers
docker-compose ps

# Processes
ps aux | grep -E "python|node|postgres|ollama"
```

### View Logs

```bash
# Docker logs
docker-compose logs -f api
docker-compose logs -f frontend
docker-compose logs -f postgres

# Pre-commit logs
pre-commit run --all-files --verbose

# npm logs
cat ~/.npm/_logs/*-debug-0.log
```

### Verify Ownership

```bash
# Check who owns files
ls -la frontend/node_modules
ls -la .venv

# Should be your user, not root
whoami  # Your username
```

### Test Individual Components

```bash
# Test Python
.venv/bin/python -c "import fastapi; print('✓ FastAPI works')"

# Test Node
cd frontend && npm run build

# Test Docker
docker-compose up api
curl http://localhost:8000/health

# Test Database
docker-compose exec postgres psql -U bible -d bibledb -c "SELECT 1;"
```

---

## Getting Help

If issues persist:

1. **Check logs**: `docker-compose logs <service>`
2. **Verify setup**: `make help` to see all commands
3. **Clean slate**: `make clean-all && make setup-dev`
4. **Check docs**:
   - [PRE_COMMIT_SETUP.md](PRE_COMMIT_SETUP.md)
   - [VIRTUAL_ENV.md](VIRTUAL_ENV.md)
   - [TESTING.md](TESTING.md)

5. **Report issue**: Include:
   - Error message (full output)
   - What you ran: `make setup-dev`
   - OS and versions: `python --version`, `node --version`
   - File ownership: `ls -la frontend/node_modules`
