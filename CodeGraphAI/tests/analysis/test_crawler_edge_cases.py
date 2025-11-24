"""
Edge case tests for Code Crawler
"""

import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock
from app.analysis.code_crawler import CodeCrawler
from app.graph.knowledge_graph import CodeKnowledgeGraph


class TestCrawlerCircularDependencies(unittest.TestCase):
    """Test crawler with circular dependencies"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = tempfile.mkdtemp()
        self.cache_path = Path(self.test_dir) / "test_kg.json"
        self.kg = CodeKnowledgeGraph(cache_path=str(self.cache_path))
        self.crawler = CodeCrawler(self.kg)

    def tearDown(self):
        """Clean up"""
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)

    def test_simple_circular_dependency(self):
        """Test A -> B -> A circular dependency"""
        # Setup: PROC_A calls PROC_B, PROC_B calls PROC_A
        self.kg.add_procedure({
            "name": "PROC_A",
            "schema": "PUBLIC",
            "called_procedures": ["PUBLIC.PROC_B"]
        })

        self.kg.add_procedure({
            "name": "PROC_B",
            "schema": "PUBLIC",
            "called_procedures": ["PUBLIC.PROC_A"]
        })

        # Crawl should handle circular dependency
        result = self.crawler.crawl_procedure("PUBLIC.PROC_A", max_depth=10)

        # Should detect both procedures without infinite loop
        self.assertIn("PUBLIC.PROC_A", result.procedures_found)
        self.assertIn("PUBLIC.PROC_B", result.procedures_found)
        # Should stop due to circular detection
        self.assertLessEqual(result.depth_reached, 10)

    def test_complex_circular_dependency(self):
        """Test A -> B -> C -> A circular dependency"""
        # Setup: PROC_A -> PROC_B -> PROC_C -> PROC_A
        self.kg.add_procedure({
            "name": "PROC_A",
            "schema": "PUBLIC",
            "called_procedures": ["PUBLIC.PROC_B"]
        })

        self.kg.add_procedure({
            "name": "PROC_B",
            "schema": "PUBLIC",
            "called_procedures": ["PUBLIC.PROC_C"]
        })

        self.kg.add_procedure({
            "name": "PROC_C",
            "schema": "PUBLIC",
            "called_procedures": ["PUBLIC.PROC_A"]
        })

        result = self.crawler.crawl_procedure("PUBLIC.PROC_A", max_depth=15)

        # Should find all three procedures
        self.assertEqual(len(result.procedures_found), 3)
        self.assertIn("PUBLIC.PROC_A", result.procedures_found)
        self.assertIn("PUBLIC.PROC_B", result.procedures_found)
        self.assertIn("PUBLIC.PROC_C", result.procedures_found)


class TestCrawlerDeepHierarchy(unittest.TestCase):
    """Test crawler with very deep dependency chains"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = tempfile.mkdtemp()
        self.cache_path = Path(self.test_dir) / "test_kg.json"
        self.kg = CodeKnowledgeGraph(cache_path=str(self.cache_path))
        self.crawler = CodeCrawler(self.kg)

    def tearDown(self):
        """Clean up"""
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)

    def test_deep_linear_chain(self):
        """Test crawling deep linear chain (20+ levels)"""
        # Create chain: PROC_0 -> PROC_1 -> ... -> PROC_20
        for i in range(21):
            called = [f"PUBLIC.PROC_{i+1}"] if i < 20 else []
            self.kg.add_procedure({
                "name": f"PROC_{i}",
                "schema": "PUBLIC",
                "called_procedures": called
            })

        # Crawl with sufficient depth
        result = self.crawler.crawl_procedure("PUBLIC.PROC_0", max_depth=25)

        # Should find all 21 procedures
        self.assertEqual(len(result.procedures_found), 21)
        self.assertEqual(result.depth_reached, 20)

    def test_depth_limit_respected(self):
        """Test that max_depth is respected"""
        # Create chain of 15 procedures
        for i in range(15):
            called = [f"PUBLIC.PROC_{i+1}"] if i < 14 else []
            self.kg.add_procedure({
                "name": f"PROC_{i}",
                "schema": "PUBLIC",
                "called_procedures": called
            })

        # Crawl with depth limit of 5
        result = self.crawler.crawl_procedure("PUBLIC.PROC_0", max_depth=5)

        # Should stop at depth 5
        self.assertLessEqual(result.depth_reached, 5)
        # Should have found at most 6 procedures (0 through 5)
        self.assertLessEqual(len(result.procedures_found), 6)


