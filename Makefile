.PHONY: help venv install-hooks setup-dev lint test format check-all clean \
	tf-check-version tf-init tf-plan tf-apply tf-destroy tf-fmt tf-validate tf-output tf-refresh \
	validate-env validate-env-strict export-blocked-samples \
	az-acr-list-images az-acr-list-tags az-deployed-images az-image-info \
	az-pg-add-ip az-pg-list-rules az-pg-remove-ip \
	db-backup-info db-backup db-restore-verify db-restore-local \
	db-restore-new-server db-restore-same-server \
	android-test android-test-compose android-build android-build-prod android-lint android-clean android-security-check \
	test-functional test-functional-local test-e2e test-e2e-local \
	repo-metrics audit-metrics \
	check-env-production \
	docker-up docker-up-gpu docker-up-dev docker-up-dev-gpu docker-down docker-down-dev \
	docker-up-prod docker-up-prod-gpu \
	docker-up-local-prod docker-up-local-prod-build docker-up-local-prod-acr-be \
	docker-down-local-prod docker-logs-local-prod docker-restart-local-prod-api

# Use bash for better compatibility
SHELL := /bin/bash

# Virtual environment
VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
PYTHON_VERSION := python3

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
NC := \033[0m # No Color

help: ## Show this help message
	@echo '$(BLUE)Available commands:$(NC)'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}'

venv: ## Create virtual environment
	@# Recreate if: python missing, pip missing, or venv owned by a different uid
	@VENV_OK=1; \
	[ ! -f "$(PYTHON)" ] && VENV_OK=0; \
	[ ! -f "$(PIP)" ] && VENV_OK=0; \
	if [ -e "$(VENV)" ] && [ "$$(stat -c '%u' $(VENV) 2>/dev/null || stat -f '%u' $(VENV) 2>/dev/null)" != "$$(id -u)" ]; then \
		echo "$(YELLOW)⚠ $(VENV) owned by a different uid — will recreate$(NC)"; \
		VENV_OK=0; \
	fi; \
	if [ "$$VENV_OK" = "0" ]; then \
		echo "$(BLUE)Creating virtual environment...$(NC)"; \
		rm -rf $(VENV) 2>/dev/null || { echo "$(YELLOW)Cannot remove $(VENV) (permission denied). Run: sudo rm -rf $(VENV)$(NC)"; exit 1; }; \
		$(PYTHON_VERSION) -m venv $(VENV); \
		echo "$(GREEN)✓ Virtual environment created at $(VENV)$(NC)"; \
	else \
		echo "$(YELLOW)Virtual environment already exists$(NC)"; \
	fi

install-hooks: venv ## Install pre-commit hooks
	@echo "$(BLUE)Installing pre-commit hooks...$(NC)"
	@$(CURDIR)/$(PIP) install -q pre-commit
	@$(CURDIR)/$(VENV)/bin/pre-commit install
	@$(CURDIR)/$(VENV)/bin/pre-commit install --hook-type commit-msg
	@echo "$(GREEN)✓ Pre-commit hooks installed$(NC)"

setup-dev: venv install-hooks ## Setup development environment
	@echo "$(BLUE)Setting up development environment...$(NC)"
	@echo "$(YELLOW)Installing Python dependencies...$(NC)"
	@$(PIP) install -q -r api/requirements-dev.txt
	@$(PIP) install -q ruff black mypy bandit isort safety detect-secrets
	@echo "$(YELLOW)Fixing frontend permissions (if needed)...$(NC)"
	@if [ -d "frontend/node_modules" ]; then \
		if [ "$$(stat -c '%U' frontend/node_modules 2>/dev/null || stat -f '%Su' frontend/node_modules 2>/dev/null)" != "$$(whoami)" ]; then \
			echo "$(YELLOW)Detected root-owned node_modules, fixing...$(NC)"; \
			sudo chown -R $$(whoami):$$(whoami) frontend/node_modules frontend/.next 2>/dev/null || true; \
		fi \
	fi
	@echo "$(YELLOW)Installing Node.js dependencies...$(NC)"
	@cd frontend && npm install
	@echo "$(GREEN)✓ Development environment ready$(NC)"
	@echo ""
	@echo "$(BLUE)To activate the virtual environment, run:$(NC)"
	@echo "  $(YELLOW)source $(VENV)/bin/activate$(NC)"

lint: install-deps ## Run all linters
	@echo "$(BLUE)Running linters...$(NC)"
	@echo "$(YELLOW)Python - Ruff$(NC)"
	@cd api && $(CURDIR)/$(PYTHON) -m ruff check .
	@echo "$(YELLOW)Python - Black$(NC)"
	@cd api && $(CURDIR)/$(PYTHON) -m black --check .
	@echo "$(YELLOW)Frontend - ESLint$(NC)"
	@cd frontend && npm run lint
	@echo "$(GREEN)✓ Linting complete$(NC)"

format: install-deps ## Auto-format all code
	@echo "$(BLUE)Formatting code...$(NC)"
	@echo "$(YELLOW)Python - Black$(NC)"
	@cd api && $(CURDIR)/$(PYTHON) -m black .
	@echo "$(YELLOW)Python - isort$(NC)"
	@cd api && $(CURDIR)/$(PYTHON) -m isort . --profile black
	@echo "$(YELLOW)Python - Ruff (auto-fix)$(NC)"
	@cd api && $(CURDIR)/$(PYTHON) -m ruff check . --fix
	@echo "$(YELLOW)Frontend - Prettier$(NC)"
	@cd frontend && npx prettier --write "src/**/*.{ts,tsx,js,jsx,json,css,md}"
	@echo "$(GREEN)✓ Formatting complete$(NC)"

type-check: install-deps ## Run type checkers
	@echo "$(BLUE)Running type checkers...$(NC)"
	@echo "$(YELLOW)Python - MyPy$(NC)"
	@cd api && $(CURDIR)/$(PYTHON) -m mypy . --ignore-missing-imports
	@echo "$(YELLOW)TypeScript$(NC)"
	@cd frontend && npx tsc --noEmit
	@echo "$(GREEN)✓ Type checking complete$(NC)"

security: install-deps ## Run security checks
	@echo "$(BLUE)Running security checks...$(NC)"
	@echo "$(YELLOW)Python - Bandit$(NC)"
	@cd api && $(CURDIR)/$(PYTHON) -m bandit -r . -ll -i
	@echo "$(YELLOW)Python - Safety$(NC)"
	@cd api && $(CURDIR)/$(PYTHON) -m safety check -r requirements.txt --ignore 70612 || true
	@echo "$(YELLOW)Node - npm audit$(NC)"
	@cd frontend && npm audit --audit-level=high || true
	@echo "$(YELLOW)Secrets detection$(NC)"
	@$(CURDIR)/$(VENV)/bin/detect-secrets scan --baseline .secrets.baseline
	@echo "$(GREEN)✓ Security checks complete$(NC)"

install-deps: venv ## Install Python dependencies
	@if ! $(CURDIR)/$(PYTHON) -c "import pytest" 2>/dev/null; then \
		echo "$(YELLOW)Installing Python dependencies...$(NC)"; \
		$(CURDIR)/$(PIP) install -q -r api/requirements-dev.txt; \
		$(CURDIR)/$(PIP) install -q ruff black mypy bandit isort safety detect-secrets; \
		echo "$(GREEN)✓ Dependencies installed$(NC)"; \
	fi

