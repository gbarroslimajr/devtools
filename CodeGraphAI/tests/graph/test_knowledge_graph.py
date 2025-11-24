"""
Tests for CodeKnowledgeGraph - Persistent graph structure
"""

import pytest
import unittest
import tempfile
import shutil
import json
from pathlib import Path
from app.graph.knowledge_graph import CodeKnowledgeGraph


class TestKnowledgeGraphInitialization(unittest.TestCase):
    """Test knowledge graph initialization"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = tempfile.mkdtemp()
        self.cache_path = Path(self.test_dir) / "test_kg.json"

    def tearDown(self):
        """Clean up test files"""
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)

    def test_initialization_new_graph(self):
        """Test initialization creates new graph"""
        kg = CodeKnowledgeGraph(cache_path=str(self.cache_path))

        self.assertIsNotNone(kg.graph)
        self.assertEqual(kg.graph.number_of_nodes(), 0)
        self.assertEqual(kg.graph.number_of_edges(), 0)

    def test_initialization_with_existing_cache(self):
        """Test initialization loads from existing cache"""
        # Create a cache file
        cache_data = {
            "nodes": [
                {
                    "id": "schema.proc1",
                    "node_type": "procedure",
                    "name": "proc1",
                    "schema": "schema"
                }
            ],
            "edges": [],
            "metadata": {
                "version": "1.0.0",
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00"
            }
        }

        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_path, 'w') as f:
            json.dump(cache_data, f)

        # Load graph
        kg = CodeKnowledgeGraph(cache_path=str(self.cache_path))

        self.assertEqual(kg.graph.number_of_nodes(), 1)
        self.assertTrue(kg.graph.has_node("schema.proc1"))


class TestKnowledgeGraphProcedures(unittest.TestCase):
    """Test procedure operations"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = tempfile.mkdtemp()
        self.cache_path = Path(self.test_dir) / "test_kg.json"
        self.kg = CodeKnowledgeGraph(cache_path=str(self.cache_path))

    def tearDown(self):
        """Clean up test files"""
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)

    def test_add_simple_procedure(self):
        """Test adding a simple procedure"""
        proc_info = {
            "name": "TEST_PROC",
            "schema": "PUBLIC",
            "business_logic": "Test logic",
            "complexity_score": 5
        }

        self.kg.add_procedure(proc_info)

        self.assertTrue(self.kg.graph.has_node("PUBLIC.TEST_PROC"))
        node_data = self.kg.graph.nodes["PUBLIC.TEST_PROC"]
        self.assertEqual(node_data["node_type"], "procedure")
        self.assertEqual(node_data["name"], "TEST_PROC")
        self.assertEqual(node_data["complexity_score"], 5)

    def test_add_procedure_with_dependencies(self):
        """Test adding procedure with called procedures"""
        proc_info = {
            "name": "MAIN_PROC",
            "schema": "PUBLIC",
            "called_procedures": ["PUBLIC.SUB_PROC1", "PUBLIC.SUB_PROC2"],
            "called_tables": ["PUBLIC.TABLE1"],
            "complexity_score": 8
        }

        self.kg.add_procedure(proc_info)

        # Check node exists
        self.assertTrue(self.kg.graph.has_node("PUBLIC.MAIN_PROC"))

        # Check edges
        self.assertTrue(self.kg.graph.has_edge("PUBLIC.MAIN_PROC", "PUBLIC.SUB_PROC1"))
        self.assertTrue(self.kg.graph.has_edge("PUBLIC.MAIN_PROC", "PUBLIC.SUB_PROC2"))
        self.assertTrue(self.kg.graph.has_edge("PUBLIC.MAIN_PROC", "PUBLIC.TABLE1"))

        # Check edge types
        edges = list(self.kg.graph["PUBLIC.MAIN_PROC"]["PUBLIC.SUB_PROC1"].values())
        self.assertEqual(edges[0]["edge_type"], "calls")

    def test_get_procedure_context(self):
        """Test retrieving procedure context"""
        # Add procedures
        proc1 = {
            "name": "PROC1",
            "schema": "PUBLIC",
            "called_procedures": ["PUBLIC.PROC2"],
            "called_tables": ["PUBLIC.TABLE1"],
            "complexity_score": 5,
            "business_logic": "Does something"
        }

        self.kg.add_procedure(proc1)

        # Get context
        context = self.kg.get_procedure_context("PUBLIC.PROC1")

        self.assertIsNotNone(context)
        self.assertEqual(context["name"], "PROC1")
        self.assertEqual(context["full_name"], "PUBLIC.PROC1")
        self.assertEqual(context["complexity_score"], 5)
        self.assertIn("PUBLIC.PROC2", context["called_procedures"])
        self.assertIn("PUBLIC.TABLE1", context["called_tables"])

    def test_get_procedure_context_not_found(self):
        """Test get context for non-existent procedure"""
        context = self.kg.get_procedure_context("PUBLIC.NONEXISTENT")

        self.assertIsNone(context)

    def test_get_callers(self):
        """Test finding procedures that call a given procedure"""
        # Setup: proc1 calls proc2, proc3 calls proc2
        self.kg.add_procedure({
            "name": "PROC1",
            "schema": "PUBLIC",
            "called_procedures": ["PUBLIC.PROC2"]
        })

        self.kg.add_procedure({
            "name": "PROC3",
            "schema": "PUBLIC",
            "called_procedures": ["PUBLIC.PROC2"]
        })

        callers = self.kg.get_callers("PUBLIC.PROC2")

        self.assertEqual(len(callers), 2)
        self.assertIn("PUBLIC.PROC1", callers)
        self.assertIn("PUBLIC.PROC3", callers)


