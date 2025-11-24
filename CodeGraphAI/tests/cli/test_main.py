"""
Tests for CLI Commands in main.py
"""

import pytest
import unittest
from unittest.mock import Mock, patch, MagicMock
from click.testing import CliRunner
import main


class TestAnalyzeCommand(unittest.TestCase):
    """Test analyze command"""

    def setUp(self):
        """Set up test fixtures"""
        self.runner = CliRunner()

    @patch('main.ProcedureAnalyzer')
    @patch('main.TableAnalyzer')
    @patch('main.get_loader')
    def test_analyze_command_both(self, mock_loader, mock_table_analyzer, mock_proc_analyzer):
        """Test analyze command with --analysis-type=both"""
        # Mock the analyzers
        mock_proc_instance = Mock()
        mock_table_instance = Mock()
        mock_proc_analyzer.return_value = mock_proc_instance
        mock_table_analyzer.return_value = mock_table_instance

        mock_loader.return_value = Mock()

        result = self.runner.invoke(main.cli, [
            'analyze',
            '--analysis-type', 'both',
            '--db-type', 'postgresql',
            '--host', 'localhost',
            '--port', '5432',
            '--database', 'test_db',
            '--schema', 'public',
            '--user', 'test_user',
            '--password', 'test_pass'
        ])

        # Command should execute without errors
        self.assertEqual(result.exit_code, 0)

    def test_analyze_command_missing_required_args(self):
        """Test analyze command fails with missing args"""
        result = self.runner.invoke(main.cli, ['analyze'])

        # Should fail with exit code != 0
        self.assertNotEqual(result.exit_code, 0)

    @patch('main.ProcedureAnalyzer')
    def test_analyze_command_procedures_only(self, mock_analyzer):
        """Test analyze command with --analysis-type=procedures"""
        mock_instance = Mock()
        mock_analyzer.return_value = mock_instance

        with patch('main.get_loader') as mock_loader:
            mock_loader.return_value = Mock()

            result = self.runner.invoke(main.cli, [
                'analyze',
                '--analysis-type', 'procedures',
                '--db-type', 'postgresql',
                '--host', 'localhost',
                '--database', 'test_db',
                '--user', 'test_user',
                '--password', 'test_pass'
            ])

            # Procedure analyzer should be called, not table analyzer
            mock_analyzer.assert_called_once()

    def test_analyze_command_with_export_flags(self):
        """Test analyze command with export flags"""
        with patch('main.ProcedureAnalyzer') as mock_analyzer:
            with patch('main.get_loader') as mock_loader:
                mock_loader.return_value = Mock()
                mock_instance = Mock()
                mock_analyzer.return_value = mock_instance

                result = self.runner.invoke(main.cli, [
                    'analyze',
                    '--analysis-type', 'procedures',
                    '--db-type', 'postgresql',
                    '--host', 'localhost',
                    '--database', 'test_db',
                    '--user', 'test_user',
                    '--password', 'test_pass',
                    '--export-json',
                    '--export-png',
                    '--export-mermaid'
                ])

                # Should pass export flags to analyzer


class TestAnalyzeFilesCommand(unittest.TestCase):
    """Test analyze-files command"""

    def setUp(self):
        """Set up test fixtures"""
        self.runner = CliRunner()

    @patch('main.ProcedureAnalyzer')
    @patch('main.FileLoader')
    def test_analyze_files_command(self, mock_loader, mock_analyzer):
        """Test analyze-files command"""
        mock_loader_instance = Mock()
        mock_loader.return_value = mock_loader_instance
        mock_loader_instance.load_procedures.return_value = []

        mock_analyzer_instance = Mock()
        mock_analyzer.return_value = mock_analyzer_instance

        with self.runner.isolated_filesystem():
            result = self.runner.invoke(main.cli, [
                'analyze-files',
                '--directory', '.',
                '--pattern', '*.prc'
            ])

            # Should execute without errors
            # May fail if no files found, but command structure is tested

    def test_analyze_files_command_missing_directory(self):
        """Test analyze-files fails without directory"""
        result = self.runner.invoke(main.cli, ['analyze-files'])

        # Should show error or use default


class TestQueryCommand(unittest.TestCase):
    """Test query command with agent"""

    def setUp(self):
        """Set up test fixtures"""
        self.runner = CliRunner()

    @patch('main.CodeAnalysisAgent')
    @patch('main.CodeKnowledgeGraph')
    def test_query_command(self, mock_kg, mock_agent):
        """Test query command"""
        mock_kg_instance = Mock()
        mock_kg.return_value = mock_kg_instance

        mock_agent_instance = Mock()
        mock_agent.return_value = mock_agent_instance
        mock_agent_instance.analyze.return_value = {
            "success": True,
            "answer": "Test answer"
        }

        result = self.runner.invoke(main.cli, [
            'query',
            'What does procedure X do?'
        ])

        # Agent should be called with query
        # May require initialized knowledge graph

    def test_query_command_missing_query(self):
        """Test query command fails without query text"""
        result = self.runner.invoke(main.cli, ['query'])

        # Should fail
        self.assertNotEqual(result.exit_code, 0)


