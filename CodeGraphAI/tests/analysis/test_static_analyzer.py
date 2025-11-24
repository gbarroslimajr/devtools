"""
Tests for StaticCodeAnalyzer
"""

import unittest
from app.analysis.static_analyzer import StaticCodeAnalyzer
from app.analysis.models import AnalysisResult


class TestStaticCodeAnalyzer(unittest.TestCase):
    """Test cases for StaticCodeAnalyzer"""

    def setUp(self):
        """Set up test fixtures"""
        self.analyzer = StaticCodeAnalyzer()

    def test_extract_procedures(self):
        """Test procedure extraction"""
        code = """
        BEGIN
            EXEC PROC1;
            CALL PROC2();
            PKG.PROC3();
        END;
        """

        result = self.analyzer.analyze_code(code, "TEST_PROC")

        self.assertIsInstance(result, AnalysisResult)
        self.assertIn("PROC1", result.procedures)
        self.assertIn("PROC2", result.procedures)
        self.assertIn("PKG.PROC3", result.procedures)

    def test_extract_tables(self):
        """Test table extraction"""
        code = """
        SELECT * FROM TABELA1
        JOIN TABELA2 ON TABELA1.id = TABELA2.id
        WHERE EXISTS (SELECT 1 FROM TABELA3);

        INSERT INTO TABELA4 VALUES (1, 2, 3);
        UPDATE TABELA5 SET campo = 1;
        """

        result = self.analyzer.analyze_code(code, "TEST_PROC")

        self.assertIn("TABELA1", result.tables)
        self.assertIn("TABELA2", result.tables)
        self.assertIn("TABELA3", result.tables)
        self.assertIn("TABELA4", result.tables)
        self.assertIn("TABELA5", result.tables)

    def test_extract_field_usage(self):
        """Test field usage extraction"""
        code = """
        SELECT campo1, campo2
        FROM tabela
        WHERE campo3 = 'value';

        UPDATE tabela SET campo1 = 'new_value';
        """

        result = self.analyzer.analyze_code(code, "TEST_PROC")

        # Should find fields in SELECT and UPDATE
        self.assertGreater(len(result.fields), 0)

    def test_extract_parameters(self):
        """Test parameter extraction"""
        code = """
        CREATE OR REPLACE PROCEDURE test_proc(
            p_param1 IN VARCHAR2,
            p_param2 OUT NUMBER,
            p_param3 IN OUT DATE
        )
        """

        result = self.analyzer.analyze_code(code, "TEST_PROC")

        # Should extract parameters
        self.assertGreater(len(result.parameters), 0)

    def test_filter_sql_keywords(self):
        """Test that SQL keywords are filtered out"""
        code = """
        SELECT COUNT(*), SUM(valor), TO_DATE('2024-01-01', 'YYYY-MM-DD')
        FROM tabela;
        """

        result = self.analyzer.analyze_code(code, "TEST_PROC")

        # SQL functions should not be in procedures
        self.assertNotIn("COUNT", result.procedures)
        self.assertNotIn("SUM", result.procedures)
        self.assertNotIn("TO_DATE", result.procedures)


if __name__ == '__main__':
    unittest.main()