test-backend: install-deps ## Run backend tests
	@echo "$(BLUE)Running backend tests...$(NC)"
	@echo "$(YELLOW)Linting with Ruff...$(NC)"
	@cd api && $(CURDIR)/$(PYTHON) -m ruff check . --select E,F,W,C90,I,N --ignore E501 || true
	@echo "$(YELLOW)Format check with Black...$(NC)"
	@cd api && $(CURDIR)/$(PYTHON) -m black --check --diff . || true
	@echo "$(YELLOW)Type check with MyPy...$(NC)"
	@cd api && $(CURDIR)/$(PYTHON) -m mypy . --ignore-missing-imports --no-strict-optional || true
	@echo "$(YELLOW)Running pytest (api tests)...$(NC)"
	@cd api && $(CURDIR)/$(PYTHON) -m pytest -v --tb=short || true
	@echo "$(YELLOW)Running pytest (migration tests)...$(NC)"
	@cd scripts/migrations && DATABASE_URL="postgresql://test:test@localhost/test" $(CURDIR)/$(PYTHON) -m pytest test_run_migrations.py -v --tb=short || true  # pragma: allowlist secret
	@echo "$(YELLOW)Testing API syntax and imports...$(NC)"
	@cd api && $(CURDIR)/$(PYTHON) -c "import main; import config; print('✓ Core modules import successfully')"
	@cd api && $(CURDIR)/$(PYTHON) -c "from routes import chat, scripture; print('✓ Route modules import successfully')"
	@cd api && $(CURDIR)/$(PYTHON) -c "from providers import factory; print('✓ Provider modules import successfully')"
	@cd api && $(CURDIR)/$(PYTHON) -c "from scripture import repository, search; print('✓ Scripture modules import successfully')"
	@echo "$(GREEN)✓ Backend tests complete$(NC)"

test-frontend: ## Run frontend tests
	@echo "$(BLUE)Running frontend tests...$(NC)"
	@echo "$(YELLOW)Linting...$(NC)"
	@cd frontend && npm run lint
	@echo "$(YELLOW)Type checking...$(NC)"
	@cd frontend && npx tsc --noEmit
	@echo "$(YELLOW)Building...$(NC)"
	@cd frontend && npm run build
	@echo "$(GREEN)✓ Frontend tests complete$(NC)"

test: test-backend test-frontend ## Run all tests

# ==================== Android ====================

android-test: ## Run Android unit tests (requires JDK 17)
	@echo "$(BLUE)Running Android unit tests...$(NC)"
	@cd android && ./gradlew testDebugUnitTest --no-daemon
	@echo "$(GREEN)✓ Android unit tests complete$(NC)"

android-test-compose: ## Run Android Compose UI tests via Robolectric — separate from android-test (requires JDK 17)
	@echo "$(BLUE)Running Android Compose UI tests...$(NC)"
	@cd android && ./gradlew testDebugCompose --no-daemon
	@echo "$(GREEN)✓ Android Compose UI tests complete$(NC)"
	@echo "$(YELLOW)Report: android/app/build/reports/tests/testDebugCompose/index.html$(NC)"

android-build: ## Build Android debug APK pointing at local dev backend (requires JDK 17)
	@echo "$(BLUE)Building Android debug APK (local backend: http://10.0.2.2:8000/)...$(NC)"
	@cd android && ./gradlew assembleDebug --no-daemon
	@echo "$(GREEN)✓ Android debug APK: android/app/build/outputs/apk/debug/app-debug.apk$(NC)"

android-build-prod: ## Build Android debug APK pointing at the production backend (requires JDK 17)
	@echo "$(BLUE)Building Android debug APK (prod backend)...$(NC)"
	@cd android && ./gradlew assembleDebug --no-daemon \
		-PbaseUrl=https://api.voxquieta.org/
	@echo "$(GREEN)✓ Android prod APK: android/app/build/outputs/apk/debug/app-debug.apk$(NC)"

android-lint: ## Run Android lint checks
	@echo "$(BLUE)Running Android lint...$(NC)"
	@cd android && ./gradlew lintDebug --no-daemon
	@echo "$(GREEN)✓ Android lint report: android/app/build/reports/lint-results-debug.html$(NC)"

android-clean: ## Clean Android build artifacts
	@echo "$(BLUE)Cleaning Android build artifacts...$(NC)"
	@cd android && ./gradlew clean --no-daemon
	@echo "$(GREEN)✓ Android build artifacts cleaned$(NC)"

android-security-check: ## Run OWASP dependency vulnerability scan (uses CLI, not Gradle plugin)
	@echo "$(BLUE)Running OWASP dependency vulnerability scan...$(NC)"
	@echo "$(YELLOW)⚠ Requires dependency-check CLI: https://dependency-check.github.io/DependencyCheck/$(NC)"
	@mkdir -p android/app/build/reports
	@cd android && ./gradlew :app:dependencies --configuration releaseRuntimeClasspath --no-daemon
	@dependency-check.sh \
		--scan "$$HOME/.gradle/caches/modules-2/files-2.1/" \
		--format HTML \
		--out android/app/build/reports \
		--project "VoxQuietaApp" \
		--failOnCVSS 7 \
		--suppression android/dependency-check-suppressions.xml
	@echo "$(GREEN)✓ OWASP scan complete. Report: android/app/build/reports/dependency-check-report.html$(NC)"

test-functional: install-deps ## Run functional tests against the backend API (requires BACKEND_API_URL)
	@echo "$(BLUE)Running functional tests against backend API...$(NC)"
	@cd api && $(CURDIR)/$(PYTHON) -m pytest tests/functional/ -m functional -v --tb=short
	@echo "$(GREEN)✓ Functional tests complete$(NC)"

# ==================== E2e and Functional tests ====================

test-functional-local: install-deps ## Run functional tests against local backend API (localhost:8000)
	@echo "$(BLUE)Running functional tests against local API...$(NC)"
	@cd api && BACKEND_API_URL=http://localhost:8000 $(CURDIR)/$(PYTHON) -m pytest tests/functional/ -m functional -v --tb=short
	@echo "$(GREEN)✓ Local functional tests complete$(NC)"

test-e2e: install-deps ## Run e2e tests simulating real users via the frontend URL
	@echo "$(BLUE)Running e2e tests against production frontend...$(NC)"
	@cd api && $(CURDIR)/$(PYTHON) -m pytest tests/e2e/ -m e2e -v --tb=short
	@echo "$(GREEN)✓ E2E tests complete$(NC)"

test-e2e-local: install-deps ## Run e2e tests against local frontend (localhost:3000)
	@echo "$(BLUE)Running e2e tests against local frontend...$(NC)"
	@cd api && FRONTEND_URL=http://localhost:3000 $(CURDIR)/$(PYTHON) -m pytest tests/e2e/ -m e2e -v --tb=short
	@echo "$(GREEN)✓ Local e2e tests complete$(NC)"

# ==================== Golden Set Testing ====================

golden-test: install-deps ## Run golden set tests (mock mode, CI-safe)
	@echo "$(BLUE)Running golden set tests (mock mode)...$(NC)"
	@cd api && $(CURDIR)/$(PYTHON) -m pytest tests/test_golden_set.py -v -m golden_set
	@echo "$(GREEN)✓ Golden set tests complete$(NC)"

