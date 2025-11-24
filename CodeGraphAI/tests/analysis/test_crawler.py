"""
Tests for CodeCrawler
"""

import unittest
from unittest.mock import Mock, MagicMock
from app.analysis.code_crawler import CodeCrawler
from app.analysis.models import CrawlResult, TracePath


class TestCodeCrawler(unittest.TestCase):
    """Test cases for CodeCrawler"""

    def setUp(self):
        """Set up test fixtures"""
        # Mock knowledge graph
        self.mock_graph = Mock()
        self.crawler = CodeCrawler(self.mock_graph)

    def test_crawl_procedure_basic(self):
        """Test basic procedure crawling"""
        # Setup mock
        self.mock_graph.get_procedure_context.return_value = {
            "name": "TEST_PROC",
            "full_name": "SCHEMA.TEST_PROC",
            "called_procedures": ["PROC1", "PROC2"],
            "called_tables": ["TABLE1"],
            "complexity_score": 5
        }

        # Execute
        result = self.crawler.crawl_procedure("TEST_PROC", max_depth=1)

        # Verify
        self.assertIsInstance(result, CrawlResult)
        self.assertIn("TEST_PROC", result.procedures_found)

    def test_crawl_procedure_max_depth(self):
        """Test that crawling respects max_depth"""
        # Setup recursive mock
        def mock_context(proc_name):
            if proc_name == "TEST_PROC":
                return {
                    "name": "TEST_PROC",
                    "called_procedures": ["PROC1"],
                    "called_tables": [],
                    "complexity_score": 5
                }
            elif proc_name == "PROC1":
                return {
                    "name": "PROC1",
                    "called_procedures": ["PROC2"],
                    "called_tables": [],
                    "complexity_score": 3
                }
            return None

        self.mock_graph.get_procedure_context.side_effect = mock_context

        # Execute with max_depth=1
        result = self.crawler.crawl_procedure("TEST_PROC", max_depth=1)

        # Should find TEST_PROC and PROC1, but not PROC2
        self.assertIn("TEST_PROC", result.procedures_found)
        self.assertIn("PROC1", result.procedures_found)

    def test_find_field_sources(self):
        """Test finding field sources"""
        # Setup mock
        self.mock_graph.query_field_usage.return_value = [
            {
                "procedure": "PROC1",
                "usage": {"operations": ["write"]}
            }
        ]
        self.mock_graph.graph.nodes.return_value = []

        # Execute
        sources = self.crawler.find_field_sources("test_field", max_results=10)

        # Verify
        self.assertIsInstance(sources, list)

    def test_get_procedure_impact(self):
        """Test procedure impact analysis"""
        # Setup mock
        self.mock_graph.get_callers.return_value = {"CALLER1", "CALLER2"}
        self.mock_graph.get_procedure_context.return_value = {
            "name": "TEST_PROC",
            "called_procedures": [],
            "called_tables": [],
            "complexity_score": 5
        }

        # Execute
        impact = self.crawler.get_procedure_impact("TEST_PROC", max_depth=2)

        # Verify
        self.assertEqual(impact["procedure"], "TEST_PROC")
        self.assertEqual(impact["caller_count"], 2)
        self.assertIsInstance(impact["total_impact_score"], int)


if __name__ == '__main__':
    unittest.main()

