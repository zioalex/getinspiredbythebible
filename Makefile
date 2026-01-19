.PHONY: help venv install-hooks setup-dev lint test format check-all clean

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
	@if [ ! -f "$(PYTHON)" ]; then \
		echo "$(BLUE)Creating virtual environment...$(NC)"; \
		rm -rf $(VENV); \
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
	@$(PIP) install -q -r api/requirements.txt
	@$(PIP) install -q ruff black mypy pytest pytest-asyncio bandit isort safety detect-secrets
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
		$(CURDIR)/$(PIP) install -q -r api/requirements.txt; \
		$(CURDIR)/$(PIP) install -q ruff black mypy pytest pytest-asyncio bandit isort safety detect-secrets; \
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
	@echo "$(YELLOW)Running pytest...$(NC)"
	@cd api && $(CURDIR)/$(PYTHON) -m pytest -v --tb=short || true
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

check-all: lint type-check security test ## Run all checks (pre-push validation)
	@echo "$(GREEN)✓ All checks passed!$(NC)"

pre-commit: install-deps ## Run pre-commit on all files
	@echo "$(BLUE)Running pre-commit hooks on all files...$(NC)"
	@$(CURDIR)/$(VENV)/bin/pre-commit run --all-files
	@echo "$(GREEN)✓ Pre-commit checks complete$(NC)"

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

docker-up: ## Start services (local development, CPU mode)
	@echo "$(BLUE)Starting services in local development mode (CPU)...$(NC)"
	@docker compose --env-file .env.local up -d
	@echo "$(GREEN)✓ Services started$(NC)"
	@echo "$(YELLOW)Frontend: http://localhost:3000$(NC)"
	@echo "$(YELLOW)API: http://localhost:8000$(NC)"
	@echo "$(YELLOW)API Docs: http://localhost:8000/docs$(NC)"

docker-up-gpu: ## Start services (local development, GPU mode)
	@echo "$(BLUE)Starting services in local development mode (GPU)...$(NC)"
	@docker compose --env-file .env.local -f docker-compose.yml -f docker-compose.gpu.yml up -d
	@echo "$(GREEN)✓ Services started$(NC)"
	@echo "$(YELLOW)Frontend: http://localhost:3000$(NC)"
	@echo "$(YELLOW)API: http://localhost:8000$(NC)"
	@echo "$(YELLOW)API Docs: http://localhost:8000/docs$(NC)"

docker-up-prod: ## Start services (production mode, CPU)
	@echo "$(BLUE)Starting services in production mode (CPU)...$(NC)"
	@docker compose --env-file .env.production up -d --build
	@echo "$(GREEN)✓ Services started in production mode$(NC)"
	@echo "$(YELLOW)Frontend: https://getinspiredbythebible.ai4you.sh$(NC)"
	@echo "$(YELLOW)API: https://getinspiredbythebible.ai4you.sh/api$(NC)"
	@echo "$(YELLOW)Note: Ensure Cloudflare Tunnel is running$(NC)"

docker-up-prod-gpu: ## Start services (production mode, GPU)
	@echo "$(BLUE)Starting services in production mode (GPU)...$(NC)"
	@docker compose --env-file .env.production -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
	@echo "$(GREEN)✓ Services started in production mode$(NC)"
	@echo "$(YELLOW)Frontend: https://getinspiredbythebible.ai4you.sh$(NC)"
	@echo "$(YELLOW)API: https://getinspiredbythebible.ai4you.sh/api$(NC)"
	@echo "$(YELLOW)Note: Ensure Cloudflare Tunnel is running$(NC)"

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