check-all: lint type-check security test validate-env ## Run all checks (pre-push validation)
	@echo "$(GREEN)✓ All checks passed!$(NC)"

pre-commit: install-deps ## Run pre-commit on all files
	@echo "$(BLUE)Running pre-commit hooks on all files...$(NC)"
	@$(CURDIR)/$(VENV)/bin/pre-commit run --all-files
	@echo "$(GREEN)✓ Pre-commit checks complete$(NC)"

validate-env: install-deps ## Validate env vars between docker-compose and Terraform
	@echo "$(BLUE)Validating environment variable consistency...$(NC)"
	@$(CURDIR)/$(PYTHON) scripts/validate-env.py
	@echo "$(GREEN)✓ Environment validation complete$(NC)"

validate-env-strict: install-deps ## Validate env vars (strict mode - warnings are errors)
	@echo "$(BLUE)Validating environment variables (strict mode)...$(NC)"
	@$(CURDIR)/$(PYTHON) scripts/validate-env.py --strict
	@echo "$(GREEN)✓ Environment validation complete$(NC)"

export-blocked-samples: install-deps ## Export captured blocked-message samples (read-only). Usage: make export-blocked-samples ARGS="--format csv --since 2026-05-01". Requires DATABASE_URL.
	@$(CURDIR)/$(PYTHON) scripts/export_blocked_samples.py $(ARGS)

clean: ## Clean build artifacts and caches
	@echo "$(BLUE)Cleaning build artifacts...$(NC)"
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@if [ -d "frontend/.next" ]; then sudo rm -rf frontend/.next 2>/dev/null || rm -rf frontend/.next; fi
	@if [ -d "frontend/node_modules" ]; then sudo rm -rf frontend/node_modules 2>/dev/null || rm -rf frontend/node_modules; fi
	@echo "$(GREEN)✓ Cleanup complete$(NC)"

clean-all: clean ## Clean everything including virtual environment
	@echo "$(BLUE)Removing virtual environment...$(NC)"
	@rm -rf $(VENV)

fix-permissions: ## Fix ownership of Docker-created files
	@echo "$(BLUE)Fixing file permissions...$(NC)"
	@if [ -d "frontend/node_modules" ]; then \
		echo "$(YELLOW)Fixing frontend/node_modules ownership...$(NC)"; \
		sudo chown -R $$(whoami):$$(whoami) frontend/node_modules; \
	fi
	@if [ -d "frontend/.next" ]; then \
		echo "$(YELLOW)Fixing frontend/.next ownership...$(NC)"; \
		sudo chown -R $$(whoami):$$(whoami) frontend/.next; \
	fi
	@echo "$(GREEN)✓ Permissions fixed$(NC)"
	@echo "$(GREEN)✓ Full cleanup complete$(NC)"

update-baseline: install-deps ## Update secrets baseline
	@echo "$(BLUE)Updating secrets baseline...$(NC)"
	@$(CURDIR)/$(VENV)/bin/detect-secrets scan --baseline .secrets.baseline --update
	@echo "$(GREEN)✓ Baseline updated$(NC)"

# ==================== Docker Commands ====================
#
# Run modes (see docs/LOCAL_DEVELOPMENT.md for the full matrix):
#   docker-up                fully local: Ollama + local Postgres      (.env.local)
#   docker-up-dev            second local stack on shifted ports       (.env.dev)
#   docker-up-local-prod     local containers -> PROD DB + cloud LLMs  (.env.production)
#   docker-up-local-prod-acr-be  prod backend image from ACR + local frontend

# Auto-create env files from their committed templates on first run.
.env.local:
	@echo "$(YELLOW).env.local not found — creating from .env.local.example$(NC)"
	@cp .env.local.example .env.local

.env.dev:
	@echo "$(YELLOW).env.dev not found — creating from .env.dev.example$(NC)"
	@cp .env.dev.example .env.dev

# .env.production holds real secrets, so it is never auto-created.
check-env-production:
	@if [ ! -f .env.production ]; then \
		echo "$(YELLOW)Error: .env.production not found$(NC)"; \
		echo "$(YELLOW)Create it from the template and fill in the secrets:$(NC)"; \
		echo "  cp .env.production.example .env.production"; \
		exit 1; \
	fi

docker-up: .env.local ## Start services (local development, CPU mode)
	@echo "$(BLUE)Starting services in local development mode (CPU)...$(NC)"
	@docker compose --env-file .env.local up -d
	@echo "$(GREEN)✓ Services started$(NC)"
	@echo "$(YELLOW)Frontend: http://localhost:3000$(NC)"
	@echo "$(YELLOW)API: http://localhost:8000$(NC)"
	@echo "$(YELLOW)API Docs: http://localhost:8000/docs$(NC)"
	@echo "$(YELLOW)First run: db-init loads Bible data + embeddings (follow with 'docker compose logs -f db-init')$(NC)"

docker-up-gpu: .env.local ## Start services (local development, GPU mode)
	@echo "$(BLUE)Starting services in local development mode (GPU)...$(NC)"
	@docker compose --env-file .env.local -f docker-compose.yml -f docker-compose.gpu.yml up -d
	@echo "$(GREEN)✓ Services started$(NC)"
	@echo "$(YELLOW)Frontend: http://localhost:3000$(NC)"
	@echo "$(YELLOW)API: http://localhost:8000$(NC)"
	@echo "$(YELLOW)API Docs: http://localhost:8000/docs$(NC)"

# ==================== Local against PROD DB + cloud LLMs ====================
# Local containers wired to the production database and cloud LLM providers
# (OpenRouter chat + Azure OpenAI embeddings). Requires .env.production and
# your IP on the Azure PG firewall (make az-pg-add-ip).

LOCAL_PROD_PROJECT := getinspired-local-prod

# These stacks run the frontend and API locally — .env.production should point
# NEXT_PUBLIC_API_URL at http://localhost:8000. If it's left pointing at a real
# deployed backend, the frontend silently bypasses the local API entirely
# (including the TURNSTILE_ENABLED=false pin below), and things like a stale
# production Turnstile site key start rejecting requests from localhost.
check-local-api-url: check-env-production
	@API_URL=$$(grep -E '^NEXT_PUBLIC_API_URL=' .env.production | tail -1 | cut -d= -f2-); \
	if [ -n "$$API_URL" ] && ! echo "$$API_URL" | grep -qE '^https?://localhost(:[0-9]+)?/?$$'; then \
		echo "$(YELLOW)⚠ .env.production NEXT_PUBLIC_API_URL=$$API_URL$(NC)"; \
		echo "$(YELLOW)  This stack expects http://localhost:8000 — the frontend will bypass your local API and talk to that host instead.$(NC)"; \
	fi

docker-up-local-prod: check-local-api-url ## Start local stack against prod DB + cloud LLMs (cached images)
	@echo "$(BLUE)Starting local stack against PROD DB + cloud LLMs...$(NC)"
	@docker compose -p $(LOCAL_PROD_PROJECT) --env-file .env.production -f docker-compose.local-prod.yml up -d
	@echo "$(GREEN)✓ Services started$(NC)"
	@echo "$(YELLOW)Frontend: http://localhost:3000$(NC)"
	@echo "$(YELLOW)API: http://localhost:8000 (docs: /docs)$(NC)"
	@echo "$(YELLOW)⚠ This stack talks to the REAL production database$(NC)"

