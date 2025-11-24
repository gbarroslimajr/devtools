"""
End-to-End Integration Tests for query command with Agent
"""

import pytest
import unittest
import os
import tempfile
import shutil
from pathlib import Path
from click.testing import CliRunner
import main


@pytest.mark.integration
@pytest.mark.real_llm
class TestE2EQueryCommand(unittest.TestCase):
    """End-to-end tests for query command with CodeAnalysisAgent"""

    def setUp(self):
        """Set up test fixtures"""
        self.runner = CliRunner()
        self.test_dir = tempfile.mkdtemp()
        self.cache_dir = Path(self.test_dir) / "cache"
        self.cache_dir.mkdir()

    def tearDown(self):
        """Clean up test files"""
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)

    def test_query_simple_question(self):
        """Test simple query to agent"""
        pytest.skip("Requires initialized knowledge graph - expensive test")

        result = self.runner.invoke(main.cli, [
            'query',
            'What does procedure X do?',
            '--cache-path', str(self.cache_dir / "kg.json")
        ])

        # Agent should respond

    def test_query_procedure_info(self):
        """Test querying procedure information"""
        pytest.skip("Requires initialized knowledge graph")

    def test_query_table_structure(self):
        """Test querying table structure"""
        pytest.skip("Requires initialized knowledge graph")

    def test_query_field_analysis(self):
        """Test querying field information"""
        pytest.skip("Requires initialized knowledge graph")


if __name__ == '__main__':
    unittest.main()

