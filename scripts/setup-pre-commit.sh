#!/bin/bash
# Setup script for pre-commit hooks
# Run this after cloning the repository

set -e

BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

VENV=".venv"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Setting up Pre-Commit Hooks${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV" ]; then
    echo -e "${BLUE}Creating virtual environment...${NC}"
    python3 -m venv $VENV
    echo -e "${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "${YELLOW}Virtual environment already exists${NC}"
fi

# Activate virtual environment
echo -e "${BLUE}Using virtual environment at $VENV${NC}"
# shellcheck source=/dev/null
source $VENV/bin/activate

# Check if pre-commit is installed
echo -e "${BLUE}Installing pre-commit...${NC}"
pip install -q pre-commit
echo -e "${GREEN}✓ Pre-commit installed${NC}"

# Install git hooks
echo -e "${BLUE}Installing git hooks...${NC}"
pre-commit install
pre-commit install --hook-type commit-msg
echo -e "${GREEN}✓ Git hooks installed${NC}"

# Install additional Python tools
echo -e "${BLUE}Installing Python development tools...${NC}"
pip install -q ruff black mypy bandit isort safety detect-secrets > /dev/null 2>&1
echo -e "${GREEN}✓ Python tools installed${NC}"

# Create secrets baseline if it doesn't exist
if [ ! -f .secrets.baseline ]; then
    echo -e "${BLUE}Creating secrets baseline...${NC}"
    detect-secrets scan --baseline .secrets.baseline
    echo -e "${GREEN}✓ Secrets baseline created${NC}"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Setup Complete! 🎉${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}Virtual environment created at: ${YELLOW}$VENV${NC}"
echo ""
echo -e "${BLUE}To activate the virtual environment:${NC}"
echo -e "  ${YELLOW}source $VENV/bin/activate${NC}"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo -e "  1. Make code changes"
echo -e "  2. Run: ${YELLOW}make format${NC} (auto-format)"
echo -e "  3. Run: ${YELLOW}git commit${NC} (hooks run automatically)"
echo ""
echo -e "${BLUE}Useful commands:${NC}"
echo -e "  ${YELLOW}make help${NC}          - Show all available commands"
echo -e "  ${YELLOW}make pre-commit${NC}    - Run hooks on all files"
echo -e "  ${YELLOW}make check-all${NC}     - Run all quality checks"
echo -e "  ${YELLOW}make format${NC}        - Auto-format all code"
echo ""
echo -e "See ${BLUE}docs/PRE_COMMIT_SETUP.md${NC} for detailed documentation"
echo ""