docker-up-local-prod-build: check-local-api-url ## Same as docker-up-local-prod but rebuild images from source
	@echo "$(BLUE)Rebuilding and starting local stack against PROD DB + cloud LLMs...$(NC)"
	@docker compose -p $(LOCAL_PROD_PROJECT) --env-file .env.production -f docker-compose.local-prod.yml up -d --build
	@echo "$(GREEN)✓ Services rebuilt and started$(NC)"
	@echo "$(YELLOW)⚠ This stack talks to the REAL production database$(NC)"

docker-up-local-prod-acr-be: check-local-api-url ## Prod backend image from ACR + local frontend (usage: TAG=abc1234, default latest)
	@echo "$(BLUE)Starting ACR backend ($(if $(TAG),$(TAG),latest)) + local frontend...$(NC)"
	@echo "$(YELLOW)Note: requires 'az acr login --name <ACR_NAME>' beforehand$(NC)"
	@TAG=$(TAG) docker compose -p $(LOCAL_PROD_PROJECT) --env-file .env.production -f docker-compose.local-prod-acr-be.yml up -d
	@echo "$(GREEN)✓ Services started$(NC)"
	@echo "$(YELLOW)⚠ This stack talks to the REAL production database$(NC)"

docker-down-local-prod: ## Stop the local-prod stack (both variants)
	@echo "$(BLUE)Stopping local-prod services...$(NC)"
	@docker compose -p $(LOCAL_PROD_PROJECT) -f docker-compose.local-prod.yml down --remove-orphans
	@echo "$(GREEN)✓ Local-prod services stopped$(NC)"

docker-logs-local-prod: ## Tail local-prod stack logs
	@docker compose -p $(LOCAL_PROD_PROJECT) -f docker-compose.local-prod.yml logs -f

docker-restart-local-prod-api: ## Restart the local-prod API only
	@docker compose -p $(LOCAL_PROD_PROJECT) -f docker-compose.local-prod.yml restart api

docker-up-prod: check-env-production ## Start full stack with prod env (legacy self-hosted mode, CPU)
	@echo "$(BLUE)Starting services in production mode (CPU)...$(NC)"
	@docker compose --env-file .env.production up -d --build
	@echo "$(GREEN)✓ Services started in production mode$(NC)"
	@echo "$(YELLOW)Frontend: https://voxquieta.org$(NC)"
	@echo "$(YELLOW)API: https://voxquieta.org/api$(NC)"
	@echo "$(YELLOW)Note: Ensure Cloudflare Tunnel is running$(NC)"

docker-up-prod-gpu: check-env-production ## Start full stack with prod env (legacy self-hosted mode, GPU)
	@echo "$(BLUE)Starting services in production mode (GPU)...$(NC)"
	@docker compose --env-file .env.production -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
	@echo "$(GREEN)✓ Services started in production mode$(NC)"
	@echo "$(YELLOW)Frontend: https://voxquieta.org$(NC)"
	@echo "$(YELLOW)API: https://voxquieta.org/api$(NC)"
	@echo "$(YELLOW)Note: Ensure Cloudflare Tunnel is running$(NC)"

docker-up-dev: .env.dev ## Start services (dev mode, safe alongside prod)
	@echo "$(BLUE)Starting services in dev mode...$(NC)"
	@# The dev stack shares the ollama_data volume with prod (external volume);
	@# create it if no prod stack ever did, so a fresh machine also works.
	@docker volume inspect ollama_data >/dev/null 2>&1 || docker volume create ollama_data >/dev/null
	@docker compose -p getinspired-dev --env-file .env.dev -f docker-compose.dev.yml up -d
	@echo "$(GREEN)✓ Dev services started$(NC)"
	@echo "$(YELLOW)Frontend: http://localhost:3001$(NC)"
	@echo "$(YELLOW)API: http://localhost:8001$(NC)"
	@echo "$(YELLOW)API Docs: http://localhost:8001/docs$(NC)"
	@echo "$(YELLOW)Postgres: localhost:5433$(NC)"
	@echo "$(YELLOW)Ollama: localhost:11435$(NC)"

docker-up-dev-gpu: .env.dev ## Start dev services with NVIDIA GPU for Ollama
	@echo "$(BLUE)Starting services in dev mode (GPU)...$(NC)"
	@docker volume inspect ollama_data >/dev/null 2>&1 || docker volume create ollama_data >/dev/null
	@docker compose -p getinspired-dev --env-file .env.dev -f docker-compose.dev.yml -f docker-compose.gpu.yml up -d
	@echo "$(GREEN)✓ Dev services started (GPU)$(NC)"

docker-down-dev: ## Stop dev services
	@echo "$(BLUE)Stopping dev services...$(NC)"
	@docker compose -p getinspired-dev --env-file .env.dev -f docker-compose.dev.yml down
	@echo "$(GREEN)✓ Dev services stopped$(NC)"

docker-logs-dev: ## View dev services logs
	@docker compose -p getinspired-dev --env-file .env.dev -f docker-compose.dev.yml logs -f

docker-restart-dev: ## Restart all dev services
	@echo "$(BLUE)Restarting dev services...$(NC)"
	@docker compose -p getinspired-dev --env-file .env.dev -f docker-compose.dev.yml restart
	@echo "$(GREEN)✓ Dev services restarted$(NC)"

docker-restart-dev-api: ## Restart dev API only
	@echo "$(BLUE)Restarting dev API...$(NC)"
	@docker compose -p getinspired-dev --env-file .env.dev -f docker-compose.dev.yml restart api
	@echo "$(GREEN)✓ Dev API restarted$(NC)"

docker-restart-dev-frontend: ## Restart dev frontend only
	@echo "$(BLUE)Restarting dev frontend...$(NC)"
	@docker compose -p getinspired-dev --env-file .env.dev -f docker-compose.dev.yml restart frontend
	@echo "$(GREEN)✓ Dev frontend restarted$(NC)"

docker-reinit-dev-db: ## Reinitialize dev database (recreate db-init)
	@echo "$(BLUE)Reinitializing dev database...$(NC)"
	@docker compose -p getinspired-dev --env-file .env.dev -f docker-compose.dev.yml rm -sf db-init
	@docker compose -p getinspired-dev --env-file .env.dev -f docker-compose.dev.yml up -d db-init
	@echo "$(GREEN)✓ Database initialization started$(NC)"
	@echo "$(YELLOW)Check logs: make docker-logs-dev-init$(NC)"

docker-logs-dev-init: ## View dev db-init logs
	@docker logs -f getinspired-dev-db-init-1

docker-restart: ## Restart all services
	@echo "$(BLUE)Restarting services...$(NC)"
	@docker compose restart
	@echo "$(GREEN)✓ Services restarted$(NC)"

docker-restart-frontend: ## Restart frontend only
	@echo "$(BLUE)Restarting frontend...$(NC)"
	@docker compose restart frontend
	@echo "$(GREEN)✓ Frontend restarted$(NC)"

