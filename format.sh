#!/bin/bash

# Code Formatting Script
# Automatically formats code with black and isort

set -e  # Exit on first error

echo "========================================="
echo "Formatting Code"
echo "========================================="
echo ""

# Color codes for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Run isort first (import sorting)
echo -e "${YELLOW}Sorting imports with isort...${NC}"
uv run isort backend/ main.py
echo -e "${GREEN}✓ Imports sorted${NC}"
echo ""

# Run black (code formatting)
echo -e "${YELLOW}Formatting code with black...${NC}"
uv run black backend/ main.py
echo -e "${GREEN}✓ Code formatted${NC}"
echo ""

echo "========================================="
echo -e "${GREEN}Code formatting complete! ✓${NC}"
