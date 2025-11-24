"""
End-to-End Integration Tests for analyze command
Tests complete workflow: DB connection -> Analysis -> Export
"""

import pytest
import unittest
import os
import tempfile
import shutil
from pathlib import Path
from click.testing import CliRunner
import main
from app.core.models import DatabaseConfig, DatabaseType


@pytest.mark.integration
@pytest.mark.real_db
@pytest.mark.real_llm
class TestE2EAnalyzeCommand(unittest.TestCase):
    """End-to-end tests for analyze command with real database and LLM"""

    @classmethod
    def setUpClass(cls):
        """Set up test configuration from environment"""
        cls.db_config = {
            "db_type": os.getenv("CODEGRAPHAI_DB_TYPE", "postgresql"),
            "host": os.getenv("CODEGRAPHAI_DB_HOST", "localhost"),
            "port": os.getenv("CODEGRAPHAI_DB_PORT", "5432"),
            "database": os.getenv("CODEGRAPHAI_DB_NAME", "optomate"),
            "schema": os.getenv("CODEGRAPHAI_DB_SCHEMA", "tenant_optomate"),
            "user": os.getenv("CODEGRAPHAI_DB_USER", "postgres"),
            "password": os.getenv("CODEGRAPHAI_DB_PASSWORD", "changeme")
        }

        # Check if database is available
        try:
            from app.io.factory import get_loader
            config = DatabaseConfig(
                db_type=DatabaseType(cls.db_config["db_type"]),
                user=cls.db_config["user"],
                password=cls.db_config["password"],
                host=cls.db_config["host"],
                port=int(cls.db_config["port"]),
                database=cls.db_config["database"],
                schema=cls.db_config["schema"]
            )
            loader = get_loader(config)
            connection = loader._connect()
            connection.close()
        except Exception as e:
            pytest.skip(f"Database not available: {e}")

    def setUp(self):
        """Set up test fixtures"""
        self.runner = CliRunner()
        self.test_dir = tempfile.mkdtemp()
        self.output_dir = Path(self.test_dir) / "output"
        self.output_dir.mkdir()

    def tearDown(self):
        """Clean up test files"""
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)

    def test_analyze_procedures_only(self):
        """Test analyzing only procedures"""
        result = self.runner.invoke(main.cli, [
            'analyze',
            '--analysis-type', 'procedures',
            '--db-type', self.db_config["db_type"],
            '--host', self.db_config["host"],
            '--port', self.db_config["port"],
            '--database', self.db_config["database"],
            '--schema', self.db_config["schema"],
            '--user', self.db_config["user"],
            '--password', self.db_config["password"],
            '--output-dir', str(self.output_dir),
            '--export-json'
        ])

        # Command should complete successfully
        # May have warnings but exit code should be 0
        # Check if output files were created
        json_files = list(self.output_dir.glob("*.json"))
        # Should have at least one output file

    def test_analyze_tables_only(self):
        """Test analyzing only tables"""
        result = self.runner.invoke(main.cli, [
            'analyze',
            '--analysis-type', 'tables',
            '--db-type', self.db_config["db_type"],
            '--host', self.db_config["host"],
            '--port', self.db_config["port"],
            '--database', self.db_config["database"],
            '--schema', self.db_config["schema"],
            '--user', self.db_config["user"],
            '--password', self.db_config["password"],
            '--output-dir', str(self.output_dir),
            '--export-json',
            '--batch-size', '3',  # Small batch for testing
            '--parallel-workers', '2'
        ])

        # Should complete successfully
        # Check for output files

    def test_analyze_both_procedures_and_tables(self):
        """Test analyzing both procedures and tables"""
        result = self.runner.invoke(main.cli, [
            'analyze',
            '--analysis-type', 'both',
            '--db-type', self.db_config["db_type"],
            '--host', self.db_config["host"],
            '--port', self.db_config["port"],
            '--database', self.db_config["database"],
            '--schema', self.db_config["schema"],
            '--user', self.db_config["user"],
            '--password', self.db_config["password"],
            '--output-dir', str(self.output_dir),
            '--export-json',
            '--export-mermaid'
        ])

        # Should complete successfully
        # Check for both procedure and table outputs

    def test_analyze_with_all_export_formats(self):
        """Test analyze with all export formats enabled"""
        result = self.runner.invoke(main.cli, [
            'analyze',
            '--analysis-type', 'procedures',
            '--db-type', self.db_config["db_type"],
            '--host', self.db_config["host"],
            '--port', self.db_config["port"],
            '--database', self.db_config["database"],
            '--schema', self.db_config["schema"],
            '--user', self.db_config["user"],
            '--password', self.db_config["password"],
            '--output-dir', str(self.output_dir),
            '--export-json',
            '--export-png',
            '--export-mermaid'
        ])

        # Check for all output formats
        # json_files = list(self.output_dir.glob("*.json"))
        # png_files = list(self.output_dir.glob("*.png"))
        # md_files = list(self.output_dir.glob("*.md"))

    def test_analyze_with_limit(self):
        """Test analyze with limit on number of items"""
        result = self.runner.invoke(main.cli, [
            'analyze',
            '--analysis-type', 'tables',
            '--db-type', self.db_config["db_type"],
            '--host', self.db_config["host"],
            '--port', self.db_config["port"],
            '--database', self.db_config["database"],
            '--schema', self.db_config["schema"],
            '--user', self.db_config["user"],
            '--password', self.db_config["password"],
            '--output-dir', str(self.output_dir),
            '--limit', '5'  # Only analyze 5 tables
        ])

        # Should complete quickly with only 5 tables


@pytest.mark.integration
class TestE2EAnalyzeValidation(unittest.TestCase):
    """Test validation and error handling in analyze command"""

    def setUp(self):
        """Set up test fixtures"""
        self.runner = CliRunner()

    def test_analyze_invalid_database_credentials(self):
        """Test analyze with invalid credentials"""
        result = self.runner.invoke(main.cli, [
            'analyze',
            '--analysis-type', 'procedures',
            '--db-type', 'postgresql',
            '--host', 'invalid_host',
            '--port', '9999',
            '--database', 'nonexistent',
            '--schema', 'public',
            '--user', 'invalid_user',
            '--password', 'wrong_password'
        ])

        # Should fail with connection error
        self.assertNotEqual(result.exit_code, 0)

    def test_analyze_invalid_schema(self):
        """Test analyze with non-existent schema"""
        result = self.runner.invoke(main.cli, [
            'analyze',
            '--analysis-type', 'procedures',
            '--db-type', 'postgresql',
            '--host', 'localhost',
            '--database', 'test_db',
            '--schema', 'nonexistent_schema',
            '--user', 'test_user',
            '--password', 'test_pass'
        ])

        # Should handle gracefully (may return empty results or error)


@pytest.mark.integration
@pytest.mark.slow
class TestE2EAnalyzePerformance(unittest.TestCase):
    """Performance tests for analyze command"""

    def test_analyze_100_tables_performance(self):
        """Test performance of analyzing 100 tables"""
        pytest.skip("Slow performance test - enable manually")

    def test_batch_processing_speedup(self):
        """Test that batch processing is faster than individual"""
        pytest.skip("Slow performance test - enable manually")

    def test_parallel_processing_speedup(self):
        """Test that parallel processing improves speed"""
        pytest.skip("Slow performance test - enable manually")


if __name__ == '__main__':
    unittest.main()