docker-restart-api: ## Restart API only
	@echo "$(BLUE)Restarting API...$(NC)"
	@docker compose restart api
	@echo "$(GREEN)✓ API restarted$(NC)"

docker-down: ## Stop Docker Compose services
	@echo "$(BLUE)Stopping services...$(NC)"
	@docker compose down
	@echo "$(GREEN)✓ Services stopped$(NC)"

docker-logs: ## View Docker Compose logs
	@docker compose logs -f

docker-build: ## Build Docker images
	@echo "$(BLUE)Building Docker images...$(NC)"
	@docker compose build
	@echo "$(GREEN)✓ Images built$(NC)"

docker-test: ## Run tests in Docker
	@echo "$(BLUE)Running tests in Docker...$(NC)"
	@docker compose build api frontend
	@docker compose run --rm api pytest -v
	@echo "$(GREEN)✓ Docker tests complete$(NC)"

docker-reset-db: ## Reset database (removes volume and reinitializes)
	@echo "$(BLUE)Resetting database...$(NC)"
	@echo "$(YELLOW)Stopping services...$(NC)"
	@docker compose down
	@echo "$(YELLOW)Removing database volume...$(NC)"
	@docker volume rm getinspiredbythebible_postgres_data 2>/dev/null || echo "$(YELLOW)Volume not found or already removed$(NC)"
	@echo "$(GREEN)✓ Database reset complete$(NC)"
	@echo "$(YELLOW)Run 'make docker-up' or 'make docker-up-gpu' to start fresh$(NC)"

docker-reset-db-dev: ## Reset dev database (removes volume and reinitializes)
	@echo "$(BLUE)Resetting dev database...$(NC)"
	@docker compose -p getinspired-dev down
	@docker volume rm getinspired-dev_postgres_data 2>/dev/null || echo "$(YELLOW)Volume not found$(NC)"
	@echo "$(GREEN)✓ Dev database reset complete$(NC)"

functional-test: ## Run functional tests (requires running services)
	@echo "$(BLUE)Running functional tests...$(NC)"
	@echo "$(YELLOW)Testing API health...$(NC)"
	@curl -sf http://localhost:8000/health/live > /dev/null && echo "$(GREEN)✓ API health check passed$(NC)" || (echo "$(YELLOW)API not running, skipping$(NC)" && exit 0)
	@echo "$(YELLOW)Testing embedding dimension consistency...$(NC)"
	@docker compose exec -T postgres psql -U bible -d bibledb -t -c \
		"SELECT CASE WHEN COUNT(*) = 0 THEN 'No embeddings yet' \
		 WHEN COUNT(DISTINCT vector_dims(embedding)) = 1 THEN '✓ All embeddings have consistent dimensions: ' || MAX(vector_dims(embedding))::text \
		 ELSE '✗ ERROR: Mixed embedding dimensions found!' END FROM verses WHERE embedding IS NOT NULL;" \
		2>/dev/null || echo "$(YELLOW)Database not accessible$(NC)"
	@echo "$(YELLOW)Testing translation table...$(NC)"
	@docker compose exec -T postgres psql -U bible -d bibledb -t -c \
		"SELECT '✓ Translations: ' || COUNT(*) || ' configured' FROM translations;" \
		2>/dev/null || echo "$(YELLOW)Database not accessible$(NC)"
	@echo "$(YELLOW)Testing verse counts by translation...$(NC)"
	@docker compose exec -T postgres psql -U bible -d bibledb -t -c \
		"SELECT translation || ': ' || COUNT(*) || ' verses' FROM verses GROUP BY translation ORDER BY translation;" \
		2>/dev/null || echo "$(YELLOW)Database not accessible$(NC)"
	@echo "$(GREEN)✓ Functional tests complete$(NC)"

functional-test-dev: ## Run functional tests on dev environment
	@echo "$(BLUE)Running functional tests on dev...$(NC)"
	@echo "$(YELLOW)Testing API health...$(NC)"
	@curl -sf http://localhost:8001/health/live > /dev/null && echo "$(GREEN)✓ API health check passed$(NC)" || (echo "$(YELLOW)API not running$(NC)" && exit 0)
	@echo "$(YELLOW)Testing embedding dimensions...$(NC)"
	@docker compose -p getinspired-dev exec -T postgres psql -U bible -d bibledb -t -c \
		"SELECT CASE WHEN COUNT(*) = 0 THEN 'No embeddings yet' \
		 WHEN COUNT(DISTINCT vector_dims(embedding)) = 1 THEN '✓ All embeddings consistent: ' || MAX(vector_dims(embedding))::text || ' dimensions' \
		 ELSE '✗ ERROR: Mixed dimensions!' END FROM verses WHERE embedding IS NOT NULL;" \
		2>/dev/null || echo "$(YELLOW)Database not accessible$(NC)"
	@echo "$(GREEN)✓ Dev functional tests complete$(NC)"

# ==================== Azure Production Build Commands ====================

# Get git SHA for image tagging (short 7-char version)
GIT_SHA := $(shell git rev-parse --short=7 HEAD 2>/dev/null || echo "latest")

docker-build-prod: docker-build-prod-backend docker-build-prod-frontend ## Build and push all images to ACR (tagged with git SHA)
	@echo "$(GREEN)✓ All production images built and pushed with tag: $(GIT_SHA)$(NC)"

docker-build-prod-backend: ## Build and push backend image to ACR (tagged with git SHA)
	@echo "$(BLUE)Building and pushing backend to ACR (tag: $(GIT_SHA))...$(NC)"
	@if [ ! -f .env.production ]; then \
		echo "$(YELLOW)Error: .env.production not found$(NC)"; \
		exit 1; \
	fi
	@source .env.production && az acr login --name $$ACR_NAME && \
	docker build -t $$ACR_NAME.azurecr.io/bible-backend:$(GIT_SHA) \
		-t $$ACR_NAME.azurecr.io/bible-backend:latest ./api && \
	docker push $$ACR_NAME.azurecr.io/bible-backend:$(GIT_SHA) && \
	docker push $$ACR_NAME.azurecr.io/bible-backend:latest
	@echo "$(GREEN)✓ Backend image pushed to ACR ($(GIT_SHA))$(NC)"

docker-build-prod-frontend: ## Build and push frontend image to ACR (tagged with git SHA)
	@echo "$(BLUE)Building and pushing frontend to ACR (tag: $(GIT_SHA))...$(NC)"
	@if [ ! -f .env.production ]; then \
		echo "$(YELLOW)Error: .env.production not found$(NC)"; \
		exit 1; \
	fi
	@# Stage CHANGELOG.md into the build context (docker build context is ./frontend,
	@# so the repo-root CHANGELOG.md is otherwise invisible inside the container).
	@# The trap ensures cleanup even on build failure.
	@cp CHANGELOG.md frontend/CHANGELOG.md; \
	trap 'rm -f frontend/CHANGELOG.md' EXIT; \
	source .env.production && az acr login --name $$ACR_NAME && \
	docker build --no-cache -t $$ACR_NAME.azurecr.io/bible-frontend:$(GIT_SHA) \
		-t $$ACR_NAME.azurecr.io/bible-frontend:latest \
		--target production \
		--build-arg NEXT_PUBLIC_API_URL=$$NEXT_PUBLIC_API_URL ./frontend && \
	docker push $$ACR_NAME.azurecr.io/bible-frontend:$(GIT_SHA) && \
	docker push $$ACR_NAME.azurecr.io/bible-frontend:latest
	@$(MAKE) docker-verify-frontend
	@echo "$(GREEN)✓ Frontend image pushed to ACR ($(GIT_SHA))$(NC)"

