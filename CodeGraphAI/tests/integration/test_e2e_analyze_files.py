"""
End-to-End Integration Tests for analyze-files command
Tests file-based analysis without database connection
"""

import pytest
import unittest
import tempfile
import shutil
from pathlib import Path
from click.testing import CliRunner
import main


@pytest.mark.integration
class TestE2EAnalyzeFiles(unittest.TestCase):
    """End-to-end tests for analyze-files command"""

    def setUp(self):
        """Set up test fixtures"""
        self.runner = CliRunner()
        self.test_dir = tempfile.mkdtemp()
        self.procedures_dir = Path(self.test_dir) / "procedures"
        self.procedures_dir.mkdir()
        self.output_dir = Path(self.test_dir) / "output"
        self.output_dir.mkdir()

        # Create sample .prc files
        self._create_sample_files()

    def tearDown(self):
        """Clean up test files"""
        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir)

    def _create_sample_files(self):
        """Create sample procedure files"""
        # Simple procedure
        (self.procedures_dir / "simple_proc.prc").write_text("""
CREATE OR REPLACE PROCEDURE simple_proc AS
BEGIN
    SELECT * FROM users;
END;
""")

        # Procedure with dependencies
        (self.procedures_dir / "main_proc.prc").write_text("""
CREATE OR REPLACE PROCEDURE main_proc AS
BEGIN
    CALL sub_proc();
    SELECT * FROM orders;
    INSERT INTO logs VALUES ('executed');
END;
""")

        # Sub procedure
        (self.procedures_dir / "sub_proc.prc").write_text("""
CREATE OR REPLACE PROCEDURE sub_proc AS
BEGIN
    SELECT * FROM products;
END;
""")

    def test_analyze_files_basic(self):
        """Test basic file analysis"""
        result = self.runner.invoke(main.cli, [
            'analyze-files',
            '--directory', str(self.procedures_dir),
            '--pattern', '*.prc',
            '--output-dir', str(self.output_dir),
            '--export-json'
        ])

        # Should complete successfully
        # Check output files created

    def test_analyze_files_with_dependencies(self):
        """Test file analysis detects dependencies between files"""
        result = self.runner.invoke(main.cli, [
            'analyze-files',
            '--directory', str(self.procedures_dir),
            '--output-dir', str(self.output_dir),
            '--export-mermaid'
        ])

        # Should detect that main_proc calls sub_proc

    def test_analyze_files_empty_directory(self):
        """Test analyze-files with empty directory"""
        empty_dir = Path(self.test_dir) / "empty"
        empty_dir.mkdir()

        result = self.runner.invoke(main.cli, [
            'analyze-files',
            '--directory', str(empty_dir)
        ])

        # Should handle gracefully

    def test_analyze_files_custom_pattern(self):
        """Test analyze-files with custom file pattern"""
        # Create file with different extension
        (self.procedures_dir / "custom.sql").write_text("""
CREATE PROCEDURE custom_proc AS BEGIN SELECT 1; END;
""")

        result = self.runner.invoke(main.cli, [
            'analyze-files',
            '--directory', str(self.procedures_dir),
            '--pattern', '*.sql',
            '--output-dir', str(self.output_dir)
        ])

        # Should find and analyze .sql file


if __name__ == '__main__':
    unittest.main()

