# CodeGraphAI - Test Suite Documentation

## Overview

This comprehensive test suite covers all features of CodeGraphAI, including new features (Agent, Knowledge Graph, Tools) and regression tests for existing functionality.

**Total Test Files:** ~30
**Estimated Test Cases:** 200-250
**Expected Coverage:** 85-90%

## Quick Start

### Setup Test Environment

```bash
# Run setup script
./tests/setup_test_env.sh

# Or manually:
pip install -r requirements-dev.txt
cp example.env environment.env
# Edit environment.env with your credentials
```

### Run Tests

```bash
# All tests
pytest

# Unit tests only (fast, no external dependencies)
pytest -m unit

# Skip expensive tests (real DB + real LLM)
pytest -m "not real_db and not real_llm"

# Integration tests only
pytest -m integration

# With coverage report
pytest --cov=app --cov-report=html --cov-report=term

# Verbose output
pytest -v

# Run specific test file
pytest tests/agents/test_code_analysis_agent.py

# Run specific test
pytest tests/agents/test_code_analysis_agent.py::TestCodeAnalysisAgentInitialization::test_agent_initialization_with_minimal_params
```

## Test Organization

### Test Structure

```
tests/
├── agents/                      # CodeAnalysisAgent tests
│   └── test_code_analysis_agent.py
├── analysis/                    # Static analyzer and crawler
│   ├── test_crawler.py         (existing)
│   ├── test_crawler_edge_cases.py (new)
│   ├── test_on_demand_analyzer.py (new)
│   ├── test_static_analyzer.py (existing)
│   └── test_static_analyzer_edge_cases.py (new)
├── cli/                         # CLI command tests
│   └── test_main.py
├── core/                        # Core functionality
│   └── test_dry_mode.py
├── export/                      # Export functionality
│   └── test_mermaid_export.py
├── graph/                       # Knowledge Graph
│   └── test_knowledge_graph.py
├── integration/                 # End-to-end tests
│   ├── test_e2e_analyze.py
│   ├── test_e2e_analyze_files.py
│   ├── test_e2e_connection.py
│   └── test_e2e_query.py
├── io/                          # Database loaders
│   ├── test_base.py
│   ├── test_connection.py
│   ├── test_file_loader.py
│   ├── test_postgres_integration.py
│   ├── test_postgres_loader_extended.py (new)
│   ├── test_postgres_loader_no_duplicates.py
│   └── test_table_loaders.py
├── llm/                         # LLM integrations
│   ├── test_anthropic_integration.py
│   ├── test_genfactory_client.py
│   ├── test_openai_integration.py
│   ├── test_openai_real_api.py (new - expensive!)
│   ├── test_token_callback.py
│   └── test_toon_converter.py
├── performance/                 # Performance tests
│   └── test_batch_parallel.py
├── tools/                       # LangChain tools
│   ├── test_crawler_tools.py
│   ├── test_field_tools.py
│   ├── test_graph_tools.py
│   └── test_query_tools.py
├── conftest.py                  # Shared fixtures
├── pytest.ini                   # Pytest configuration
├── test_env_loader.py          # Environment validation
├── setup_test_env.sh           # Setup script
├── cleanup_test_data.sh        # Cleanup script
└── README.md                    # This file
```

## Test Markers

Tests are organized using pytest markers for easy filtering:

- `@pytest.mark.unit` - Fast unit tests, no external dependencies
- `@pytest.mark.integration` - Integration tests, may require setup
- `@pytest.mark.real_db` - Requires real database connection
- `@pytest.mark.real_llm` - Requires real LLM API (**costs money!**)
- `@pytest.mark.slow` - Tests taking > 30 seconds
- `@pytest.mark.expensive` - Tests consuming significant resources or money

### Example Usage

```bash
# Run only unit tests (fast)
pytest -m unit

# Run integration tests
pytest -m integration

# Skip expensive tests
pytest -m "not expensive"

# Run only real database tests
pytest -m real_db

# Skip real LLM tests (avoid API costs)
pytest -m "not real_llm"
```

## Test Categories

### 1. New Features Tests (Priority: High)

#### CodeAnalysisAgent
- **File:** `tests/agents/test_code_analysis_agent.py`
- **Coverage:** Agent initialization, query processing, tool selection, batch analysis
- **Dependencies:** Mocked LLM, no real API calls by default

#### CodeKnowledgeGraph
- **File:** `tests/graph/test_knowledge_graph.py`
- **Coverage:** Graph operations, persistence, queries, statistics, performance
- **Tests:** 100+ procedures, deep hierarchies (20+ levels)

#### LangChain Tools
- **Files:**
  - `tests/tools/test_field_tools.py`
  - `tests/tools/test_crawler_tools.py`
  - `tests/tools/test_query_tools.py`
- **Coverage:** Field analysis, dependency crawling, SQL query execution

#### CLI Commands
- **File:** `tests/cli/test_main.py`
- **Coverage:** All CLI commands (analyze, analyze-files, query, test-connection)
- **Testing:** Argument parsing, error handling, command execution

### 2. Regression Tests

#### Database Loaders
- **Files:** `tests/io/test_*_loader_extended.py`
- **Coverage:** PostgreSQL, Oracle, MSSQL, MySQL (with real databases)
- **Features:** Procedures, tables, foreign keys, indexes, types

#### LLM Analyzers
- **File:** `tests/llm/test_openai_real_api.py` (**expensive!**)
- **Coverage:** Real API calls, dependency extraction, complexity calculation
- **Cost:** ~$0.01-0.10 per test run (estimate)

#### Static Analyzer
- **File:** `tests/analysis/test_static_analyzer_edge_cases.py`
- **Coverage:** Complex queries, dynamic SQL, comments, special characters