class TestKnowledgeGraphTables(unittest.TestCase):
    """Test table operations"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = tempfile.mkdtemp()
        self.cache_path = Path(self.test_dir) / "test_kg.json"
        self.kg = CodeKnowledgeGraph(cache_path=str(self.cache_path))

    def tearDown(self):
        """Clean up test files"""
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)

    def test_add_table(self):
        """Test adding a table"""
        table_info = {
            "name": "USERS",
            "schema": "PUBLIC",
            "columns": [
                {
                    "name": "id",
                    "data_type": "INTEGER",
                    "nullable": False,
                    "is_primary_key": True
                },
                {
                    "name": "email",
                    "data_type": "VARCHAR",
                    "nullable": False
                }
            ],
            "business_purpose": "Stores user data",
            "row_count": 1000
        }

        self.kg.add_table(table_info)

        self.assertTrue(self.kg.graph.has_node("PUBLIC.USERS"))
        node_data = self.kg.graph.nodes["PUBLIC.USERS"]
        self.assertEqual(node_data["node_type"], "table")
        self.assertEqual(node_data["row_count"], 1000)
        self.assertEqual(len(node_data["columns"]), 2)

    def test_add_table_with_foreign_keys(self):
        """Test adding table with foreign key relationships"""
        table_info = {
            "name": "ORDERS",
            "schema": "PUBLIC",
            "columns": [{"name": "user_id", "data_type": "INTEGER"}],
            "relationships": {
                "foreign_keys": [
                    {
                        "column": "user_id",
                        "referenced_table": "PUBLIC.USERS",
                        "referenced_column": "id"
                    }
                ]
            }
        }

        self.kg.add_table(table_info)

        # Check foreign key edge
        self.assertTrue(self.kg.graph.has_edge("PUBLIC.ORDERS", "PUBLIC.USERS"))
        edges = list(self.kg.graph["PUBLIC.ORDERS"]["PUBLIC.USERS"].values())
        self.assertEqual(edges[0]["edge_type"], "foreign_key")

    def test_get_table_info(self):
        """Test retrieving table information"""
        table_info = {
            "name": "PRODUCTS",
            "schema": "PUBLIC",
            "columns": [{"name": "id", "data_type": "INTEGER"}],
            "business_purpose": "Product catalog"
        }

        self.kg.add_table(table_info)

        info = self.kg.get_table_info("PUBLIC.PRODUCTS")

        self.assertIsNotNone(info)
        self.assertEqual(info["name"], "PRODUCTS")
        self.assertEqual(info["business_purpose"], "Product catalog")


class TestKnowledgeGraphFields(unittest.TestCase):
    """Test field operations"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = tempfile.mkdtemp()
        self.cache_path = Path(self.test_dir) / "test_kg.json"
        self.kg = CodeKnowledgeGraph(cache_path=str(self.cache_path))

    def tearDown(self):
        """Clean up test files"""
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)

    def test_add_field_usage(self):
        """Test adding field usage"""
        # Add procedure first
        self.kg.add_procedure({
            "name": "PROC1",
            "schema": "PUBLIC"
        })

        # Add field usage
        field_info = {
            "field_name": "user_id",
            "procedure": "PUBLIC.PROC1",
            "operations": ["read", "write"],
            "transformations": ["UPPER(user_id)"],
            "context": "Used in WHERE clause"
        }

        self.kg.add_field_usage(field_info)

        # Verify field node exists
        self.assertTrue(self.kg.graph.has_node("field:user_id"))

        # Verify edges
        self.assertTrue(self.kg.graph.has_edge("PUBLIC.PROC1", "field:user_id"))

    def test_query_field_usage(self):
        """Test querying field usage"""
        # Setup: add procedure with field usage
        self.kg.add_procedure({
            "name": "PROC1",
            "schema": "PUBLIC",
            "fields_used": {
                "email": {
                    "operations": ["read"],
                    "transformations": ["LOWER(email)"]
                }
            }
        })

        self.kg.add_field_usage({
            "field_name": "email",
            "procedure": "PUBLIC.PROC1",
            "operations": ["read"]
        })

        # Query
        usage_list = self.kg.query_field_usage("email")

        self.assertGreater(len(usage_list), 0)
        self.assertEqual(usage_list[0]["field"], "email")

    def test_get_field_usage(self):
        """Test getting field usage summary"""
        # Add field usage
        self.kg.add_field_usage({
            "field_name": "status",
            "procedure": "PUBLIC.PROC1",
            "operations": ["read"]
        })

        self.kg.add_field_usage({
            "field_name": "status",
            "procedure": "PUBLIC.PROC2",
            "operations": ["write"]
        })

        usage = self.kg.get_field_usage("status")

        self.assertIn("read_by", usage)
        self.assertIn("written_by", usage)
        self.assertIn("procedures", usage)