docker-verify-frontend: ## Verify frontend image has correct API URL baked in
	@echo "$(BLUE)Verifying frontend image configuration...$(NC)"
	@source .env.production && \
	IMAGE="$$ACR_NAME.azurecr.io/bible-frontend:$(GIT_SHA)" && \
	echo "$(YELLOW)Checking image: $$IMAGE$(NC)" && \
	if docker run --rm $$IMAGE sh -c "grep -r 'localhost:8000' .next/ 2>/dev/null" | head -1 | grep -q .; then \
		echo "$(YELLOW)ERROR: localhost:8000 found in image - NEXT_PUBLIC_API_URL not applied!$(NC)"; \
		exit 1; \
	else \
		echo "$(GREEN)✓ No localhost:8000 found in image$(NC)"; \
	fi && \
	if docker run --rm $$IMAGE sh -c "grep -r '$$NEXT_PUBLIC_API_URL' .next/ 2>/dev/null" | head -1 | grep -q .; then \
		echo "$(GREEN)✓ Correct API URL found: $$NEXT_PUBLIC_API_URL$(NC)"; \
	else \
		echo "$(YELLOW)Warning: Could not verify API URL (may be minified)$(NC)"; \
	fi

docker-update-tfvars: ## Update terraform.tfvars with current git SHA image tags
	@echo "$(BLUE)Updating terraform.tfvars with image tag: $(GIT_SHA)...$(NC)"
	@source .env.production && \
	sed -i 's|backend_image  = ".*"|backend_image  = "'$$ACR_NAME'.azurecr.io/bible-backend:$(GIT_SHA)"|' $(TF_DIR)/terraform.tfvars && \
	sed -i 's|frontend_image = ".*"|frontend_image = "'$$ACR_NAME'.azurecr.io/bible-frontend:$(GIT_SHA)"|' $(TF_DIR)/terraform.tfvars
	@echo "$(GREEN)✓ terraform.tfvars updated with tag: $(GIT_SHA)$(NC)"
	@grep -E "^(backend|frontend)_image" $(TF_DIR)/terraform.tfvars

docker-deploy-prod: ## Deploy images to Azure Container Apps via Terraform
	@echo "$(BLUE)Deploying to Azure Container Apps via Terraform...$(NC)"
	@$(MAKE) docker-update-tfvars
	@$(MAKE) tf-apply-auto
	@echo "$(GREEN)✓ Deployment complete (tag: $(GIT_SHA))$(NC)"

docker-deploy-prod-quick: ## Deploy images directly via az CLI (faster, no Terraform)
	@echo "$(BLUE)Deploying to Azure Container Apps (quick mode)...$(NC)"
	@source .env.production && \
	az containerapp update \
		--name bible-app-backend \
		--resource-group bible-app-rg \
		--image $$ACR_NAME.azurecr.io/bible-backend:$(GIT_SHA) && \
	az containerapp update \
		--name bible-app-frontend \
		--resource-group bible-app-rg \
		--image $$ACR_NAME.azurecr.io/bible-frontend:$(GIT_SHA)
	@echo "$(GREEN)✓ Deployment complete (tag: $(GIT_SHA))$(NC)"

docker-build-deploy-prod: docker-build-prod docker-deploy-prod ## Build, push, and deploy all images
	@echo "$(GREEN)✓ Full production deployment complete (tag: $(GIT_SHA))$(NC)"

docker-get-backend-url: ## Get the backend URL from Azure
	@az containerapp show \
		--name bible-app-backend \
		--resource-group bible-app-rg \
		--query "properties.configuration.ingress.fqdn" -o tsv | \
		xargs -I {} echo "https://{}"

update-env-backend-url: ## Update .env.production with current Azure backend URL
	@./scripts/update-env-backend-url.sh

# ==================== Azure ACR Image Management ====================

# Resource suffix (same as used for PostgreSQL and other Azure resources)
RESOURCE_SUFFIX := mb0172

# ACR name built from suffix
ACR_NAME := bibleappacr$(RESOURCE_SUFFIX)

az-acr-list-images: ## List all image tags with creation dates from ACR
	@echo "$(BLUE)Listing images in ACR...$(NC)"
	@echo ""
	@echo "$(YELLOW)=== Backend Images (bible-backend) ===$(NC)"
	@az acr repository show-tags \
		--name $(ACR_NAME) \
		--repository bible-backend \
		--orderby time_desc \
		--detail \
		--output table 2>/dev/null | head -20 || echo "$(YELLOW)No backend images found$(NC)"
	@echo ""
	@echo "$(YELLOW)=== Frontend Images (bible-frontend) ===$(NC)"
	@az acr repository show-tags \
		--name $(ACR_NAME) \
		--repository bible-frontend \
		--orderby time_desc \
		--detail \
		--output table 2>/dev/null | head -20 || echo "$(YELLOW)No frontend images found$(NC)"

az-acr-list-tags: ## List image tags for backend and frontend (quick view)
	@echo "$(BLUE)Listing image tags in ACR...$(NC)"
	@echo ""
	@echo "$(YELLOW)=== Backend Tags ===$(NC)"
	@az acr repository show-tags \
		--name $(ACR_NAME) \
		--repository bible-backend \
		--orderby time_desc \
		--output tsv 2>/dev/null | head -15 || echo "$(YELLOW)No tags found$(NC)"
	@echo ""
	@echo "$(YELLOW)=== Frontend Tags ===$(NC)"
	@az acr repository show-tags \
		--name $(ACR_NAME) \
		--repository bible-frontend \
		--orderby time_desc \
		--output tsv 2>/dev/null | head -15 || echo "$(YELLOW)No tags found$(NC)"

az-deployed-images: ## Show currently deployed images with digest info
	@echo "$(BLUE)Checking deployed images in Azure Container Apps...$(NC)"
	@echo ""
	@echo "$(YELLOW)=== Backend ($(CA_BACKEND)) ===$(NC)"
	@BACKEND_IMAGE=$$(az containerapp show \
		--name $(CA_BACKEND) \
		--resource-group $(CA_RG) \
		--query "properties.template.containers[0].image" -o tsv 2>/dev/null) && \
	if [ -n "$$BACKEND_IMAGE" ]; then \
		echo "  Image: $$BACKEND_IMAGE"; \
		TAG=$$(echo "$$BACKEND_IMAGE" | sed 's/.*://'); \
		echo "  $(YELLOW)Resolving digest for tag '$$TAG'...$(NC)"; \
		az acr repository show-tags \
			--name $(ACR_NAME) \
			--repository bible-backend \
			--detail \
			--query "[?name=='$$TAG'].{Tag: name, Digest: digest, Created: createdTime}" \
			--output table 2>/dev/null || echo "  $(YELLOW)Could not resolve digest$(NC)"; \
	else \
		echo "  $(YELLOW)Could not retrieve backend image$(NC)"; \
	fi
	@echo ""
	@echo "$(YELLOW)=== Frontend ($(CA_FRONTEND)) ===$(NC)"
	@FRONTEND_IMAGE=$$(az containerapp show \
		--name $(CA_FRONTEND) \
		--resource-group $(CA_RG) \
		--query "properties.template.containers[0].image" -o tsv 2>/dev/null) && \
	if [ -n "$$FRONTEND_IMAGE" ]; then \
		echo "  Image: $$FRONTEND_IMAGE"; \
		TAG=$$(echo "$$FRONTEND_IMAGE" | sed 's/.*://'); \
		echo "  $(YELLOW)Resolving digest for tag '$$TAG'...$(NC)"; \
		az acr repository show-tags \
			--name $(ACR_NAME) \
			--repository bible-frontend \
			--detail \
			--query "[?name=='$$TAG'].{Tag: name, Digest: digest, Created: createdTime}" \
			--output table 2>/dev/null || echo "  $(YELLOW)Could not resolve digest$(NC)"; \
	else \
		echo "  $(YELLOW)Could not retrieve frontend image$(NC)"; \
	fi
	@echo ""
	@echo "$(GREEN)✓ Deployment check complete$(NC)"