#### Code Crawler
- **File:** `tests/analysis/test_crawler_edge_cases.py`
- **Coverage:** Circular dependencies, deep hierarchies, orphan procedures

### 3. Integration Tests (End-to-End)

#### Full Workflow Tests
- **Files:** `tests/integration/test_e2e_*.py`
- **Coverage:** Complete workflows from DB connection to export
- **Requirements:** Real database + real LLM (configurable)

## Configuration

### Environment Variables

Tests use environment variables from `environment.env`:

```bash
# Database Configuration
CODEGRAPHAI_DB_TYPE=postgresql
CODEGRAPHAI_DB_HOST=localhost
CODEGRAPHAI_DB_PORT=5432
CODEGRAPHAI_DB_NAME=optomate
CODEGRAPHAI_DB_SCHEMA=tenant_optomate
CODEGRAPHAI_DB_USER=postgres
CODEGRAPHAI_DB_PASSWORD=changeme

# LLM Configuration
CODEGRAPHAI_LLM_MODE=api
CODEGRAPHAI_LLM_PROVIDER=openai
CODEGRAPHAI_OPENAI_API_KEY=your_api_key_here
CODEGRAPHAI_OPENAI_MODEL=o3-mini
CODEGRAPHAI_ANTHROPIC_API_KEY=your_api_key_here
```

### Fixtures

Global fixtures are defined in `conftest.py`:

- `real_postgres_connection` - Real PostgreSQL connection
- `real_llm_client` - Real OpenAI client (costs money!)
- `sample_knowledge_graph` - Pre-populated graph for testing
- `temp_output_dir` - Temporary output directory
- `sample_prc_files` - Sample procedure files

## Cost Considerations

### Tests That Cost Money

Tests marked with `@pytest.mark.real_llm` make real API calls:

**Estimated Costs (OpenAI o3-mini):**
- Single procedure analysis: ~$0.001-0.005
- Full test suite with real LLM: ~$0.10-0.50
- Integration tests: ~$0.05-0.20

**To avoid costs:**
```bash
pytest -m "not real_llm"
```

### Database Requirements

Tests marked with `@pytest.mark.real_db` require:
- PostgreSQL 11+ (primary)
- Oracle 11g+ (optional)
- SQL Server 2016+ (optional)
- MySQL 8.0+ (optional)

## Coverage Reports

### Generate Coverage

```bash
# HTML report (opens in browser)
pytest --cov=app --cov-report=html
open htmlcov/index.html

# Terminal report
pytest --cov=app --cov-report=term

# Both
pytest --cov=app --cov-report=html --cov-report=term
```

### Coverage Goals

- **Overall:** > 85%
- **New features:** > 90%
- **Core modules:** > 95%
- **Integration:** > 70%

## Troubleshooting

### Common Issues

#### 1. Database Connection Failed
```bash
# Check PostgreSQL is running
pg_isready -h localhost -p 5432

# Test connection manually
psql -h localhost -U postgres -d optomate

# Solution: Update environment.env with correct credentials
```

#### 2. Import Errors
```bash
# Install missing dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Check Python path
echo $PYTHONPATH
export PYTHONPATH=$PYTHONPATH:$(pwd)
```

#### 3. API Key Missing
```bash
# Check environment variables
echo $CODEGRAPHAI_OPENAI_API_KEY

# Solution: Add to environment.env
CODEGRAPHAI_OPENAI_API_KEY=sk-your-key-here
```

#### 4. Slow Tests
```bash
# Skip slow tests
pytest -m "not slow"

# Run parallel (requires pytest-xdist)
pip install pytest-xdist
pytest -n auto
```

## Continuous Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:13
        env:
          POSTGRES_PASSWORD: test_pass
        options: >-
          --health-cmd pg_isready
          --health-interval 10s

    steps:
    - uses: actions/checkout@v2
    - uses: actions/setup-python@v2
      with:
        python-version: '3.8'

    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install -r requirements-dev.txt

    - name: Run tests
      run: pytest -m "not real_llm" --cov=app
      env:
        CODEGRAPHAI_DB_HOST: localhost
        CODEGRAPHAI_DB_USER: postgres
        CODEGRAPHAI_DB_PASSWORD: test_pass
```

## Best Practices

1. **Always run unit tests before committing:**
   ```bash
   pytest -m unit
   ```

2. **Use markers appropriately:**
   - Mark expensive tests as `@pytest.mark.expensive`
   - Mark slow tests as `@pytest.mark.slow`

3. **Keep tests isolated:**
   - Use fixtures for setup/teardown
   - Don't rely on test execution order

4. **Mock external dependencies:**
   - Mock LLM calls for unit tests
   - Use real APIs only for integration tests

5. **Document test purpose:**
   - Clear test names
   - Docstrings explaining what's being tested

## Maintenance

### Adding New Tests

1. Create test file in appropriate directory
2. Use existing fixtures from `conftest.py`
3. Add appropriate markers
4. Update this README if adding new test category

### Cleaning Up

```bash
# Remove test artifacts
./tests/cleanup_test_data.sh

# Or manually:
rm -rf cache/* output/* logs/* .pytest_cache htmlcov .coverage
```

## Support

For issues or questions:
1. Check this README
2. Review test output for specific errors
3. Check `environment.env` configuration
4. Run environment validation: `pytest tests/test_env_loader.py`

## Summary

- **Total Tests:** ~200-250
- **Execution Time:**
  - Unit tests: ~2-3 minutes
  - Full suite (no real API): ~5-8 minutes
  - With real DB + LLM: ~15-20 minutes
- **Coverage Goal:** 85-90%
- **Cost (with real LLM):** ~$0.10-0.50 per full run

Happy Testing! 🚀