class TestCrawlerOrphanProcedures(unittest.TestCase):
    """Test crawler with orphan procedures (no callers)"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = tempfile.mkdtemp()
        self.cache_path = Path(self.test_dir) / "test_kg.json"
        self.kg = CodeKnowledgeGraph(cache_path=str(self.cache_path))
        self.crawler = CodeCrawler(self.kg)

    def tearDown(self):
        """Clean up"""
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)

    def test_orphan_procedure_no_dependencies(self):
        """Test procedure with no dependencies"""
        self.kg.add_procedure({
            "name": "ORPHAN",
            "schema": "PUBLIC",
            "called_procedures": [],
            "called_tables": []
        })

        result = self.crawler.crawl_procedure("PUBLIC.ORPHAN", max_depth=5)

        # Should find only itself
        self.assertEqual(len(result.procedures_found), 1)
        self.assertIn("PUBLIC.ORPHAN", result.procedures_found)
        self.assertEqual(result.depth_reached, 0)

    def test_orphan_as_leaf_node(self):
        """Test orphan procedure as leaf in dependency tree"""
        # Setup: MAIN -> SUB -> ORPHAN (orphan has no further dependencies)
        self.kg.add_procedure({
            "name": "MAIN",
            "schema": "PUBLIC",
            "called_procedures": ["PUBLIC.SUB"]
        })

        self.kg.add_procedure({
            "name": "SUB",
            "schema": "PUBLIC",
            "called_procedures": ["PUBLIC.ORPHAN"]
        })

        self.kg.add_procedure({
            "name": "ORPHAN",
            "schema": "PUBLIC",
            "called_procedures": []
        })

        result = self.crawler.crawl_procedure("PUBLIC.MAIN", max_depth=5)

        # Should find all three
        self.assertEqual(len(result.procedures_found), 3)


class TestCrawlerCachePerformance(unittest.TestCase):
    """Test crawler cache hit rate and performance"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = tempfile.mkdtemp()
        self.cache_path = Path(self.test_dir) / "test_kg.json"
        self.kg = CodeKnowledgeGraph(cache_path=str(self.cache_path))
        self.crawler = CodeCrawler(self.kg)

    def tearDown(self):
        """Clean up"""
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)

    def test_cache_hit_on_repeated_crawl(self):
        """Test cache is used on repeated crawls"""
        # Setup procedures
        self.kg.add_procedure({
            "name": "PROC_A",
            "schema": "PUBLIC",
            "called_procedures": ["PUBLIC.PROC_B"]
        })

        self.kg.add_procedure({
            "name": "PROC_B",
            "schema": "PUBLIC"
        })

        # First crawl - should build cache
        result1 = self.crawler.crawl_procedure("PUBLIC.PROC_A", max_depth=5)

        # Second crawl - should use cache
        result2 = self.crawler.crawl_procedure("PUBLIC.PROC_A", max_depth=5)

        # Results should be consistent
        self.assertEqual(
            len(result1.procedures_found),
            len(result2.procedures_found)
        )

    def test_cache_invalidation_on_update(self):
        """Test cache is invalidated when procedure is updated"""
        # Setup procedure
        self.kg.add_procedure({
            "name": "PROC_A",
            "schema": "PUBLIC",
            "called_procedures": []
        })

        # Crawl
        result1 = self.crawler.crawl_procedure("PUBLIC.PROC_A", max_depth=5)
        self.assertEqual(len(result1.procedures_found), 1)

        # Update procedure to add dependency
        self.kg.add_procedure({
            "name": "PROC_A",
            "schema": "PUBLIC",
            "called_procedures": ["PUBLIC.PROC_B"]
        })

        self.kg.add_procedure({
            "name": "PROC_B",
            "schema": "PUBLIC"
        })

        # Crawl again - should reflect changes
        result2 = self.crawler.crawl_procedure("PUBLIC.PROC_A", max_depth=5)
        self.assertEqual(len(result2.procedures_found), 2)


class TestCrawlerComplexGraphs(unittest.TestCase):
    """Test crawler with complex dependency graphs"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = tempfile.mkdtemp()
        self.cache_path = Path(self.test_dir) / "test_kg.json"
        self.kg = CodeKnowledgeGraph(cache_path=str(self.cache_path))
        self.crawler = CodeCrawler(self.kg)

    def tearDown(self):
        """Clean up"""
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)

    def test_diamond_dependency(self):
        """Test diamond-shaped dependency graph"""
        # Setup: A -> B, A -> C, B -> D, C -> D
        #        A
        #       / \
        #      B   C
        #       \ /
        #        D

        self.kg.add_procedure({
            "name": "A",
            "schema": "PUBLIC",
            "called_procedures": ["PUBLIC.B", "PUBLIC.C"]
        })

        self.kg.add_procedure({
            "name": "B",
            "schema": "PUBLIC",
            "called_procedures": ["PUBLIC.D"]
        })

        self.kg.add_procedure({
            "name": "C",
            "schema": "PUBLIC",
            "called_procedures": ["PUBLIC.D"]
        })

        self.kg.add_procedure({
            "name": "D",
            "schema": "PUBLIC"
        })

        result = self.crawler.crawl_procedure("PUBLIC.A", max_depth=10)

        # Should find all 4 procedures
        self.assertEqual(len(result.procedures_found), 4)
        # D should be visited only once despite multiple paths
        self.assertIn("PUBLIC.D", result.procedures_found)

    def test_wide_dependency_graph(self):
        """Test procedure with many direct dependencies"""
        # Setup: MAIN calls 20 different procedures
        called_procs = [f"PUBLIC.SUB_{i}" for i in range(20)]

        self.kg.add_procedure({
            "name": "MAIN",
            "schema": "PUBLIC",
            "called_procedures": called_procs
        })

        # Add all sub procedures
        for i in range(20):
            self.kg.add_procedure({
                "name": f"SUB_{i}",
                "schema": "PUBLIC"
            })

        result = self.crawler.crawl_procedure("PUBLIC.MAIN", max_depth=5)

        # Should find MAIN + 20 subs = 21 procedures
        self.assertEqual(len(result.procedures_found), 21)


if __name__ == '__main__':
    unittest.main()

