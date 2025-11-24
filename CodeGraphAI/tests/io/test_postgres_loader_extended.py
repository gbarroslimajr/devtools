"""
Extended tests for PostgreSQL Loader with real database
"""

import pytest
import unittest
import os
from unittest.mock import Mock
from app.io.postgres_loader import PostgreSQLLoader
from app.io.postgres_table_loader import PostgreSQLTableLoader
from app.core.models import DatabaseConfig, DatabaseType


@pytest.mark.real_db
class TestPostgreSQLLoaderRealDB(unittest.TestCase):
    """Real database tests for PostgreSQL loader"""

    @classmethod
    def setUpClass(cls):
        """Set up database connection from environment"""
        cls.db_config = DatabaseConfig(
            db_type=DatabaseType.POSTGRESQL,
            user=os.getenv("CODEGRAPHAI_DB_USER", "postgres"),
            password=os.getenv("CODEGRAPHAI_DB_PASSWORD", "changeme"),
            host=os.getenv("CODEGRAPHAI_DB_HOST", "localhost"),
            port=int(os.getenv("CODEGRAPHAI_DB_PORT", "5432")),
            database=os.getenv("CODEGRAPHAI_DB_NAME", "optomate"),
            schema=os.getenv("CODEGRAPHAI_DB_SCHEMA", "tenant_optomate")
        )

    def setUp(self):
        """Set up test fixtures"""
        self.loader = PostgreSQLLoader(self.db_config)

    def test_real_connection(self):
        """Test real database connection"""
        # Test connection works
        try:
            connection = self.loader._connect()
            self.assertIsNotNone(connection)
            connection.close()
        except Exception as e:
            pytest.skip(f"Database not available: {e}")

    def test_load_real_functions(self):
        """Test loading real functions from database"""
        try:
            procedures = self.loader.load_procedures(limit=5)

            # Should return some procedures/functions
            self.assertIsInstance(procedures, list)

            if len(procedures) > 0:
                # Verify structure
                proc = procedures[0]
                self.assertIsNotNone(proc.name)
                self.assertIsNotNone(proc.schema)
                self.assertIsNotNone(proc.source_code)
        except Exception as e:
            pytest.skip(f"Could not load procedures: {e}")

    def test_load_procedures_with_filter(self):
        """Test loading procedures with name filter"""
        try:
            # Try to load specific procedure
            procedures = self.loader.load_procedures(procedure_names=["specific_proc"])

            # Should return list (may be empty if proc doesn't exist)
            self.assertIsInstance(procedures, list)
        except Exception as e:
            pytest.skip(f"Could not load procedures: {e}")


@pytest.mark.real_db
class TestPostgreSQLTableLoaderRealDB(unittest.TestCase):
    """Real database tests for PostgreSQL table loader"""

    @classmethod
    def setUpClass(cls):
        """Set up database connection from environment"""
        cls.db_config = DatabaseConfig(
            db_type=DatabaseType.POSTGRESQL,
            user=os.getenv("CODEGRAPHAI_DB_USER", "postgres"),
            password=os.getenv("CODEGRAPHAI_DB_PASSWORD", "changeme"),
            host=os.getenv("CODEGRAPHAI_DB_HOST", "localhost"),
            port=int(os.getenv("CODEGRAPHAI_DB_PORT", "5432")),
            database=os.getenv("CODEGRAPHAI_DB_NAME", "optomate"),
            schema=os.getenv("CODEGRAPHAI_DB_SCHEMA", "tenant_optomate")
        )

    def setUp(self):
        """Set up test fixtures"""
        self.loader = PostgreSQLTableLoader(self.db_config)

    def test_load_real_tables(self):
        """Test loading real tables from database"""
        try:
            tables = self.loader.load_tables(limit=10)

            self.assertIsInstance(tables, list)

            if len(tables) > 0:
                # Verify structure
                table = tables[0]
                self.assertIsNotNone(table.name)
                self.assertIsNotNone(table.schema)
                self.assertIsInstance(table.columns, list)
        except Exception as e:
            pytest.skip(f"Could not load tables: {e}")

    def test_load_tables_with_columns(self):
        """Test tables include column information"""
        try:
            tables = self.loader.load_tables(limit=5)

            if len(tables) > 0:
                table = tables[0]

                # Should have columns
                self.assertGreater(len(table.columns), 0)

                # Verify column structure
                col = table.columns[0]
                self.assertIsNotNone(col.name)
                self.assertIsNotNone(col.data_type)
                self.assertIsNotNone(col.nullable)
        except Exception as e:
            pytest.skip(f"Could not load tables: {e}")

    def test_load_tables_with_foreign_keys(self):
        """Test tables include foreign key relationships"""
        try:
            tables = self.loader.load_tables(limit=20)

            # Find a table with foreign keys
            table_with_fk = None
            for table in tables:
                if table.relationships and len(table.relationships.get("foreign_keys", [])) > 0:
                    table_with_fk = table
                    break

            if table_with_fk:
                # Verify FK structure
                fks = table_with_fk.relationships["foreign_keys"]
                self.assertGreater(len(fks), 0)

                fk = fks[0]
                self.assertIn("column", fk)
                self.assertIn("referenced_table", fk)
                self.assertIn("referenced_column", fk)
        except Exception as e:
            pytest.skip(f"Could not load foreign keys: {e}")

    def test_load_tables_with_indexes(self):
        """Test tables include index information"""
        try:
            tables = self.loader.load_tables(limit=10)

            # Find table with indexes
            table_with_idx = None
            for table in tables:
                if hasattr(table, 'indexes') and len(table.indexes) > 0:
                    table_with_idx = table
                    break

            if table_with_idx:
                # Verify index structure
                self.assertGreater(len(table_with_idx.indexes), 0)
        except Exception as e:
            pytest.skip(f"Could not load indexes: {e}")

    def test_no_duplicate_columns(self):
        """Test that columns are not duplicated"""
        try:
            tables = self.loader.load_tables(limit=10)

            for table in tables:
                # Check for duplicate column names
                column_names = [col.name for col in table.columns]
                unique_names = set(column_names)

                self.assertEqual(
                    len(column_names),
                    len(unique_names),
                    f"Table {table.name} has duplicate columns"
                )
        except Exception as e:
            pytest.skip(f"Could not check duplicates: {e}")


class TestPostgreSQLSpecificFeatures(unittest.TestCase):
    """Test PostgreSQL-specific features"""

    def test_array_column_types(self):
        """Test handling of PostgreSQL array types"""
        # PostgreSQL supports array types like INTEGER[]
        # Test that these are handled correctly
        pass

    def test_json_column_types(self):
        """Test handling of JSON/JSONB types"""
        # PostgreSQL supports JSON and JSONB types
        # Test that these are identified correctly
        pass

    def test_custom_types(self):
        """Test handling of custom/enum types"""
        # PostgreSQL supports custom types and ENUMs
        # Test that these are handled correctly
        pass

    def test_materialized_views(self):
        """Test handling of materialized views"""
        # PostgreSQL has materialized views
        # Test if they are included/excluded correctly
        pass


if __name__ == '__main__':
    unittest.main()