az-image-info: ## Show detailed info for a specific image (usage: make az-image-info REPO=bible-backend TAG=latest)
	@if [ -z "$(REPO)" ] || [ -z "$(TAG)" ]; then \
		echo "$(YELLOW)Usage: make az-image-info REPO=bible-backend TAG=abc1234$(NC)"; \
		echo "$(YELLOW)  REPO: bible-backend or bible-frontend$(NC)"; \
		echo "$(YELLOW)  TAG: image tag (e.g., latest, abc1234, full SHA)$(NC)"; \
		exit 1; \
	fi
	@echo "$(BLUE)Getting info for $(REPO):$(TAG)...$(NC)"
	@az acr repository show-tags \
		--name $(ACR_NAME) \
		--repository $(REPO) \
		--detail \
		--query "[?name=='$(TAG)']" \
		--output yaml 2>/dev/null || echo "$(YELLOW)Image not found$(NC)"

# ==================== Azure PostgreSQL Commands ====================

# PostgreSQL server name (using shared RESOURCE_SUFFIX)
PG_SERVER := bible-app-db-$(RESOURCE_SUFFIX)
PG_RG := bible-app-rg

# ---- Backup & restore (see docs/HOW-TO-BACKUP-RESTORE-DATABASE.md) ----
# All of these delegate to scripts/db-backup-restore.sh, which owns the safety
# guards. Connection comes from DATABASE_URL (+ PGPASSWORD), never from a
# password on the command line.
DB_TOOL := PG_RG=$(PG_RG) PG_SERVER=$(PG_SERVER) bash scripts/db-backup-restore.sh

db-backup-info: ## Show backup retention + earliest restore point (read-only)
	@$(DB_TOOL) info

db-backup: ## Logical backup to backups/ (usage: DATABASE_URL=... make db-backup [DUMP=path])
	@$(DB_TOOL) dump

db-restore-verify: ## Post-restore checklist: extensions, counts, HNSW, invalid indexes
	@$(DB_TOOL) verify

db-restore-local: ## Restore a dump into a local pgvector container (usage: make db-restore-local DUMP=backups/x.dump)
	@$(DB_TOOL) restore-local

db-restore-new-server: ## Azure PITR into a NEW server (usage: make db-restore-new-server NEW_SERVER=... RESTORE_POINT=2026-07-30T14:25:00Z)
	@$(DB_TOOL) restore-new-server

db-restore-same-server: ## DESTRUCTIVE — replace an existing database from a dump (usage: DATABASE_URL=... make db-restore-same-server DUMP=...)
	@$(DB_TOOL) restore-same-server

az-pg-add-ip: ## Add your current IP to PostgreSQL firewall
	@echo "$(BLUE)Adding your IP to PostgreSQL firewall...$(NC)"
	@MY_IP=$$(curl -4 -s ifconfig.me) && \
	echo "$(YELLOW)Your IP: $$MY_IP$(NC)" && \
	az postgres flexible-server firewall-rule create \
		--resource-group $(PG_RG) \
		--server-name $(PG_SERVER) \
		--name $(PG_SERVER) \
		--start-ip-address $$MY_IP \
		--end-ip-address $$MY_IP && \
	echo "$(GREEN)✓ Firewall rule added for IP: $$MY_IP$(NC)"

az-pg-list-rules: ## List PostgreSQL firewall rules
	@echo "$(BLUE)Listing PostgreSQL firewall rules...$(NC)"
	@az postgres flexible-server firewall-rule list \
		--resource-group $(PG_RG) \
		--server-name $(PG_SERVER) \
		--output table

az-pg-remove-ip: ## Remove a firewall rule by name (usage: make az-pg-remove-ip RULE=rule-name)
	@if [ -z "$(RULE)" ]; then \
		echo "$(YELLOW)Usage: make az-pg-remove-ip RULE=rule-name$(NC)"; \
		echo "$(YELLOW)Run 'make az-pg-list-rules' to see existing rules$(NC)"; \
		exit 1; \
	fi
	@echo "$(BLUE)Removing firewall rule: $(RULE)...$(NC)"
	@az postgres flexible-server firewall-rule delete \
		--resource-group $(PG_RG) \
		--server-name $(PG_SERVER) \
		--name $(RULE) \
		--yes && \
	echo "$(GREEN)✓ Firewall rule removed: $(RULE)$(NC)"

# ==================== Azure Container Apps Logs ====================

# Container Apps names
CA_BACKEND := bible-app-backend
CA_FRONTEND := bible-app-frontend
CA_RG := bible-app-rg

az-logs-backend: ## Tail backend container app logs
	@echo "$(BLUE)Streaming backend logs (Ctrl+C to stop)...$(NC)"
	@az containerapp logs show \
		--name $(CA_BACKEND) \
		--resource-group $(CA_RG) \
		--type console \
		--follow

az-logs-frontend: ## Tail frontend container app logs
	@echo "$(BLUE)Streaming frontend logs (Ctrl+C to stop)...$(NC)"
	@az containerapp logs show \
		--name $(CA_FRONTEND) \
		--resource-group $(CA_RG) \
		--type console \
		--follow

az-logs-backend-system: ## Tail backend system logs (startup, scaling events)
	@echo "$(BLUE)Streaming backend system logs (Ctrl+C to stop)...$(NC)"
	@az containerapp logs show \
		--name $(CA_BACKEND) \
		--resource-group $(CA_RG) \
		--type system \
		--follow

az-logs-frontend-system: ## Tail frontend system logs (startup, scaling events)
	@echo "$(BLUE)Streaming frontend system logs (Ctrl+C to stop)...$(NC)"
	@az containerapp logs show \
		--name $(CA_FRONTEND) \
		--resource-group $(CA_RG) \
		--type system \
		--follow

# ==================== Terraform Commands ====================

TF_DIR := deployment
TF_VARS := -var-file="terraform.tfvars"
TF_SECRETS := -var-file="terraform.tfvars.secrets"

