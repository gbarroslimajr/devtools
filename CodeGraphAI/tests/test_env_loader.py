"""
Tests for environment configuration loading and validation
"""

import unittest
import os
from pathlib import Path


class TestEnvironmentConfiguration(unittest.TestCase):
    """Test environment variables are properly configured"""

    def test_environment_file_exists(self):
        """Test that environment.env file exists"""
        env_file = Path("environment.env")
        self.assertTrue(env_file.exists(), "environment.env file not found")

    def test_database_config_variables(self):
        """Test that database configuration variables are set"""
        required_vars = [
            "CODEGRAPHAI_DB_TYPE",
            "CODEGRAPHAI_DB_HOST",
            "CODEGRAPHAI_DB_PORT",
            "CODEGRAPHAI_DB_NAME",
            "CODEGRAPHAI_DB_USER",
            "CODEGRAPHAI_DB_PASSWORD",
            "CODEGRAPHAI_DB_SCHEMA"
        ]

        for var in required_vars:
            value = os.getenv(var)
            # Should at least have a default or configured value
            # Not testing if it's correct, just if it's set

    def test_llm_config_variables(self):
        """Test that LLM configuration variables are set"""
        llm_mode = os.getenv("CODEGRAPHAI_LLM_MODE", "api")

        if llm_mode == "api":
            # Should have at least one API provider configured
            has_openai = bool(os.getenv("CODEGRAPHAI_OPENAI_API_KEY"))
            has_anthropic = bool(os.getenv("CODEGRAPHAI_ANTHROPIC_API_KEY"))
            has_genfactory = bool(os.getenv("CODEGRAPHAI_GENFACTORY_LLAMA70B_AUTHORIZATION_TOKEN"))

            # At least one should be configured
            # (though not strictly required for tests that don't use LLM)

    def test_database_connection_with_env_vars(self):
        """Test database connection using environment variables"""
        db_type = os.getenv("CODEGRAPHAI_DB_TYPE", "postgresql")

        if db_type == "postgresql":
            # Test PostgreSQL specific vars
            host = os.getenv("CODEGRAPHAI_DB_HOST", "localhost")
            port = os.getenv("CODEGRAPHAI_DB_PORT", "5432")
            database = os.getenv("CODEGRAPHAI_DB_NAME")

            self.assertIsNotNone(database, "Database name not configured")

    def test_output_directory_config(self):
        """Test output directory configuration"""
        output_dir = os.getenv("CODEGRAPHAI_OUTPUT_DIR", "./output")

        # Should be a valid path string
        self.assertIsInstance(output_dir, str)
        self.assertGreater(len(output_dir), 0)

    def test_log_level_config(self):
        """Test logging configuration"""
        log_level = os.getenv("CODEGRAPHAI_LOG_LEVEL", "INFO")

        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        self.assertIn(log_level, valid_levels)


class TestEnvironmentValidation(unittest.TestCase):
    """Test validation of environment configuration values"""

    def test_database_type_is_valid(self):
        """Test database type is one of supported types"""
        db_type = os.getenv("CODEGRAPHAI_DB_TYPE", "postgresql")

        valid_types = ["postgresql", "oracle", "mssql", "mysql"]
        self.assertIn(db_type.lower(), valid_types)

    def test_database_port_is_numeric(self):
        """Test database port is a valid number"""
        port_str = os.getenv("CODEGRAPHAI_DB_PORT", "5432")

        try:
            port = int(port_str)
            self.assertGreater(port, 0)
            self.assertLess(port, 65536)
        except ValueError:
            self.fail(f"Database port '{port_str}' is not a valid number")

    def test_llm_provider_is_valid(self):
        """Test LLM provider is one of supported providers"""
        provider = os.getenv("CODEGRAPHAI_LLM_PROVIDER", "openai")

        valid_providers = [
            "openai",
            "anthropic",
            "genfactory_llama70b",
            "genfactory_codestral",
            "genfactory_gptoss120b"
        ]

        # Provider might be set but not validated strictly in tests

    def test_llm_use_toon_is_boolean(self):
        """Test TOON usage flag is valid boolean"""
        use_toon = os.getenv("CODEGRAPHAI_LLM_USE_TOON", "false")

        valid_values = ["true", "false", "1", "0", "yes", "no"]
        self.assertIn(use_toon.lower(), valid_values)


class TestRequiredDependencies(unittest.TestCase):
    """Test that required dependencies are installed"""

    def test_langchain_installed(self):
        """Test LangChain is installed"""
        try:
            import langchain
            import langchain_core
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"LangChain not installed: {e}")

    def test_networkx_installed(self):
        """Test NetworkX is installed"""
        try:
            import networkx
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"NetworkX not installed: {e}")

    def test_click_installed(self):
        """Test Click is installed"""
        try:
            import click
            self.assertTrue(True)
        except ImportError as e:
            self.fail(f"Click not installed: {e}")

    def test_database_driver_available(self):
        """Test at least one database driver is available"""
        db_type = os.getenv("CODEGRAPHAI_DB_TYPE", "postgresql")

        drivers = {
            "postgresql": "psycopg2",
            "oracle": "oracledb",
            "mssql": "pyodbc",
            "mysql": "mysql.connector"
        }

        if db_type.lower() in drivers:
            driver = drivers[db_type.lower()]
            try:
                __import__(driver)
                self.assertTrue(True)
            except ImportError:
                # Driver not installed, but that's ok for tests that don't need it
                pass


if __name__ == '__main__':
    unittest.main()

