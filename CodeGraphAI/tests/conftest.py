"""
Fixtures compartilhadas para testes
"""

import pytest
from unittest.mock import Mock, MagicMock
from analyzer import LLMAnalyzer, ProcedureAnalyzer


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

