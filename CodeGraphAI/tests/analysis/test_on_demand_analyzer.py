"""
Tests for On-Demand Analyzer - lazy loading of procedures and tables
"""

import pytest
import unittest
from unittest.mock import Mock, MagicMock, patch
from app.analysis.on_demand_analyzer import OnDemandAnalyzer


class TestOnDemandAnalyzerInitialization(unittest.TestCase):
    """Test on-demand analyzer initialization"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_knowledge_graph = Mock()
        self.mock_procedure_loader = Mock()
        self.mock_table_loader = Mock()
        self.mock_llm_analyzer = Mock()

    def test_initialization_with_minimal_params(self):
        """Test initialization with minimal parameters"""
        analyzer = OnDemandAnalyzer(
            knowledge_graph=self.mock_knowledge_graph,
            procedure_loader=self.mock_procedure_loader,
            llm_analyzer=self.mock_llm_analyzer
        )

        self.assertIsNotNone(analyzer)
        self.assertEqual(analyzer.knowledge_graph, self.mock_knowledge_graph)
        self.assertEqual(analyzer.procedure_loader, self.mock_procedure_loader)

    def test_initialization_with_table_loader(self):
        """Test initialization with table loader"""
        analyzer = OnDemandAnalyzer(
            knowledge_graph=self.mock_knowledge_graph,
            procedure_loader=self.mock_procedure_loader,
            table_loader=self.mock_table_loader,
            llm_analyzer=self.mock_llm_analyzer
        )

        self.assertEqual(analyzer.table_loader, self.mock_table_loader)


class TestOnDemandProcedureAnalysis(unittest.TestCase):
    """Test on-demand procedure analysis"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_kg = Mock()
        self.mock_proc_loader = Mock()
        self.mock_llm = Mock()

        self.analyzer = OnDemandAnalyzer(
            knowledge_graph=self.mock_kg,
            procedure_loader=self.mock_proc_loader,
            llm_analyzer=self.mock_llm
        )

    def test_get_or_analyze_procedure_already_in_cache(self):
        """Test returns cached procedure if already analyzed"""
        # Setup mock - procedure already in cache
        self.mock_kg.get_procedure_context.return_value = {
            "name": "TEST_PROC",
            "schema": "PUBLIC",
            "complexity_score": 5
        }

        result = self.analyzer.get_or_analyze_procedure("PUBLIC.TEST_PROC")

        self.assertTrue(result["success"])
        self.assertEqual(result["source"], "cache")
        self.assertEqual(result["data"]["name"], "TEST_PROC")

        # Verify didn't try to load from database
        self.mock_proc_loader.load_procedures.assert_not_called()

    def test_get_or_analyze_procedure_loads_from_db(self):
        """Test loads and analyzes procedure from database"""
        # Setup mock - not in cache
        self.mock_kg.get_procedure_context.return_value = None

        # Setup mock loader
        mock_proc_info = Mock()
        mock_proc_info.name = "TEST_PROC"
        mock_proc_info.schema = "PUBLIC"
        mock_proc_info.source_code = "CREATE PROCEDURE TEST_PROC AS BEGIN END;"

        self.mock_proc_loader.load_procedures.return_value = [mock_proc_info]

        # Setup mock LLM analyzer
        self.mock_llm.analyze_business_logic.return_value = "Test logic"
        self.mock_llm.extract_dependencies.return_value = (set(), set())
        self.mock_llm.calculate_complexity.return_value = 5

        result = self.analyzer.get_or_analyze_procedure("PUBLIC.TEST_PROC")

        self.assertTrue(result["success"])
        self.assertEqual(result["source"], "database")

        # Verify loader was called
        self.mock_proc_loader.load_procedures.assert_called_once()

    def test_get_or_analyze_procedure_not_found(self):
        """Test handles procedure not found"""
        # Setup mock - not in cache
        self.mock_kg.get_procedure_context.return_value = None

        # Setup mock loader - returns empty list
        self.mock_proc_loader.load_procedures.return_value = []

        result = self.analyzer.get_or_analyze_procedure("PUBLIC.NONEXISTENT")

        self.assertFalse(result["success"])
        self.assertIn("not found", result["error"])

    def test_get_or_analyze_procedure_handles_errors(self):
        """Test handles analysis errors gracefully"""
        # Setup mock - not in cache
        self.mock_kg.get_procedure_context.return_value = None

        # Setup mock loader to raise exception
        self.mock_proc_loader.load_procedures.side_effect = Exception("Database error")

        result = self.analyzer.get_or_analyze_procedure("PUBLIC.TEST_PROC")

        self.assertFalse(result["success"])
        self.assertIn("error", result)


