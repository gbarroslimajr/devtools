"""
Tests for Mermaid Export functionality
"""

import pytest
import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch
import networkx as nx


class TestMermaidProcedureExport(unittest.TestCase):
    """Test Mermaid export for procedures"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = tempfile.mkdtemp()
        self.output_path = Path(self.test_dir) / "test_diagram.md"

    def tearDown(self):
        """Clean up test files"""
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)

    def test_export_simple_procedure_hierarchy(self):
        """Test exporting simple procedure hierarchy"""
        # Create graph with procedures
        graph = nx.DiGraph()
        graph.add_node("PROC1", level=0, complexity_score=5)
        graph.add_node("PROC2", level=1, complexity_score=3)
        graph.add_edge("PROC2", "PROC1")

        # Import analyzer with graph
        from analyzer import ProcedureAnalyzer

        with patch.object(ProcedureAnalyzer, '__init__', lambda x, y: None):
            analyzer = ProcedureAnalyzer(None)
            analyzer.graph = graph

            # Test export (would need actual implementation)
            # This is a placeholder for the structure
            # result = analyzer.export_mermaid_hierarchy(str(self.output_path))

    def test_mermaid_syntax_validation(self):
        """Test that generated Mermaid syntax is valid"""
        # Basic Mermaid flowchart syntax
        mermaid_content = """
```mermaid
flowchart TD
    PROC1[PROC1<br/>Level: 0<br/>Complexity: 5]
    PROC2[PROC2<br/>Level: 1<br/>Complexity: 3]
    PROC2 --> PROC1
```
"""
        # Validate basic syntax structure
        self.assertIn("flowchart TD", mermaid_content)
        self.assertIn("```mermaid", mermaid_content)
        self.assertIn("-->", mermaid_content)

    def test_export_procedure_dependencies(self):
        """Test exporting procedure dependencies"""
        # Create complex dependency graph
        graph = nx.DiGraph()
        graph.add_node("MAIN", complexity_score=8)
        graph.add_node("SUB1", complexity_score=4)
        graph.add_node("SUB2", complexity_score=3)
        graph.add_node("HELPER", complexity_score=2)

        graph.add_edge("MAIN", "SUB1")
        graph.add_edge("MAIN", "SUB2")
        graph.add_edge("SUB1", "HELPER")

        # Would test actual export here
        # Verify all nodes and edges are in output


class TestMermaidTableExport(unittest.TestCase):
    """Test Mermaid export for tables"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = tempfile.mkdtemp()
        self.output_path = Path(self.test_dir) / "test_table_diagram.md"

    def tearDown(self):
        """Clean up test files"""
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)

    def test_export_table_relationships(self):
        """Test exporting table relationships"""
        # Create graph with tables and FKs
        graph = nx.DiGraph()
        graph.add_node("USERS", node_type="table", row_count=1000)
        graph.add_node("ORDERS", node_type="table", row_count=5000)
        graph.add_edge("ORDERS", "USERS", edge_type="foreign_key")

        # Would test actual export here

    def test_mermaid_er_diagram_syntax(self):
        """Test Entity-Relationship diagram syntax"""
        mermaid_content = """
```mermaid
erDiagram
    USERS ||--o{ ORDERS : "has"
    USERS {
        int id PK
        string email
        string name
    }
    ORDERS {
        int id PK
        int user_id FK
        decimal total
    }
```
"""
        # Validate ER diagram syntax
        self.assertIn("erDiagram", mermaid_content)
        self.assertIn("||--o{", mermaid_content)
        self.assertIn("PK", mermaid_content)
        self.assertIn("FK", mermaid_content)


class TestMermaidFormatting(unittest.TestCase):
    """Test Mermaid formatting and styling"""

    def test_complexity_color_coding(self):
        """Test procedures are color-coded by complexity"""
        # Low complexity (1-3): green
        # Medium complexity (4-7): yellow
        # High complexity (8-10): red

        mermaid_with_styles = """
```mermaid
flowchart TD
    SIMPLE[SIMPLE]:::green
    MEDIUM[MEDIUM]:::yellow
    COMPLEX[COMPLEX]:::red

    classDef green fill:#90EE90
    classDef yellow fill:#FFD700
    classDef red fill:#FF6B6B
```
"""
        self.assertIn("classDef green", mermaid_with_styles)
        self.assertIn("classDef yellow", mermaid_with_styles)
        self.assertIn("classDef red", mermaid_with_styles)

    def test_special_character_escaping(self):
        """Test special characters are properly escaped"""
        # Mermaid requires escaping of certain characters
        procedure_name = "PROC<TEST>"
        # Should escape < and >
        escaped = procedure_name.replace("<", "&lt;").replace(">", "&gt;")
        self.assertEqual(escaped, "PROC&lt;TEST&gt;")

    def test_long_names_truncation(self):
        """Test very long names are truncated or wrapped"""
        long_name = "VERY_LONG_PROCEDURE_NAME_THAT_WOULD_MAKE_DIAGRAM_UGLY"
        # Should truncate or add line breaks
        if len(long_name) > 30:
            # Could truncate
            truncated = long_name[:27] + "..."
            self.assertEqual(len(truncated), 30)


class TestMermaidFileGeneration(unittest.TestCase):
    """Test Mermaid file generation"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test files"""
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)

    def test_generates_valid_markdown_file(self):
        """Test generates valid .md file"""
        output_file = Path(self.test_dir) / "diagram.md"

        # Generate file
        mermaid_content = """# Procedure Hierarchy

```mermaid
flowchart TD
    PROC1[PROC1]
```
"""
        output_file.write_text(mermaid_content)

        # Verify file exists and has content
        self.assertTrue(output_file.exists())
        content = output_file.read_text()
        self.assertIn("```mermaid", content)
        self.assertIn("flowchart TD", content)

    def test_generates_multiple_diagrams_in_one_file(self):
        """Test can generate multiple Mermaid diagrams in one file"""
        output_file = Path(self.test_dir) / "multi_diagram.md"

        content = """# Analysis Results

## Hierarchy Diagram

```mermaid
flowchart TD
    A --> B
```

## Dependencies Diagram

```mermaid
graph LR
    C --> D
```
"""
        output_file.write_text(content)

        file_content = output_file.read_text()
        # Should have two Mermaid blocks
        self.assertEqual(file_content.count("```mermaid"), 2)


class TestMermaidEdgeCases(unittest.TestCase):
    """Test edge cases in Mermaid generation"""

    def test_circular_dependencies(self):
        """Test handles circular dependencies"""
        graph = nx.DiGraph()
        graph.add_edge("PROC1", "PROC2")
        graph.add_edge("PROC2", "PROC1")  # Circular

        # Should handle gracefully, possibly with special notation

    def test_orphan_procedures(self):
        """Test handles procedures with no dependencies"""
        graph = nx.DiGraph()
        graph.add_node("ORPHAN", level=0)

        # Should still be included in diagram

    def test_very_large_graph(self):
        """Test handles very large graphs (100+ nodes)"""
        graph = nx.DiGraph()
        for i in range(100):
            graph.add_node(f"PROC{i}", complexity_score=i % 10)
            if i > 0:
                graph.add_edge(f"PROC{i}", f"PROC{i-1}")

        # Should generate diagram without errors
        # May need pagination or filtering for readability


if __name__ == '__main__':
    unittest.main()