class TestKnowledgeGraphPersistence(unittest.TestCase):
    """Test persistence and caching"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = tempfile.mkdtemp()
        self.cache_path = Path(self.test_dir) / "test_kg.json"

    def tearDown(self):
        """Clean up test files"""
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)

    def test_save_to_cache(self):
        """Test saving graph to cache"""
        kg = CodeKnowledgeGraph(cache_path=str(self.cache_path))

        # Add some data
        kg.add_procedure({
            "name": "PROC1",
            "schema": "PUBLIC",
            "complexity_score": 5
        })

        # Save
        kg.save_to_cache()

        # Verify file exists
        self.assertTrue(self.cache_path.exists())

        # Verify content
        with open(self.cache_path, 'r') as f:
            data = json.load(f)
            self.assertIn("nodes", data)
            self.assertIn("edges", data)
            self.assertIn("metadata", data)
            self.assertGreater(len(data["nodes"]), 0)

    def test_load_from_cache(self):
        """Test loading graph from cache"""
        # Create first graph and save
        kg1 = CodeKnowledgeGraph(cache_path=str(self.cache_path))
        kg1.add_procedure({
            "name": "PROC1",
            "schema": "PUBLIC",
            "complexity_score": 7
        })
        kg1.save_to_cache()

        # Load into new graph
        kg2 = CodeKnowledgeGraph(cache_path=str(self.cache_path))

        # Verify data loaded
        self.assertEqual(kg2.graph.number_of_nodes(), 1)
        self.assertTrue(kg2.graph.has_node("PUBLIC.PROC1"))
        node_data = kg2.graph.nodes["PUBLIC.PROC1"]
        self.assertEqual(node_data["complexity_score"], 7)

    def test_clear_cache(self):
        """Test clearing the graph"""
        kg = CodeKnowledgeGraph(cache_path=str(self.cache_path))

        # Add data
        kg.add_procedure({"name": "PROC1", "schema": "PUBLIC"})
        self.assertEqual(kg.graph.number_of_nodes(), 1)

        # Clear
        kg.clear()

        # Verify empty
        self.assertEqual(kg.graph.number_of_nodes(), 0)
        self.assertEqual(kg.graph.number_of_edges(), 0)


class TestKnowledgeGraphStatistics(unittest.TestCase):
    """Test graph statistics"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = tempfile.mkdtemp()
        self.cache_path = Path(self.test_dir) / "test_kg.json"
        self.kg = CodeKnowledgeGraph(cache_path=str(self.cache_path))

    def tearDown(self):
        """Clean up test files"""
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)

    def test_get_statistics(self):
        """Test getting graph statistics"""
        # Add some data
        self.kg.add_procedure({
            "name": "PROC1",
            "schema": "PUBLIC",
            "called_procedures": ["PUBLIC.PROC2"],
            "called_tables": ["PUBLIC.TABLE1"]
        })

        self.kg.add_table({
            "name": "TABLE1",
            "schema": "PUBLIC"
        })

        stats = self.kg.get_statistics()

        self.assertIn("total_nodes", stats)
        self.assertIn("total_edges", stats)
        self.assertIn("procedures", stats)
        self.assertIn("tables", stats)
        self.assertIn("fields", stats)

        self.assertGreater(stats["total_nodes"], 0)
        self.assertGreater(stats["procedures"], 0)


