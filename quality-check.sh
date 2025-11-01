#!/bin/bash

# Code Quality Check Script
# Runs all quality checks for the codebase

set -e  # Exit on first error

echo "========================================="
echo "Running Code Quality Checks"
echo "========================================="
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track overall success
FAILED=0

# Function to run a check
run_check() {
    local name=$1
    local command=$2

    echo -e "${YELLOW}Running ${name}...${NC}"
    if eval "$command"; then
        echo -e "${GREEN}✓ ${name} passed${NC}"
        echo ""
    else
        echo -e "${RED}✗ ${name} failed${NC}"
        echo ""
        FAILED=1
    fi
}

# Run Black (check mode)
run_check "Black (code formatting check)" \
    "uv run black --check backend/ main.py"

# Run isort (check mode)
run_check "isort (import sorting check)" \
    "uv run isort --check-only backend/ main.py"

# Run Flake8 (linting)
run_check "Flake8 (linting)" \
    "uv run flake8 backend/ main.py"

# Run MyPy (type checking)
run_check "MyPy (type checking)" \
    "uv run mypy backend/ main.py"

# Run pytest
run_check "Pytest (unit tests)" \
    "cd backend && uv run pytest"

echo "========================================="
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All quality checks passed! ✓${NC}"
    exit 0
else
    echo -e "${RED}Some quality checks failed! ✗${NC}"
    exit 1
fi
