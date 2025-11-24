#!/bin/bash
# Setup script for CodeGraphAI test environment

set -e  # Exit on error

echo "==================================================="
echo "CodeGraphAI - Test Environment Setup"
echo "==================================================="

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Python version
echo -e "\n${YELLOW}Checking Python version...${NC}"
python_version=$(python --version 2>&1 | awk '{print $2}')
echo "Python version: $python_version"

if ! python -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)'; then
    echo -e "${RED}Error: Python 3.8+ required${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python version OK${NC}"

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "\n${YELLOW}Warning: No virtual environment detected${NC}"
    echo "It's recommended to use a virtual environment"
    echo "Run: python -m venv venv && source venv/bin/activate"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Install test dependencies
echo -e "\n${YELLOW}Installing test dependencies...${NC}"
if [ -f "requirements-dev.txt" ]; then
    pip install -r requirements-dev.txt
    echo -e "${GREEN}✓ Test dependencies installed${NC}"
else
    echo -e "${RED}Error: requirements-dev.txt not found${NC}"
    exit 1
fi

# Check if environment.env exists
echo -e "\n${YELLOW}Checking environment configuration...${NC}"
if [ ! -f "environment.env" ]; then
    echo -e "${RED}Warning: environment.env not found${NC}"
    if [ -f "example.env" ]; then
        echo "Creating environment.env from example.env..."
        cp example.env environment.env
        echo -e "${YELLOW}Please edit environment.env with your credentials${NC}"
    else
        echo -e "${RED}Error: example.env not found either${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✓ environment.env found${NC}"
fi

# Load environment variables
if [ -f "environment.env" ]; then
    set -a
    source environment.env
    set +a
fi

# Check PostgreSQL connection (if configured)
echo -e "\n${YELLOW}Checking database connectivity...${NC}"
if [ -n "$CODEGRAPHAI_DB_HOST" ]; then
    echo "Testing connection to $CODEGRAPHAI_DB_TYPE at $CODEGRAPHAI_DB_HOST:$CODEGRAPHAI_DB_PORT..."

    if [ "$CODEGRAPHAI_DB_TYPE" == "postgresql" ]; then
        if command -v psql &> /dev/null; then
            if PGPASSWORD="$CODEGRAPHAI_DB_PASSWORD" psql -h "$CODEGRAPHAI_DB_HOST" -p "$CODEGRAPHAI_DB_PORT" -U "$CODEGRAPHAI_DB_USER" -d "$CODEGRAPHAI_DB_NAME" -c "SELECT 1" &> /dev/null; then
                echo -e "${GREEN}✓ PostgreSQL connection successful${NC}"
            else
                echo -e "${YELLOW}Warning: Could not connect to PostgreSQL${NC}"
                echo "Tests requiring real database will be skipped"
            fi
        else
            echo -e "${YELLOW}Warning: psql not found, skipping connection test${NC}"
        fi
    fi
else
    echo -e "${YELLOW}Database configuration not found in environment${NC}"
    echo "Tests requiring real database will be skipped"
fi

# Validate API keys (without exposing them)
echo -e "\n${YELLOW}Checking LLM API configuration...${NC}"
if [ -n "$CODEGRAPHAI_OPENAI_API_KEY" ]; then
    echo -e "${GREEN}✓ OpenAI API key configured${NC}"
else
    echo -e "${YELLOW}Warning: OpenAI API key not configured${NC}"
    echo "Tests requiring real LLM will be skipped"
fi

if [ -n "$CODEGRAPHAI_ANTHROPIC_API_KEY" ]; then
    echo -e "${GREEN}✓ Anthropic API key configured${NC}"
else
    echo -e "${YELLOW}Warning: Anthropic API key not configured${NC}"
fi

# Create necessary directories
echo -e "\n${YELLOW}Creating test directories...${NC}"
mkdir -p cache
mkdir -p output
mkdir -p logs
echo -e "${GREEN}✓ Directories created${NC}"

# Run environment validation tests
echo -e "\n${YELLOW}Running environment validation tests...${NC}"
if python -m pytest tests/test_env_loader.py -v; then
    echo -e "${GREEN}✓ Environment validation passed${NC}"
else
    echo -e "${RED}Warning: Some environment validations failed${NC}"
    echo "Review the errors above"
fi

echo -e "\n${GREEN}==================================================="
echo "Setup complete!"
echo "===================================================${NC}"
echo ""
echo "To run tests:"
echo "  All tests:                pytest"
echo "  Unit tests only:          pytest -m unit"
echo "  Without real DB/LLM:      pytest -m 'not real_db and not real_llm'"
echo "  With coverage:            pytest --cov=app --cov-report=html"
echo ""
echo "Note: Tests marked as 'real_db' or 'real_llm' require"
echo "configured database and API keys respectively."
echo ""