class TestKnowledgeGraphPerformance(unittest.TestCase):
    """Test graph performance with large datasets"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = tempfile.mkdtemp()
        self.cache_path = Path(self.test_dir) / "test_kg.json"
        self.kg = CodeKnowledgeGraph(cache_path=str(self.cache_path))

    def tearDown(self):
        """Clean up test files"""
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)

    def test_large_graph_performance(self):
        """Test performance with 100+ nodes"""
        # Add 100 procedures
        for i in range(100):
            self.kg.add_procedure({
                "name": f"PROC{i}",
                "schema": "PUBLIC",
                "complexity_score": i % 10
            })

        # Verify all added
        self.assertEqual(self.kg.graph.number_of_nodes(), 100)

        # Test query performance
        context = self.kg.get_procedure_context("PUBLIC.PROC50")
        self.assertIsNotNone(context)

        # Test statistics
        stats = self.kg.get_statistics()
        self.assertEqual(stats["procedures"], 100)

    def test_deep_dependency_tree(self):
        """Test graph with deep dependency chains (20+ levels)"""
        # Create chain: PROC0 -> PROC1 -> PROC2 -> ... -> PROC20
        for i in range(21):
            called = [f"PUBLIC.PROC{i+1}"] if i < 20 else []
            self.kg.add_procedure({
                "name": f"PROC{i}",
                "schema": "PUBLIC",
                "called_procedures": called
            })

        # Verify chain created
        self.assertEqual(self.kg.graph.number_of_nodes(), 21)
        self.assertEqual(self.kg.graph.number_of_edges(), 20)

        # Test navigation
        context = self.kg.get_procedure_context("PUBLIC.PROC0")
        self.assertIsNotNone(context)
        self.assertIn("PUBLIC.PROC1", context["called_procedures"])


if __name__ == '__main__':
    unittest.main()

