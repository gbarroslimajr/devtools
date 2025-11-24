"""
Tests for Field Tools - analyze_field and trace_field_flow
"""

import pytest
import unittest
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch
from app.tools.field_tools import analyze_field, trace_field_flow
from app.graph.knowledge_graph import CodeKnowledgeGraph
from app.analysis.code_crawler import CodeCrawler
import app.tools.field_tools as field_tools


class TestAnalyzeFieldTool(unittest.TestCase):
    """Test analyze_field tool"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = tempfile.mkdtemp()
        self.cache_path = Path(self.test_dir) / "test_kg.json"
        self.kg = CodeKnowledgeGraph(cache_path=str(self.cache_path))

        # Setup global reference
        field_tools._knowledge_graph = self.kg
        field_tools._on_demand_analyzer = None

    def tearDown(self):
        """Clean up"""
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)
        field_tools._knowledge_graph = None

    def test_analyze_field_not_initialized(self):
        """Test analyze_field without knowledge graph"""
        field_tools._knowledge_graph = None

        result = analyze_field.invoke({
            "field_name": "test_field"
        })

        data = json.loads(result)
        self.assertFalse(data["success"])
        self.assertIn("Knowledge graph não inicializado", data["error"])

    def test_analyze_field_not_found(self):
        """Test analyze_field for non-existent field"""
        result = analyze_field.invoke({
            "field_name": "nonexistent_field"
        })

        data = json.loads(result)
        self.assertFalse(data["success"])
        self.assertIn("não encontrado", data["error"])

    def test_analyze_field_basic(self):
        """Test basic field analysis"""
        # Add procedure with field usage
        self.kg.add_procedure({
            "name": "PROC1",
            "schema": "PUBLIC",
            "fields_used": {
                "user_id": {
                    "operations": ["read"],
                    "transformations": []
                }
            }
        })

        self.kg.add_field_usage({
            "field_name": "user_id",
            "procedure": "PUBLIC.PROC1",
            "operations": ["read"]
        })

        result = analyze_field.invoke({
            "field_name": "user_id"
        })

        data = json.loads(result)
        self.assertTrue(data["success"])
        self.assertEqual(data["data"]["field_name"], "user_id")
        self.assertIn("usage", data["data"])
        self.assertIn("detailed_usage", data["data"])

    def test_analyze_field_with_procedure_filter(self):
        """Test field analysis with procedure name filter"""
        # Add two procedures using the same field
        self.kg.add_procedure({
            "name": "PROC1",
            "schema": "PUBLIC"
        })

        self.kg.add_procedure({
            "name": "PROC2",
            "schema": "PUBLIC"
        })

        self.kg.add_field_usage({
            "field_name": "email",
            "procedure": "PUBLIC.PROC1",
            "operations": ["read"]
        })

        self.kg.add_field_usage({
            "field_name": "email",
            "procedure": "PUBLIC.PROC2",
            "operations": ["write"]
        })

        result = analyze_field.invoke({
            "field_name": "email",
            "procedure_name": "PUBLIC.PROC1"
        })

        data = json.loads(result)
        self.assertTrue(data["success"])
        self.assertGreater(data["data"]["usage_count"], 0)

    def test_analyze_field_with_table_definition(self):
        """Test field analysis with table definition"""
        # Add table with column
        self.kg.add_table({
            "name": "USERS",
            "schema": "PUBLIC",
            "columns": [
                {
                    "name": "user_id",
                    "data_type": "INTEGER",
                    "nullable": False,
                    "is_primary_key": True,
                    "is_foreign_key": False
                }
            ]
        })

        # Add field usage
        self.kg.add_procedure({
            "name": "PROC1",
            "schema": "PUBLIC"
        })

        self.kg.add_field_usage({
            "field_name": "user_id",
            "procedure": "PUBLIC.PROC1",
            "operations": ["read"]
        })

        result = analyze_field.invoke({
            "field_name": "user_id",
            "table_name": "PUBLIC.USERS"
        })

        data = json.loads(result)
        self.assertTrue(data["success"])
        self.assertIsNotNone(data["data"]["definition"])
        self.assertEqual(data["data"]["definition"]["data_type"], "INTEGER")
        self.assertTrue(data["data"]["definition"]["is_primary_key"])

    def test_analyze_field_with_transformations(self):
        """Test field analysis showing transformations"""
        self.kg.add_procedure({
            "name": "PROC1",
            "schema": "PUBLIC"
        })

        self.kg.add_field_usage({
            "field_name": "email",
            "procedure": "PUBLIC.PROC1",
            "operations": ["read", "write"],
            "transformations": ["LOWER(email)", "TRIM(email)"]
        })

        result = analyze_field.invoke({
            "field_name": "email"
        })

        data = json.loads(result)
        self.assertTrue(data["success"])
        usage_list = data["data"]["detailed_usage"]
        self.assertGreater(len(usage_list), 0)
        self.assertIn("operations", usage_list[0])
        self.assertIn("transformations", usage_list[0])


class TestTraceFieldFlowTool(unittest.TestCase):
    """Test trace_field_flow tool"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = tempfile.mkdtemp()
        self.cache_path = Path(self.test_dir) / "test_kg.json"
        self.kg = CodeKnowledgeGraph(cache_path=str(self.cache_path))
        self.crawler = Mock()

        # Setup global references
        field_tools._knowledge_graph = self.kg
        field_tools._crawler = self.crawler
        field_tools._on_demand_analyzer = None

    def tearDown(self):
        """Clean up"""
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)
        field_tools._knowledge_graph = None
        field_tools._crawler = None

    def test_trace_field_flow_not_initialized(self):
        """Test trace_field_flow without crawler"""
        field_tools._crawler = None

        result = trace_field_flow.invoke({
            "field_name": "test_field",
            "start_procedure": "PROC1"
        })

        data = json.loads(result)
        self.assertFalse(data["success"])
        self.assertIn("Crawler não inicializado", data["error"])

    def test_trace_field_flow_procedure_not_found(self):
        """Test trace_field_flow with non-existent procedure"""
        # Mock crawler to return error
        field_tools._on_demand_analyzer = Mock()
        field_tools._on_demand_analyzer.get_or_analyze_procedure.return_value = {
            "success": False,
            "error": "Procedure not found"
        }

        result = trace_field_flow.invoke({
            "field_name": "test_field",
            "start_procedure": "NONEXISTENT"
        })

        data = json.loads(result)
        self.assertFalse(data["success"])

    def test_trace_field_flow_success(self):
        """Test successful field flow tracing"""
        # Add procedure
        self.kg.add_procedure({
            "name": "PROC1",
            "schema": "PUBLIC"
        })

        # Mock crawler response
        mock_trace_result = Mock()
        mock_trace_result.field_name = "user_id"
        mock_trace_result.path = [
            Mock(procedure="PUBLIC.PROC1", operation="read", depth=0, context="SELECT"),
            Mock(procedure="PUBLIC.PROC2", operation="write", depth=1, context="INSERT")
        ]
        mock_trace_result.sources = ["PUBLIC.TABLE1"]
        mock_trace_result.destinations = ["PUBLIC.TABLE2"]
        mock_trace_result.transformations = ["UPPER(user_id)"]

        self.crawler.trace_field.return_value = mock_trace_result

        result = trace_field_flow.invoke({
            "field_name": "user_id",
            "start_procedure": "PUBLIC.PROC1",
            "max_depth": 10
        })

        data = json.loads(result)
        self.assertTrue(data["success"])
        self.assertEqual(data["data"]["field_name"], "user_id")
        self.assertEqual(data["data"]["path_length"], 2)
        self.assertEqual(len(data["data"]["path"]), 2)
        self.assertEqual(data["data"]["path"][0]["procedure"], "PUBLIC.PROC1")
        self.assertEqual(data["data"]["path"][0]["operation"], "read")

    def test_trace_field_flow_with_custom_max_depth(self):
        """Test trace with custom max_depth"""
        self.kg.add_procedure({
            "name": "PROC1",
            "schema": "PUBLIC"
        })

        mock_trace_result = Mock()
        mock_trace_result.field_name = "status"
        mock_trace_result.path = []
        mock_trace_result.sources = []
        mock_trace_result.destinations = []
        mock_trace_result.transformations = []

        self.crawler.trace_field.return_value = mock_trace_result

        result = trace_field_flow.invoke({
            "field_name": "status",
            "start_procedure": "PUBLIC.PROC1",
            "max_depth": 5
        })

        # Verify max_depth was passed to crawler
        self.crawler.trace_field.assert_called_once()
        call_args = self.crawler.trace_field.call_args
        self.assertEqual(call_args[1]["max_depth"], 5)

    def test_trace_field_flow_summary_format(self):
        """Test that summary is properly formatted"""
        self.kg.add_procedure({
            "name": "PROC1",
            "schema": "PUBLIC"
        })

        mock_trace_result = Mock()
        mock_trace_result.field_name = "email"
        mock_trace_result.path = [Mock(procedure="PROC1", operation="read", depth=0, context="WHERE")]
        mock_trace_result.sources = ["TABLE1"]
        mock_trace_result.destinations = ["TABLE2"]
        mock_trace_result.transformations = ["LOWER(email)"]

        self.crawler.trace_field.return_value = mock_trace_result

        result = trace_field_flow.invoke({
            "field_name": "email",
            "start_procedure": "PUBLIC.PROC1"
        })

        data = json.loads(result)
        self.assertIn("summary", data)
        summary = data["summary"]
        self.assertEqual(summary["field"], "email")
        self.assertEqual(summary["starts_at"], "PUBLIC.PROC1")
        self.assertEqual(summary["comes_from"], ["TABLE1"])
        self.assertEqual(summary["goes_to"], ["TABLE2"])
        self.assertTrue(summary["has_transformations"])


class TestFieldToolsIntegration(unittest.TestCase):
    """Integration tests for field tools"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = tempfile.mkdtemp()
        self.cache_path = Path(self.test_dir) / "test_kg.json"
        self.kg = CodeKnowledgeGraph(cache_path=str(self.cache_path))

        field_tools._knowledge_graph = self.kg

    def tearDown(self):
        """Clean up"""
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)
        field_tools._knowledge_graph = None

    def test_analyze_field_multiple_procedures(self):
        """Test analyzing field used in multiple procedures"""
        # Setup: field used in 3 different procedures
        for i in range(3):
            self.kg.add_procedure({
                "name": f"PROC{i}",
                "schema": "PUBLIC"
            })

            self.kg.add_field_usage({
                "field_name": "status",
                "procedure": f"PUBLIC.PROC{i}",
                "operations": ["read"] if i % 2 == 0 else ["write"]
            })

        result = analyze_field.invoke({
            "field_name": "status"
        })

        data = json.loads(result)
        self.assertTrue(data["success"])
        self.assertEqual(data["data"]["usage_count"], 3)
        self.assertGreater(len(data["data"]["detailed_usage"]), 0)


if __name__ == '__main__':
    unittest.main()

