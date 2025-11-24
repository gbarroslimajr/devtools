#!/bin/bash
# Cleanup script for CodeGraphAI test data

set -e

echo "==================================================="
echo "CodeGraphAI - Test Data Cleanup"
echo "==================================================="

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Confirm cleanup
echo -e "\n${YELLOW}This will remove:${NC}"
echo "  - Temporary test files"
echo "  - Knowledge graph cache"
echo "  - Test output files"
echo "  - Test logs"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cleanup cancelled"
    exit 0
fi

# Remove cache directory
if [ -d "cache" ]; then
    echo -e "\n${YELLOW}Removing cache directory...${NC}"
    rm -rf cache/*
    echo -e "${GREEN}✓ Cache cleared${NC}"
fi

# Remove output files
if [ -d "output" ]; then
    echo -e "\n${YELLOW}Removing output directory...${NC}"
    rm -rf output/*
    echo -e "${GREEN}✓ Output cleared${NC}"
fi

# Remove test logs
if [ -d "logs" ]; then
    echo -e "\n${YELLOW}Removing log files...${NC}"
    rm -rf logs/*
    echo -e "${GREEN}✓ Logs cleared${NC}"
fi

# Remove pytest cache
if [ -d ".pytest_cache" ]; then
    echo -e "\n${YELLOW}Removing pytest cache...${NC}"
    rm -rf .pytest_cache
    echo -e "${GREEN}✓ Pytest cache cleared${NC}"
fi

# Remove Python cache
echo -e "\n${YELLOW}Removing Python cache files...${NC}"
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
find . -type f -name "*.pyo" -delete 2>/dev/null || true
echo -e "${GREEN}✓ Python cache cleared${NC}"

# Remove coverage reports
if [ -d "htmlcov" ]; then
    echo -e "\n${YELLOW}Removing coverage reports...${NC}"
    rm -rf htmlcov
    echo -e "${GREEN}✓ Coverage reports cleared${NC}"
fi

if [ -f ".coverage" ]; then
    rm -f .coverage
fi

# Remove any temporary test databases (if any)
# Add custom cleanup here if needed

echo -e "\n${GREEN}==================================================="
echo "Cleanup complete!"
echo "===================================================${NC}"
echo ""
echo "All test data has been removed."
echo "Run ./tests/setup_test_env.sh to setup again."
echo ""

