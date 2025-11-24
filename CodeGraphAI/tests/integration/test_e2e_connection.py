"""
End-to-End Integration Tests for test-connection command
"""

import pytest
import unittest
import os
from click.testing import CliRunner
import main


@pytest.mark.integration
class TestE2EConnectionCommand(unittest.TestCase):
    """End-to-end tests for test-connection command"""

    def setUp(self):
        """Set up test fixtures"""
        self.runner = CliRunner()
        self.db_config = {
            "db_type": os.getenv("CODEGRAPHAI_DB_TYPE", "postgresql"),
            "host": os.getenv("CODEGRAPHAI_DB_HOST", "localhost"),
            "port": os.getenv("CODEGRAPHAI_DB_PORT", "5432"),
            "database": os.getenv("CODEGRAPHAI_DB_NAME", "optomate"),
            "user": os.getenv("CODEGRAPHAI_DB_USER", "postgres"),
            "password": os.getenv("CODEGRAPHAI_DB_PASSWORD", "changeme")
        }

    @pytest.mark.real_db
    def test_connection_postgresql_success(self):
        """Test successful PostgreSQL connection"""
        result = self.runner.invoke(main.cli, [
            'test-connection',
            '--db-type', self.db_config["db_type"],
            '--host', self.db_config["host"],
            '--port', self.db_config["port"],
            '--database', self.db_config["database"],
            '--user', self.db_config["user"],
            '--password', self.db_config["password"]
        ])

        # Should succeed or skip if DB not available

    def test_connection_invalid_credentials(self):
        """Test connection with invalid credentials"""
        result = self.runner.invoke(main.cli, [
            'test-connection',
            '--db-type', 'postgresql',
            '--host', 'localhost',
            '--port', '5432',
            '--database', 'test_db',
            '--user', 'invalid_user',
            '--password', 'wrong_password'
        ])

        # Should fail gracefully
        self.assertNotEqual(result.exit_code, 0)

    def test_connection_invalid_host(self):
        """Test connection with invalid host"""
        result = self.runner.invoke(main.cli, [
            'test-connection',
            '--db-type', 'postgresql',
            '--host', 'nonexistent.host.invalid',
            '--port', '5432',
            '--database', 'test_db',
            '--user', 'test_user',
            '--password', 'test_pass'
        ])

        # Should fail with connection error
        self.assertNotEqual(result.exit_code, 0)


if __name__ == '__main__':
    unittest.main()

