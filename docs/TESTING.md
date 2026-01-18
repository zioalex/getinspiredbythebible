# Testing Guide

This document describes the testing infrastructure for the Bible Inspiration Chat application.

## Overview

The CI/CD pipeline includes comprehensive testing across multiple layers:

- ✅ **Backend API Tests** - Python/FastAPI testing with pytest
- ✅ **Frontend Tests** - Next.js TypeScript checking and linting
- ✅ **Integration Tests** - Docker-based end-to-end testing
- ✅ **Security Checks** - Dependency vulnerability scanning

## Workflow Jobs

### 1. Backend Tests (`backend-tests`)

**Purpose:** Validate Python API code quality and functionality

**What it tests:**

- ✅ Code linting with Ruff (PEP8, imports, naming)
- ✅ Code formatting with Black
- ✅ Type checking with MyPy
- ✅ Unit tests with pytest
- ✅ Module imports and syntax validation
- ✅ Database connectivity (PostgreSQL with pgvector)

**Runs on:** Every push and PR

### 2. Frontend Tests (`frontend-tests`)

**Purpose:** Validate Next.js frontend code and build

**What it tests:**

- ✅ ESLint code quality checks
- ✅ TypeScript compilation (type checking)
- ✅ Production build creation
- ✅ Multi-version Node.js compatibility (18.x, 20.x)

**Runs on:** Every push and PR

### 3. Integration Tests (`integration-tests`)

**Purpose:** Validate full stack functionality with Docker

**What it tests:**

- ✅ Docker image builds successfully
- ✅ PostgreSQL database starts and is healthy
- ✅ API service starts and responds to health checks
- ✅ Frontend service starts and serves pages
- ✅ API endpoints are accessible
- ✅ Configuration is correctly loaded

**Services tested:**

- PostgreSQL (port 5432)
- API (port 8000)
- Frontend (port 3000)

**Runs on:** Every push and PR

### 4. Security Check (`security-check`)

**Purpose:** Scan dependencies for known vulnerabilities

**What it checks:**

- ✅ Python package vulnerabilities (safety)
- ✅ npm package vulnerabilities (npm audit)

**Runs on:** Every push and PR

## Running Tests Locally

### Backend Tests

```bash
# Navigate to API directory
cd api

# Install dependencies
pip install -r requirements.txt
pip install ruff black mypy pytest pytest-asyncio

# Run linting
ruff check .
black --check .
mypy . --ignore-missing-imports

# Run tests (requires PostgreSQL)
export DATABASE_URL=postgresql://bible:bible123@localhost:5432/bibledb  # pragma: allowlist secret
pytest -v

# Test imports
python -c "import main; print('✓ Imports work')"
```

### Frontend Tests

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Run linting
npm run lint

# Type check
npm run type-check

# Build
npm run build
```

### Integration Tests

```bash
# From project root
docker-compose build
docker-compose up -d postgres
sleep 10

# Start API
docker-compose up -d api
sleep 15

# Test API
curl http://localhost:8000/health
curl http://localhost:8000/config

# Start frontend
docker-compose up -d frontend
sleep 20

# Test frontend
curl http://localhost:3000

# Cleanup
docker-compose down -v
```

## Test Files

### Backend Test Files

Located in `api/tests/`:

- `test_api.py` - API endpoint tests
- `test_providers.py` - LLM provider tests
- `test_models.py` - Database model tests

### Configuration Files

- `api/pytest.ini` - Pytest configuration
- `api/pyproject.toml` - Black, Ruff, MyPy configuration
- `api/.flake8` - Flake8 linting rules

## Continuous Integration

The workflow runs automatically on:

- ✅ Push to `main` branch
- ✅ Push to `feature/**` branches
- ✅ All pull requests

## Adding New Tests

### Backend (Python)

1. Create test file in `api/tests/test_*.py`
2. Use pytest conventions:

   ```python
   def test_my_feature():
       assert True
   ```

3. Run locally: `cd api && pytest tests/test_*.py`

### Frontend (TypeScript)

1. Update `frontend/package.json` to add testing framework (Jest/Vitest)
2. Create `__tests__` directory
3. Add test files: `*.test.ts` or `*.spec.ts`

## Troubleshooting

### Backend tests fail with import errors

- Ensure `DATABASE_URL` environment variable is set
- Check PostgreSQL is running and accessible
- Verify all dependencies are installed

### Frontend build fails

- Clear `node_modules` and `.next`: `rm -rf node_modules .next`
- Reinstall: `npm install`
- Check Node.js version: `node --version`

### Integration tests timeout

- Increase sleep timers in workflow
- Check Docker resources (CPU/memory)
- Review service logs: `docker-compose logs <service>`

### Security vulnerabilities reported

- Review the specific CVEs
- Update dependencies if patches available
- Document exceptions if vulnerabilities don't apply

## Future Enhancements

- [ ] Add Jest/Vitest for frontend unit tests
- [ ] Add React Testing Library for component tests
- [ ] Add E2E tests with Playwright/Cypress
- [ ] Add code coverage reporting
- [ ] Add performance benchmarks
- [ ] Add load testing for API
- [ ] Add visual regression tests
- [ ] Mock Ollama for faster tests
- [ ] Add database migration tests
- [ ] Add embedding search accuracy tests

## CI/CD Best Practices

1. **Keep tests fast** - Integration tests should complete in <5 minutes
2. **Test in isolation** - Each test should be independent
3. **Use continue-on-error wisely** - Only for non-critical checks
4. **Cache dependencies** - Use GitHub Actions cache for npm/pip
5. **Fail fast** - Stop on critical failures
6. **Clear logging** - Include detailed error messages
7. **Test matrix** - Test multiple Node.js versions
8. **Security first** - Always scan dependencies

## Monitoring Test Health

Check workflow status:

- GitHub Actions tab in repository
- PR status checks
- Branch protection rules

Green checkmarks mean all tests passed! ✅
