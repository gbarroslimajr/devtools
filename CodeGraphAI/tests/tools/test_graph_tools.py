"""
Tests for graph tools
"""

import unittest
import json
from unittest.mock import Mock
from app.tools import init_tools
from app.tools.graph_tools import query_procedure, query_table


class TestGraphTools(unittest.TestCase):
    """Test cases for graph tools"""

    def setUp(self):
        """Set up test fixtures"""
        # Create mock knowledge graph
        self.mock_graph = Mock()
        init_tools(self.mock_graph)

    def tearDown(self):
        """Clean up after tests"""
        # Reset global state
        import app.tools.graph_tools as gt
        gt._knowledge_graph = None

    def test_query_procedure_success(self):
        """Test successful procedure query"""
        # Setup mock
        self.mock_graph.get_procedure_context.return_value = {
            "name": "TEST_PROC",
            "schema": "TEST_SCHEMA",
            "full_name": "TEST_SCHEMA.TEST_PROC",
            "parameters": [{"name": "p1", "type": "VARCHAR2"}],
            "business_logic": "Test logic",
            "complexity_score": 5,
            "called_procedures": ["PROC1"],
            "called_tables": ["TABLE1"]
        }
        self.mock_graph.get_callers.return_value = {"CALLER1"}

        # Execute
        result = query_procedure.invoke({
            "procedure_name": "TEST_PROC",
            "include_dependencies": True,
            "include_callers": True
        })

        # Verify
        data = json.loads(result)
        self.assertTrue(data["success"])
        self.assertEqual(data["data"]["procedure_name"], "TEST_PROC")
        self.assertEqual(data["data"]["complexity_score"], 5)

    def test_query_procedure_not_found(self):
        """Test procedure not found"""
        # Setup mock
        self.mock_graph.get_procedure_context.return_value = None

        # Execute
        result = query_procedure.invoke({
            "procedure_name": "NONEXISTENT",
            "include_dependencies": False,
            "include_callers": False
        })

        # Verify
        data = json.loads(result)
        self.assertFalse(data["success"])
        self.assertIn("error", data)

    def test_query_table_success(self):
        """Test successful table query"""
        # Setup mock
        self.mock_graph.get_table_info.return_value = {
            "name": "TEST_TABLE",
            "schema": "TEST_SCHEMA",
            "full_name": "TEST_SCHEMA.TEST_TABLE",
            "business_purpose": "Test purpose",
            "complexity_score": 3,
            "row_count": 1000,
            "columns": [
                {
                    "name": "ID",
                    "data_type": "NUMBER",
                    "nullable": False,
                    "is_primary_key": True,
                    "is_foreign_key": False
                }
            ],
            "relationships": {}
        }

        # Execute
        result = query_table.invoke({
            "table_name": "TEST_TABLE",
            "include_columns": True,
            "include_relationships": True
        })

        # Verify
        data = json.loads(result)
        self.assertTrue(data["success"])
        self.assertEqual(data["data"]["table_name"], "TEST_TABLE")
        self.assertEqual(data["data"]["column_count"], 1)


if __name__ == '__main__':
    unittest.main()