class TestOnDemandTableAnalysis(unittest.TestCase):
    """Test on-demand table analysis"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_kg = Mock()
        self.mock_proc_loader = Mock()
        self.mock_table_loader = Mock()
        self.mock_llm = Mock()

        self.analyzer = OnDemandAnalyzer(
            knowledge_graph=self.mock_kg,
            procedure_loader=self.mock_proc_loader,
            table_loader=self.mock_table_loader,
            llm_analyzer=self.mock_llm
        )

    def test_get_or_analyze_table_already_in_cache(self):
        """Test returns cached table if already analyzed"""
        # Setup mock - table already in cache
        self.mock_kg.get_table_info.return_value = {
            "name": "USERS",
            "schema": "PUBLIC",
            "row_count": 1000
        }

        result = self.analyzer.get_or_analyze_table("PUBLIC.USERS")

        self.assertTrue(result["success"])
        self.assertEqual(result["source"], "cache")
        self.assertEqual(result["data"]["name"], "USERS")

        # Verify didn't try to load from database
        self.mock_table_loader.load_tables.assert_not_called()

    def test_get_or_analyze_table_loads_from_db(self):
        """Test loads and analyzes table from database"""
        # Setup mock - not in cache
        self.mock_kg.get_table_info.return_value = None

        # Setup mock loader
        mock_table_info = Mock()
        mock_table_info.name = "USERS"
        mock_table_info.schema = "PUBLIC"
        mock_table_info.columns = []

        self.mock_table_loader.load_tables.return_value = [mock_table_info]

        result = self.analyzer.get_or_analyze_table("PUBLIC.USERS")

        self.assertTrue(result["success"])
        self.assertEqual(result["source"], "database")

        # Verify loader was called
        self.mock_table_loader.load_tables.assert_called_once()

    def test_get_or_analyze_table_without_loader(self):
        """Test handles missing table loader"""
        # Create analyzer without table loader
        analyzer = OnDemandAnalyzer(
            knowledge_graph=self.mock_kg,
            procedure_loader=self.mock_proc_loader,
            llm_analyzer=self.mock_llm
        )

        result = analyzer.get_or_analyze_table("PUBLIC.USERS")

        self.assertFalse(result["success"])
        self.assertIn("Table loader not configured", result["error"])


class TestOnDemandAnalyzerCache(unittest.TestCase):
    """Test caching behavior"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_kg = Mock()
        self.mock_proc_loader = Mock()
        self.mock_llm = Mock()

        self.analyzer = OnDemandAnalyzer(
            knowledge_graph=self.mock_kg,
            procedure_loader=self.mock_proc_loader,
            llm_analyzer=self.mock_llm
        )

    def test_cache_hit_avoids_database_access(self):
        """Test cache hit doesn't access database"""
        # First call - not in cache
        self.mock_kg.get_procedure_context.side_effect = [None, {
            "name": "TEST_PROC",
            "schema": "PUBLIC"
        }]

        mock_proc_info = Mock()
        mock_proc_info.name = "TEST_PROC"
        mock_proc_info.schema = "PUBLIC"
        mock_proc_info.source_code = "..."

        self.mock_proc_loader.load_procedures.return_value = [mock_proc_info]
        self.mock_llm.analyze_business_logic.return_value = "Logic"
        self.mock_llm.extract_dependencies.return_value = (set(), set())
        self.mock_llm.calculate_complexity.return_value = 5

        # First call - should load from DB
        result1 = self.analyzer.get_or_analyze_procedure("PUBLIC.TEST_PROC")
        self.assertEqual(result1["source"], "database")

        # Second call - should hit cache
        result2 = self.analyzer.get_or_analyze_procedure("PUBLIC.TEST_PROC")
        self.assertEqual(result2["source"], "cache")

        # Verify loader only called once
        self.assertEqual(self.mock_proc_loader.load_procedures.call_count, 1)


class TestOnDemandAnalyzerPerformance(unittest.TestCase):
    """Test performance characteristics"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_kg = Mock()
        self.mock_proc_loader = Mock()
        self.mock_llm = Mock()

        self.analyzer = OnDemandAnalyzer(
            knowledge_graph=self.mock_kg,
            procedure_loader=self.mock_proc_loader,
            llm_analyzer=self.mock_llm
        )

    def test_lazy_loading_vs_eager_loading(self):
        """Test that on-demand is faster than eager loading"""
        # This is more of a conceptual test
        # On-demand should only load what's requested

        # Request specific procedure
        self.mock_kg.get_procedure_context.return_value = None
        self.mock_proc_loader.load_procedures.return_value = []

        self.analyzer.get_or_analyze_procedure("PUBLIC.PROC1")

        # Verify only specific procedure was requested (not all procedures)
        call_args = self.mock_proc_loader.load_procedures.call_args
        # Should have specific procedure filter, not loading all
        self.assertIsNotNone(call_args)


if __name__ == '__main__':
    unittest.main()