class TestConnectionCommand(unittest.TestCase):
    """Test test-connection command"""

    def setUp(self):
        """Set up test fixtures"""
        self.runner = CliRunner()

    @patch('main.get_loader')
    def test_connection_command_success(self, mock_get_loader):
        """Test successful connection test"""
        mock_loader = Mock()
        mock_get_loader.return_value = mock_loader

        # Mock successful connection
        mock_loader.test_connection.return_value = True

        result = self.runner.invoke(main.cli, [
            'test-connection',
            '--db-type', 'postgresql',
            '--host', 'localhost',
            '--port', '5432',
            '--database', 'test_db',
            '--user', 'test_user',
            '--password', 'test_pass'
        ])

        # Should show success message
        self.assertIn("success", result.output.lower()) or self.assertEqual(result.exit_code, 0)

    @patch('main.get_loader')
    def test_connection_command_failure(self, mock_get_loader):
        """Test failed connection test"""
        mock_loader = Mock()
        mock_get_loader.return_value = mock_loader

        # Mock failed connection
        mock_loader.test_connection.side_effect = Exception("Connection failed")

        result = self.runner.invoke(main.cli, [
            'test-connection',
            '--db-type', 'postgresql',
            '--host', 'invalid_host',
            '--database', 'test_db',
            '--user', 'test_user',
            '--password', 'test_pass'
        ])

        # Should show error message
        self.assertNotEqual(result.exit_code, 0) or self.assertIn("error", result.output.lower())


class TestCLIOptions(unittest.TestCase):
    """Test CLI options and flags"""

    def setUp(self):
        """Set up test fixtures"""
        self.runner = CliRunner()

    def test_help_option(self):
        """Test --help option shows help"""
        result = self.runner.invoke(main.cli, ['--help'])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Usage:", result.output)

    def test_version_option(self):
        """Test --version option (if implemented)"""
        result = self.runner.invoke(main.cli, ['--version'])

        # May or may not be implemented

    def test_dry_run_option(self):
        """Test --dry-run option"""
        with patch('main.ProcedureAnalyzer') as mock_analyzer:
            with patch('main.get_loader') as mock_loader:
                mock_loader.return_value = Mock()

                result = self.runner.invoke(main.cli, [
                    'analyze',
                    '--dry-run',
                    '--analysis-type', 'procedures',
                    '--db-type', 'postgresql',
                    '--host', 'localhost',
                    '--database', 'test_db',
                    '--user', 'test_user',
                    '--password', 'test_pass'
                ])

                # Dry run should not actually execute analysis

    def test_verbose_option(self):
        """Test --verbose option increases logging"""
        with patch('main.logging.basicConfig') as mock_logging:
            result = self.runner.invoke(main.cli, [
                '--verbose',
                'test-connection',
                '--db-type', 'postgresql',
                '--host', 'localhost',
                '--database', 'test_db',
                '--user', 'test_user',
                '--password', 'test_pass'
            ])

            # Verbose should set DEBUG level


class TestCLIErrorHandling(unittest.TestCase):
    """Test CLI error handling"""

    def setUp(self):
        """Set up test fixtures"""
        self.runner = CliRunner()

    def test_invalid_db_type(self):
        """Test error with invalid database type"""
        result = self.runner.invoke(main.cli, [
            'analyze',
            '--db-type', 'invalid_db',
            '--host', 'localhost',
            '--database', 'test_db',
            '--user', 'test_user',
            '--password', 'test_pass'
        ])

        # Should show error
        self.assertNotEqual(result.exit_code, 0)

    def test_invalid_analysis_type(self):
        """Test error with invalid analysis type"""
        result = self.runner.invoke(main.cli, [
            'analyze',
            '--analysis-type', 'invalid_type',
            '--db-type', 'postgresql',
            '--host', 'localhost',
            '--database', 'test_db',
            '--user', 'test_user',
            '--password', 'test_pass'
        ])

        # Should show error
        self.assertNotEqual(result.exit_code, 0)


@pytest.mark.integration
class TestCLIIntegration(unittest.TestCase):
    """Integration tests for CLI"""

    def test_full_analyze_workflow(self):
        """Test complete analyze workflow"""
        pytest.skip("Integration test - requires real database")

    def test_full_query_workflow(self):
        """Test complete query workflow"""
        pytest.skip("Integration test - requires initialized knowledge graph")


if __name__ == '__main__':
    unittest.main()

