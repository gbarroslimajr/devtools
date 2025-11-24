"""
Tests for Crawler Tools - crawl_procedure for dependency analysis
"""

import pytest
import unittest
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock
from app.tools.crawler_tools import crawl_procedure
from app.graph.knowledge_graph import CodeKnowledgeGraph
import app.tools.crawler_tools as crawler_tools


class TestCrawlProcedureTool(unittest.TestCase):
    """Test crawl_procedure tool"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = tempfile.mkdtemp()
        self.cache_path = Path(self.test_dir) / "test_kg.json"
        self.kg = CodeKnowledgeGraph(cache_path=str(self.cache_path))
        self.crawler = Mock()

        # Setup global references
        crawler_tools._knowledge_graph = self.kg
        crawler_tools._crawler = self.crawler
        crawler_tools._on_demand_analyzer = None

    def tearDown(self):
        """Clean up"""
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)
        crawler_tools._knowledge_graph = None
        crawler_tools._crawler = None

    def test_crawl_procedure_not_initialized(self):
        """Test crawl_procedure without crawler"""
        crawler_tools._crawler = None

        result = crawl_procedure.invoke({
            "procedure_name": "TEST_PROC"
        })

        data = json.loads(result)
        self.assertFalse(data["success"])
        self.assertIn("Crawler não inicializado", data["error"])

    def test_crawl_procedure_not_found(self):
        """Test crawl_procedure with non-existent procedure"""
        crawler_tools._on_demand_analyzer = Mock()
        crawler_tools._on_demand_analyzer.get_or_analyze_procedure.return_value = {
            "success": False,
            "error": "Procedure not found"
        }

        result = crawl_procedure.invoke({
            "procedure_name": "NONEXISTENT"
        })

        data = json.loads(result)
        self.assertFalse(data["success"])

    def test_crawl_procedure_success(self):
        """Test successful procedure crawling"""
        # Add procedure
        self.kg.add_procedure({
            "name": "MAIN_PROC",
            "schema": "PUBLIC"
        })

        # Mock crawler response
        mock_crawl_result = Mock()
        mock_crawl_result.dependencies_tree = {
            "name": "PUBLIC.MAIN_PROC",
            "children": [
                {"name": "PUBLIC.SUB_PROC1"},
                {"name": "PUBLIC.SUB_PROC2"}
            ]
        }
        mock_crawl_result.procedures_found = {"PUBLIC.MAIN_PROC", "PUBLIC.SUB_PROC1", "PUBLIC.SUB_PROC2"}
        mock_crawl_result.tables_found = {"PUBLIC.TABLE1", "PUBLIC.TABLE2"}
        mock_crawl_result.depth_reached = 2

        self.crawler.crawl_procedure.return_value = mock_crawl_result

        result = crawl_procedure.invoke({
            "procedure_name": "PUBLIC.MAIN_PROC",
            "max_depth": 5,
            "include_tables": True
        })

        data = json.loads(result)
        self.assertTrue(data["success"])
        self.assertEqual(data["data"]["procedure_name"], "PUBLIC.MAIN_PROC")
        self.assertEqual(len(data["data"]["procedures_found"]), 3)
        self.assertEqual(len(data["data"]["tables_found"]), 2)
        self.assertEqual(data["data"]["depth_reached"], 2)

    def test_crawl_procedure_without_tables(self):
        """Test crawling without including tables"""
        self.kg.add_procedure({
            "name": "PROC1",
            "schema": "PUBLIC"
        })

        mock_crawl_result = Mock()
        mock_crawl_result.dependencies_tree = {"name": "PUBLIC.PROC1"}
        mock_crawl_result.procedures_found = {"PUBLIC.PROC1"}
        mock_crawl_result.tables_found = {"PUBLIC.TABLE1"}
        mock_crawl_result.depth_reached = 1

        self.crawler.crawl_procedure.return_value = mock_crawl_result

        result = crawl_procedure.invoke({
            "procedure_name": "PUBLIC.PROC1",
            "max_depth": 5,
            "include_tables": False
        })

        data = json.loads(result)
        self.assertTrue(data["success"])
        self.assertEqual(len(data["data"]["tables_found"]), 0)

        # Verify crawler was called with include_tables=False
        self.crawler.crawl_procedure.assert_called_once()
        call_args = self.crawler.crawl_procedure.call_args
        self.assertFalse(call_args[1]["include_tables"])

    def test_crawl_procedure_statistics(self):
        """Test that statistics are properly calculated"""
        self.kg.add_procedure({
            "name": "PROC1",
            "schema": "PUBLIC"
        })

        mock_crawl_result = Mock()
        mock_crawl_result.dependencies_tree = {}
        mock_crawl_result.procedures_found = set([f"PUBLIC.PROC{i}" for i in range(15)])
        mock_crawl_result.tables_found = set([f"PUBLIC.TABLE{i}" for i in range(5)])
        mock_crawl_result.depth_reached = 8

        self.crawler.crawl_procedure.return_value = mock_crawl_result

        result = crawl_procedure.invoke({
            "procedure_name": "PUBLIC.PROC1"
        })

        data = json.loads(result)
        self.assertIn("statistics", data)
        stats = data["statistics"]
        self.assertEqual(stats["total_procedures"], 15)
        self.assertEqual(stats["total_tables"], 5)
        self.assertEqual(stats["depth_reached"], 8)

    def test_crawl_procedure_summary_complexity_baixa(self):
        """Test summary shows low complexity"""
        self.kg.add_procedure({
            "name": "PROC1",
            "schema": "PUBLIC"
        })

        mock_crawl_result = Mock()
        mock_crawl_result.dependencies_tree = {}
        mock_crawl_result.procedures_found = {"PUBLIC.PROC1", "PUBLIC.PROC2"}  # 2 procedures
        mock_crawl_result.tables_found = {"PUBLIC.TABLE1"}
        mock_crawl_result.depth_reached = 1

        self.crawler.crawl_procedure.return_value = mock_crawl_result

        result = crawl_procedure.invoke({
            "procedure_name": "PUBLIC.PROC1"
        })

        data = json.loads(result)
        self.assertEqual(data["summary"]["complexity"], "baixa")

    def test_crawl_procedure_summary_complexity_media(self):
        """Test summary shows medium complexity"""
        self.kg.add_procedure({
            "name": "PROC1",
            "schema": "PUBLIC"
        })

        mock_crawl_result = Mock()
        mock_crawl_result.dependencies_tree = {}
        mock_crawl_result.procedures_found = set([f"PUBLIC.PROC{i}" for i in range(7)])  # 7 procedures
        mock_crawl_result.tables_found = set()
        mock_crawl_result.depth_reached = 3

        self.crawler.crawl_procedure.return_value = mock_crawl_result

        result = crawl_procedure.invoke({
            "procedure_name": "PUBLIC.PROC1"
        })

        data = json.loads(result)
        self.assertEqual(data["summary"]["complexity"], "média")

    def test_crawl_procedure_summary_complexity_alta(self):
        """Test summary shows high complexity"""
        self.kg.add_procedure({
            "name": "PROC1",
            "schema": "PUBLIC"
        })

        mock_crawl_result = Mock()
        mock_crawl_result.dependencies_tree = {}
        mock_crawl_result.procedures_found = set([f"PUBLIC.PROC{i}" for i in range(12)])  # 12 procedures
        mock_crawl_result.tables_found = set()
        mock_crawl_result.depth_reached = 5

        self.crawler.crawl_procedure.return_value = mock_crawl_result

        result = crawl_procedure.invoke({
            "procedure_name": "PUBLIC.PROC1"
        })

        data = json.loads(result)
        self.assertEqual(data["summary"]["complexity"], "alta")

    def test_crawl_procedure_with_max_depth(self):
        """Test crawling respects max_depth parameter"""
        self.kg.add_procedure({
            "name": "PROC1",
            "schema": "PUBLIC"
        })

        mock_crawl_result = Mock()
        mock_crawl_result.dependencies_tree = {}
        mock_crawl_result.procedures_found = {"PUBLIC.PROC1"}
        mock_crawl_result.tables_found = set()
        mock_crawl_result.depth_reached = 3

        self.crawler.crawl_procedure.return_value = mock_crawl_result

        result = crawl_procedure.invoke({
            "procedure_name": "PUBLIC.PROC1",
            "max_depth": 3
        })

        # Verify crawler was called with correct max_depth
        self.crawler.crawl_procedure.assert_called_once()
        call_args = self.crawler.crawl_procedure.call_args
        self.assertEqual(call_args[1]["max_depth"], 3)

    def test_crawl_procedure_exception_handling(self):
        """Test crawl handles exceptions gracefully"""
        self.kg.add_procedure({
            "name": "PROC1",
            "schema": "PUBLIC"
        })

        self.crawler.crawl_procedure.side_effect = Exception("Crawl failed")

        result = crawl_procedure.invoke({
            "procedure_name": "PUBLIC.PROC1"
        })

        data = json.loads(result)
        self.assertFalse(data["success"])
        self.assertIn("Erro ao fazer crawling", data["error"])


class TestCrawlerToolsIntegration(unittest.TestCase):
    """Integration tests for crawler tools"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = tempfile.mkdtemp()
        self.cache_path = Path(self.test_dir) / "test_kg.json"
        self.kg = CodeKnowledgeGraph(cache_path=str(self.cache_path))
        self.crawler = Mock()

        crawler_tools._knowledge_graph = self.kg
        crawler_tools._crawler = self.crawler

    def tearDown(self):
        """Clean up"""
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)
        crawler_tools._knowledge_graph = None
        crawler_tools._crawler = None

    def test_crawl_with_circular_dependencies(self):
        """Test crawling with circular dependencies"""
        # Setup circular reference: PROC1 -> PROC2 -> PROC1
        self.kg.add_procedure({
            "name": "PROC1",
            "schema": "PUBLIC",
            "called_procedures": ["PUBLIC.PROC2"]
        })

        self.kg.add_procedure({
            "name": "PROC2",
            "schema": "PUBLIC",
            "called_procedures": ["PUBLIC.PROC1"]
        })

        mock_crawl_result = Mock()
        mock_crawl_result.dependencies_tree = {
            "name": "PUBLIC.PROC1",
            "children": [
                {
                    "name": "PUBLIC.PROC2",
                    "children": [{"name": "PUBLIC.PROC1 (circular)"}]
                }
            ]
        }
        mock_crawl_result.procedures_found = {"PUBLIC.PROC1", "PUBLIC.PROC2"}
        mock_crawl_result.tables_found = set()
        mock_crawl_result.depth_reached = 2

        self.crawler.crawl_procedure.return_value = mock_crawl_result

        result = crawl_procedure.invoke({
            "procedure_name": "PUBLIC.PROC1"
        })

        data = json.loads(result)
        self.assertTrue(data["success"])
        # Should handle circular dependencies gracefully


if __name__ == '__main__':
    unittest.main()

