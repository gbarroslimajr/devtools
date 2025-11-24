"""
Fixtures compartilhadas para testes
"""

import pytest
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, MagicMock
from analyzer import LLMAnalyzer, ProcedureAnalyzer
from app.core.models import DatabaseConfig, DatabaseType
from app.graph.knowledge_graph import CodeKnowledgeGraph


# ==================== Basic Fixtures ====================

@pytest.fixture
def sample_procedure_code():
    """Código de exemplo de uma procedure Oracle"""
    return """
    CREATE OR REPLACE PROCEDURE TEST_PROC (
        p_id IN NUMBER,
        p_name OUT VARCHAR2
    ) AS
    BEGIN
        SELECT nome INTO p_name FROM clientes WHERE id = p_id;
        UPDATE clientes SET ultima_consulta = SYSDATE WHERE id = p_id;
    END;
    """


@pytest.fixture
def sample_procedures_dict():
    """Dict com procedures de exemplo"""
    return {
        "PROC1": """
        CREATE OR REPLACE PROCEDURE PROC1 AS
        BEGIN
            INSERT INTO tabela1 VALUES (1, 'test');
        END;
        """,
        "PROC2": """
        CREATE OR REPLACE PROCEDURE PROC2 AS
        BEGIN
            PROC1();
            SELECT * FROM tabela2;
        END;
        """
    }


@pytest.fixture
def mock_llm_analyzer():
    """Mock do LLMAnalyzer para testes rápidos"""
    mock = Mock(spec=LLMAnalyzer)
    mock.analyze_business_logic.return_value = "Procedure de teste"
    mock.extract_dependencies.return_value = (set(), set())
    mock.calculate_complexity.return_value = 5
    return mock


@pytest.fixture
def mock_procedure_analyzer(mock_llm_analyzer):
    """Mock do ProcedureAnalyzer"""
    return ProcedureAnalyzer(mock_llm_analyzer)


# ==================== Database Fixtures ====================

@pytest.fixture
def real_postgres_connection():
    """Real PostgreSQL connection from environment variables"""
    config = DatabaseConfig(
        db_type=DatabaseType.POSTGRESQL,
        user=os.getenv("CODEGRAPHAI_DB_USER", "postgres"),
        password=os.getenv("CODEGRAPHAI_DB_PASSWORD", "changeme"),
        host=os.getenv("CODEGRAPHAI_DB_HOST", "localhost"),
        port=int(os.getenv("CODEGRAPHAI_DB_PORT", "5432")),
        database=os.getenv("CODEGRAPHAI_DB_NAME", "optomate"),
        schema=os.getenv("CODEGRAPHAI_DB_SCHEMA", "tenant_optomate")
    )
    return config


@pytest.fixture
def mock_database_config():
    """Mock database configuration"""
    return DatabaseConfig(
        db_type=DatabaseType.POSTGRESQL,
        user="test_user",
        password="test_pass",
        host="localhost",
        port=5432,
        database="test_db",
        schema="public"
    )


# ==================== LLM Fixtures ====================

@pytest.fixture
def real_llm_client():
    """Real OpenAI client from environment (costs money!)"""
    api_key = os.getenv("CODEGRAPHAI_OPENAI_API_KEY")
    model = os.getenv("CODEGRAPHAI_OPENAI_MODEL", "o3-mini")

    if not api_key:
        pytest.skip("OpenAI API key not configured")

    from analyzer import LLMAnalyzer
    return LLMAnalyzer(
        model_name=model,
        device="api",
        api_key=api_key,
        use_local=False
    )


# ==================== Knowledge Graph Fixtures ====================

@pytest.fixture
def temp_knowledge_graph(tmp_path):
    """Temporary knowledge graph for testing"""
    cache_path = tmp_path / "test_kg.json"
    kg = CodeKnowledgeGraph(cache_path=str(cache_path))
    yield kg
    # Cleanup happens automatically with tmp_path


@pytest.fixture
def sample_knowledge_graph(tmp_path):
    """Knowledge graph populated with sample data"""
    cache_path = tmp_path / "sample_kg.json"
    kg = CodeKnowledgeGraph(cache_path=str(cache_path))

    # Add sample procedures
    kg.add_procedure({
        "name": "PROC1",
        "schema": "PUBLIC",
        "complexity_score": 3,
        "called_procedures": ["PUBLIC.PROC2"],
        "called_tables": ["PUBLIC.TABLE1"]
    })

    kg.add_procedure({
        "name": "PROC2",
        "schema": "PUBLIC",
        "complexity_score": 5,
        "called_tables": ["PUBLIC.TABLE2"]
    })

    # Add sample tables
    kg.add_table({
        "name": "TABLE1",
        "schema": "PUBLIC",
        "columns": [
            {"name": "id", "data_type": "INTEGER", "nullable": False},
            {"name": "name", "data_type": "VARCHAR", "nullable": True}
        ]
    })

    kg.add_table({
        "name": "TABLE2",
        "schema": "PUBLIC",
        "columns": [
            {"name": "id", "data_type": "INTEGER", "nullable": False}
        ]
    })

    yield kg


# ==================== File System Fixtures ====================

@pytest.fixture
def temp_output_dir(tmp_path):
    """Temporary directory for output files"""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    yield output_dir


@pytest.fixture
def sample_prc_files(tmp_path):
    """Directory with sample .prc files"""
    prc_dir = tmp_path / "procedures"
    prc_dir.mkdir()

    # Create sample files
    (prc_dir / "simple.prc").write_text("""
CREATE PROCEDURE simple_proc AS
BEGIN
    SELECT * FROM users;
END;
""")

    (prc_dir / "complex.prc").write_text("""
CREATE PROCEDURE complex_proc AS
BEGIN
    CALL helper_proc();
    UPDATE orders SET status = 'processed';
END;
""")

    yield prc_dir


# ==================== Environment Fixtures ====================

@pytest.fixture(scope="session")
def test_env_config():
    """Load and validate test environment configuration"""
    config = {
        "db_type": os.getenv("CODEGRAPHAI_DB_TYPE", "postgresql"),
        "db_host": os.getenv("CODEGRAPHAI_DB_HOST", "localhost"),
        "db_port": os.getenv("CODEGRAPHAI_DB_PORT", "5432"),
        "db_name": os.getenv("CODEGRAPHAI_DB_NAME", "optomate"),
        "db_schema": os.getenv("CODEGRAPHAI_DB_SCHEMA", "tenant_optomate"),
        "db_user": os.getenv("CODEGRAPHAI_DB_USER", "postgres"),
        "db_password": os.getenv("CODEGRAPHAI_DB_PASSWORD", "changeme"),
        "openai_api_key": os.getenv("CODEGRAPHAI_OPENAI_API_KEY"),
        "openai_model": os.getenv("CODEGRAPHAI_OPENAI_MODEL", "o3-mini"),
        "anthropic_api_key": os.getenv("CODEGRAPHAI_ANTHROPIC_API_KEY"),
        "anthropic_model": os.getenv("CODEGRAPHAI_ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")
    }
    return config