tf-check-version: ## Check if local Terraform version matches pipeline version
	@echo "$(BLUE)Checking Terraform version consistency...$(NC)"
	@PIPELINE_VERSION=$$(grep 'TF_VERSION:' .github/workflows/azure-deploy.yml | head -1 | sed 's/.*"\(.*\)"/\1/'); \
	LOCAL_VERSION=$$(terraform version | head -1 | sed 's/Terraform v//'); \
	echo "  Pipeline version: $$PIPELINE_VERSION"; \
	echo "  Local version:    $$LOCAL_VERSION"; \
	if [ "$$PIPELINE_VERSION" != "$$LOCAL_VERSION" ]; then \
		echo ""; \
		echo "$(YELLOW)⚠ WARNING: Version mismatch!$(NC)"; \
		echo "$(YELLOW)  Pipeline uses Terraform $$PIPELINE_VERSION$(NC)"; \
		echo "$(YELLOW)  You have Terraform $$LOCAL_VERSION$(NC)"; \
		echo ""; \
		echo "$(YELLOW)  This may cause state file compatibility issues.$(NC)"; \
		echo "$(YELLOW)  Consider installing Terraform $$PIPELINE_VERSION or updating the pipeline.$(NC)"; \
	else \
		echo "$(GREEN)✓ Terraform versions match$(NC)"; \
	fi

tf-init: tf-check-version ## Initialize Terraform
	@echo "$(BLUE)Initializing Terraform...$(NC)"
	@if [ -f "$(TF_DIR)/backend.hcl" ]; then \
		echo "$(YELLOW)Using backend.hcl for backend configuration$(NC)"; \
		cd $(TF_DIR) && terraform init -backend-config=backend.hcl; \
	else \
		echo "$(YELLOW)Detecting storage account from Azure...$(NC)"; \
		STORAGE_ACCOUNT=$$(az storage account list --resource-group bible-app-tfstate-rg --query "[0].name" -o tsv 2>/dev/null); \
		if [ -n "$$STORAGE_ACCOUNT" ]; then \
			echo "$(YELLOW)Found storage account: $$STORAGE_ACCOUNT$(NC)"; \
			cd $(TF_DIR) && terraform init \
				-backend-config="storage_account_name=$$STORAGE_ACCOUNT" \
				-backend-config="resource_group_name=bible-app-tfstate-rg" \
				-backend-config="container_name=tfstate" \
				-backend-config="key=bible-app.tfstate"; \
		else \
			echo "$(YELLOW)Error: Could not find storage account. Create backend.hcl or ensure Azure CLI is logged in$(NC)"; \
			exit 1; \
		fi; \
	fi
	@echo "$(GREEN)✓ Terraform initialized$(NC)"

tf-plan: ## Run Terraform plan (preview changes)
	@echo "$(BLUE)Running Terraform plan...$(NC)"
	@if [ ! -f "$(TF_DIR)/terraform.tfvars.secrets" ]; then \
		echo "$(YELLOW)Warning: terraform.tfvars.secrets not found$(NC)"; \
		echo "$(YELLOW)Copy terraform.tfvars.secrets.example and fill in your secrets$(NC)"; \
		exit 1; \
	fi
	@cd $(TF_DIR) && terraform plan $(TF_VARS) $(TF_SECRETS)
	@echo "$(GREEN)✓ Terraform plan complete$(NC)"

tf-apply: ## Apply Terraform changes
	@echo "$(BLUE)Applying Terraform changes...$(NC)"
	@if [ ! -f "$(TF_DIR)/terraform.tfvars.secrets" ]; then \
		echo "$(YELLOW)Error: terraform.tfvars.secrets not found$(NC)"; \
		exit 1; \
	fi
	@cd $(TF_DIR) && terraform apply $(TF_VARS) $(TF_SECRETS)
	@echo "$(GREEN)✓ Terraform apply complete$(NC)"

tf-apply-auto: ## Apply Terraform changes (auto-approve)
	@echo "$(BLUE)Applying Terraform changes (auto-approve)...$(NC)"
	@if [ ! -f "$(TF_DIR)/terraform.tfvars.secrets" ]; then \
		echo "$(YELLOW)Error: terraform.tfvars.secrets not found$(NC)"; \
		exit 1; \
	fi
	@cd $(TF_DIR) && terraform apply $(TF_VARS) $(TF_SECRETS) -auto-approve
	@echo "$(GREEN)✓ Terraform apply complete$(NC)"

tf-destroy: ## Destroy Terraform infrastructure
	@echo "$(YELLOW)WARNING: This will destroy all infrastructure!$(NC)"
	@if [ ! -f "$(TF_DIR)/terraform.tfvars.secrets" ]; then \
		echo "$(YELLOW)Error: terraform.tfvars.secrets not found$(NC)"; \
		exit 1; \
	fi
	@cd $(TF_DIR) && terraform destroy $(TF_VARS) $(TF_SECRETS)
	@echo "$(GREEN)✓ Terraform destroy complete$(NC)"

tf-fmt: ## Format Terraform files
	@echo "$(BLUE)Formatting Terraform files...$(NC)"
	@cd $(TF_DIR) && terraform fmt -recursive
	@echo "$(GREEN)✓ Terraform files formatted$(NC)"

tf-validate: ## Validate Terraform configuration
	@echo "$(BLUE)Validating Terraform configuration...$(NC)"
	@cd $(TF_DIR) && terraform init -backend=false -upgrade > /dev/null 2>&1
	@cd $(TF_DIR) && terraform validate
	@echo "$(GREEN)✓ Terraform configuration valid$(NC)"

tf-output: ## Show Terraform outputs
	@echo "$(BLUE)Terraform outputs:$(NC)"
	@cd $(TF_DIR) && terraform output

tf-refresh: ## Refresh Terraform state
	@echo "$(BLUE)Refreshing Terraform state...$(NC)"
	@if [ ! -f "$(TF_DIR)/terraform.tfvars.secrets" ]; then \
		echo "$(YELLOW)Error: terraform.tfvars.secrets not found$(NC)"; \
		exit 1; \
	fi
	@cd $(TF_DIR) && terraform refresh $(TF_VARS) $(TF_SECRETS)
	@echo "$(GREEN)✓ Terraform state refreshed$(NC)"

tf-state-list: ## List resources in Terraform state
	@echo "$(BLUE)Resources in Terraform state:$(NC)"
	@cd $(TF_DIR) && terraform state list

repo-metrics: ## Regenerate repo productivity dashboard + report (docs/metrics/) from git history
	@echo "$(BLUE)Analyzing git history...$(NC)"
	@git fetch origin main --tags --quiet 2>/dev/null || echo "$(YELLOW)⚠ could not fetch origin/main — using local state$(NC)"
	@$(PYTHON_VERSION) tools/repo-metrics/analyze.py
	@$(PYTHON_VERSION) tools/repo-metrics/render.py
	@echo "$(GREEN)✓ docs/metrics/index.html and docs/metrics/report.md updated$(NC)"

audit-metrics: ## Regenerate audit trend dashboard + report (docs/audits/metrics/) from audit reports
	@echo "$(BLUE)Analyzing audit reports and worktree...$(NC)"
	@$(PYTHON_VERSION) tools/audit-metrics/test_analyze.py
	@$(PYTHON_VERSION) tools/audit-metrics/analyze.py
	@$(PYTHON_VERSION) tools/audit-metrics/render.py
	@echo "$(GREEN)✓ docs/audits/metrics/index.html and docs/audits/metrics/report.md updated$(NC)"
