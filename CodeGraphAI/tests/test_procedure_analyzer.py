"""
Testes para ProcedureAnalyzer
"""

import pytest
import json
import tempfile
from pathlib import Path
from analyzer import ProcedureAnalyzer, ProcedureInfo
from tests.conftest import mock_llm_analyzer, sample_procedure_code


class TestProcedureAnalyzer:
    """Testes para ProcedureAnalyzer"""

    def test_extract_parameters_from_code(self, mock_llm_analyzer):
        """Testa extração de parâmetros"""
        analyzer = ProcedureAnalyzer(mock_llm_analyzer)

        code = """
        CREATE OR REPLACE PROCEDURE TEST_PROC (
            p_id IN NUMBER,
            p_name OUT VARCHAR2,
            p_value IN OUT NUMBER
        ) AS
        BEGIN
            NULL;
        END;
        """

        params = analyzer._extract_parameters_from_code(code)

        assert len(params) == 3
        assert params[0]['name'] == 'p_id'
        assert params[0]['direction'] == 'IN'
        assert params[1]['direction'] == 'OUT'
        assert params[2]['direction'] == 'IN OUT'

    def test_calculate_dependency_levels_simple(self, mock_llm_analyzer):
        """Testa cálculo de níveis de dependência simples"""
        analyzer = ProcedureAnalyzer(mock_llm_analyzer)

        # Cria procedures de teste
        proc1 = ProcedureInfo(
            name="PROC1",
            schema="TEST",
            source_code="BEGIN NULL; END;",
            parameters=[],
            called_procedures=set(),
            called_tables=set(),
            business_logic="Test",
            complexity_score=1,
            dependencies_level=0
        )

        proc2 = ProcedureInfo(
            name="PROC2",
            schema="TEST",
            source_code="BEGIN PROC1(); END;",
            parameters=[],
            called_procedures={"PROC1"},
            called_tables=set(),
            business_logic="Test",
            complexity_score=2,
            dependencies_level=0
        )

        analyzer.procedures = {"PROC1": proc1, "PROC2": proc2}
        analyzer.dependency_graph.add_node("PROC1")
        analyzer.dependency_graph.add_node("PROC2")
        analyzer.dependency_graph.add_edge("PROC2", "PROC1")

        analyzer._calculate_dependency_levels()

        assert analyzer.procedures["PROC1"].dependencies_level == 0
        assert analyzer.procedures["PROC2"].dependencies_level == 1

    def test_get_procedure_hierarchy(self, mock_llm_analyzer):
        """Testa obtenção de hierarquia"""
        analyzer = ProcedureAnalyzer(mock_llm_analyzer)

        # Cria procedures com diferentes níveis
        for i in range(3):
            proc = ProcedureInfo(
                name=f"PROC{i}",
                schema="TEST",
                source_code="BEGIN NULL; END;",
                parameters=[],
                called_procedures=set(),
                called_tables=set(),
                business_logic="Test",
                complexity_score=1,
                dependencies_level=i
            )
            analyzer.procedures[f"PROC{i}"] = proc

        hierarchy = analyzer.get_procedure_hierarchy()

        assert 0 in hierarchy
        assert 1 in hierarchy
        assert 2 in hierarchy
        assert len(hierarchy[0]) == 1
        assert len(hierarchy[1]) == 1
        assert len(hierarchy[2]) == 1

    def test_export_results(self, mock_llm_analyzer):
        """Testa exportação de resultados para JSON"""
        analyzer = ProcedureAnalyzer(mock_llm_analyzer)

        # Cria procedure de teste
        proc = ProcedureInfo(
            name="TEST_PROC",
            schema="TEST",
            source_code="BEGIN NULL; END;",
            parameters=[],
            called_procedures={"OTHER_PROC"},
            called_tables={"TEST_TABLE"},
            business_logic="Test procedure",
            complexity_score=5,
            dependencies_level=0
        )
        analyzer.procedures["TEST_PROC"] = proc

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            output_file = f.name

        try:
            analyzer.export_results(output_file)

            # Verifica que arquivo foi criado e é JSON válido
            assert Path(output_file).exists()

            with open(output_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            assert 'procedures' in data
            assert 'hierarchy' in data
            assert 'statistics' in data
            assert 'TEST_PROC' in data['procedures']
            assert data['procedures']['TEST_PROC']['complexity_score'] == 5

        finally:
            Path(output_file).unlink()

    def test_export_results_empty(self, mock_llm_analyzer):
        """Testa erro ao exportar sem procedures"""
        analyzer = ProcedureAnalyzer(mock_llm_analyzer)

        with pytest.raises(Exception):  # ExportError
            analyzer.export_results("test.json")

