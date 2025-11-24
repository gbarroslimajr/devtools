"""
Tests for Query Tools - execute_query, sample_table_data, get_field_statistics
"""

import pytest
import unittest
import json
from unittest.mock import Mock, patch, MagicMock
from app.tools.query_tools import (
    execute_query,
    sample_table_data,
    get_field_statistics,
    _validate_select_query,
    _add_limit_if_needed
)
from app.core.models import DatabaseConfig, DatabaseType
import app.tools.query_tools as query_tools


class TestQueryValidation(unittest.TestCase):
    """Test query validation functions"""

    def test_validate_select_query_valid(self):
        """Test validation of valid SELECT query"""
        query = "SELECT * FROM users WHERE id = 1"
        is_valid, error = _validate_select_query(query)

        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_validate_select_query_case_insensitive(self):
        """Test validation is case-insensitive"""
        query = "select * from users"
        is_valid, error = _validate_select_query(query)

        self.assertTrue(is_valid)

    def test_validate_select_query_with_joins(self):
        """Test validation of SELECT with JOINs"""
        query = """
            SELECT u.name, o.total
            FROM users u
            JOIN orders o ON u.id = o.user_id
        """
        is_valid, error = _validate_select_query(query)

        self.assertTrue(is_valid)

    def test_validate_select_query_rejects_delete(self):
        """Test validation rejects DELETE"""
        query = "DELETE FROM users WHERE id = 1"
        is_valid, error = _validate_select_query(query)

        self.assertFalse(is_valid)
        self.assertIn("DELETE", error)

    def test_validate_select_query_rejects_update(self):
        """Test validation rejects UPDATE"""
        query = "UPDATE users SET name = 'test' WHERE id = 1"
        is_valid, error = _validate_select_query(query)

        self.assertFalse(is_valid)
        self.assertIn("UPDATE", error)

    def test_validate_select_query_rejects_insert(self):
        """Test validation rejects INSERT"""
        query = "INSERT INTO users (name) VALUES ('test')"
        is_valid, error = _validate_select_query(query)

        self.assertFalse(is_valid)
        self.assertIn("INSERT", error)

    def test_validate_select_query_rejects_drop(self):
        """Test validation rejects DROP"""
        query = "DROP TABLE users"
        is_valid, error = _validate_select_query(query)

        self.assertFalse(is_valid)
        self.assertIn("DROP", error)

    def test_validate_select_query_rejects_exec(self):
        """Test validation rejects EXEC"""
        query = "EXEC sp_executesql 'SELECT * FROM users'"
        is_valid, error = _validate_select_query(query)

        self.assertFalse(is_valid)
        self.assertIn("EXEC", error)

    def test_validate_select_query_with_comments(self):
        """Test validation handles SQL comments"""
        query = """
            -- This is a comment
            SELECT * FROM users
            /* Another comment */
            WHERE id = 1
        """
        is_valid, error = _validate_select_query(query)

        self.assertTrue(is_valid)

    def test_validate_select_query_rejects_multiple_statements(self):
        """Test validation rejects multiple statements"""
        query = "SELECT * FROM users; DELETE FROM users"
        is_valid, error = _validate_select_query(query)

        self.assertFalse(is_valid)
        self.assertIn("Múltiplos comandos", error)


class TestQueryLimitAddition(unittest.TestCase):
    """Test limit addition to queries"""

    def test_add_limit_to_query_without_limit(self):
        """Test adding LIMIT to query without one"""
        query = "SELECT * FROM users"
        result = _add_limit_if_needed(query, max_limit=100)

        self.assertIn("LIMIT 100", result)

    def test_add_limit_respects_existing_limit(self):
        """Test doesn't override existing LIMIT"""
        query = "SELECT * FROM users LIMIT 50"
        result = _add_limit_if_needed(query, max_limit=100)

        self.assertIn("LIMIT 50", result)

    def test_add_limit_enforces_max_limit(self):
        """Test replaces LIMIT if exceeds max"""
        query = "SELECT * FROM users LIMIT 2000"
        result = _add_limit_if_needed(query, max_limit=1000)

        self.assertIn("LIMIT 1000", result)
        self.assertNotIn("LIMIT 2000", result)

    def test_add_limit_handles_trailing_semicolon(self):
        """Test handles trailing semicolon"""
        query = "SELECT * FROM users;"
        result = _add_limit_if_needed(query, max_limit=100)

        self.assertIn("LIMIT 100", result)
        # Should have only one semicolon or none at end


class TestExecuteQueryTool(unittest.TestCase):
    """Test execute_query tool"""

    def setUp(self):
        """Set up test fixtures"""
        self.db_config = DatabaseConfig(
            db_type=DatabaseType.POSTGRESQL,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            database="test_db",
            schema="public"
        )

    def test_execute_query_no_db_config(self):
        """Test execute_query without database config"""
        query_tools._db_config = None

        result = execute_query.invoke({
            "query": "SELECT * FROM users",
            "limit": 10
        })

        data = json.loads(result)
        self.assertFalse(data["success"])
        self.assertIn("Configuração de banco de dados não disponível", data["error"])

    def test_execute_query_invalid_query(self):
        """Test execute_query with invalid query"""
        query_tools._db_config = self.db_config

        result = execute_query.invoke({
            "query": "DELETE FROM users",
            "limit": 10
        })

        data = json.loads(result)
        self.assertFalse(data["success"])
        self.assertIn("DELETE", data["error"])

    def test_execute_query_limit_validation(self):
        """Test execute_query enforces limit"""
        query_tools._db_config = self.db_config

        # Test limit > 1000
        with patch('app.tools.query_tools._execute_safe_query') as mock_execute:
            mock_execute.return_value = {
                "columns": ["id"],
                "rows": [],
                "row_count": 0
            }

            result = execute_query.invoke({
                "query": "SELECT * FROM users",
                "limit": 5000  # Should be reduced to 1000
            })

            # Verify limit was enforced
            call_args = mock_execute.call_args
            query_arg = call_args[0][0]
            self.assertIn("LIMIT 1000", query_arg)


class TestSampleTableDataTool(unittest.TestCase):
    """Test sample_table_data tool"""

    def setUp(self):
        """Set up test fixtures"""
        self.db_config = DatabaseConfig(
            db_type=DatabaseType.POSTGRESQL,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            database="test_db",
            schema="public"
        )

    def test_sample_table_data_no_db_config(self):
        """Test sample_table_data without database config"""
        query_tools._db_config = None

        result = sample_table_data.invoke({
            "table_name": "users",
            "limit": 10
        })

        data = json.loads(result)
        self.assertFalse(data["success"])

    def test_sample_table_data_basic(self):
        """Test basic table sampling"""
        query_tools._db_config = self.db_config

        with patch('app.tools.query_tools._execute_safe_query') as mock_execute:
            mock_execute.return_value = {
                "columns": ["id", "name", "email"],
                "rows": [
                    {"id": "1", "name": "Alice", "email": "alice@example.com"},
                    {"id": "2", "name": "Bob", "email": "bob@example.com"}
                ],
                "row_count": 2
            }

            result = sample_table_data.invoke({
                "table_name": "users",
                "limit": 10
            })

            data = json.loads(result)
            self.assertTrue(data["success"])
            self.assertEqual(data["table_name"], "users")
            self.assertEqual(data["data"]["row_count"], 2)
            self.assertEqual(len(data["data"]["columns"]), 3)

    def test_sample_table_data_with_specific_columns(self):
        """Test sampling with specific columns"""
        query_tools._db_config = self.db_config

        with patch('app.tools.query_tools._execute_safe_query') as mock_execute:
            mock_execute.return_value = {
                "columns": ["name", "email"],
                "rows": [{"name": "Alice", "email": "alice@example.com"}],
                "row_count": 1
            }

            result = sample_table_data.invoke({
                "table_name": "users",
                "limit": 5,
                "columns": ["name", "email"]
            })

            # Verify correct query was built
            call_args = mock_execute.call_args
            query_arg = call_args[0][0]
            self.assertIn("name", query_arg)
            self.assertIn("email", query_arg)
            self.assertIn("FROM users", query_arg)

    def test_sample_table_data_limit_enforcement(self):
        """Test limit is enforced (max 100)"""
        query_tools._db_config = self.db_config

        with patch('app.tools.query_tools._execute_safe_query') as mock_execute:
            mock_execute.return_value = {
                "columns": ["id"],
                "rows": [],
                "row_count": 0
            }

            result = sample_table_data.invoke({
                "table_name": "users",
                "limit": 500  # Should be reduced to 100
            })

            call_args = mock_execute.call_args
            query_arg = call_args[0][0]
            self.assertIn("LIMIT 100", query_arg)


class TestGetFieldStatisticsTool(unittest.TestCase):
    """Test get_field_statistics tool"""

    def setUp(self):
        """Set up test fixtures"""
        self.db_config = DatabaseConfig(
            db_type=DatabaseType.POSTGRESQL,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            database="test_db",
            schema="public"
        )

    def test_get_field_statistics_no_db_config(self):
        """Test get_field_statistics without database config"""
        query_tools._db_config = None

        result = get_field_statistics.invoke({
            "table_name": "users",
            "field_name": "age"
        })

        data = json.loads(result)
        self.assertFalse(data["success"])

    def test_get_field_statistics_basic(self):
        """Test basic field statistics"""
        query_tools._db_config = self.db_config

        with patch('app.tools.query_tools._execute_safe_query') as mock_execute:
            # Mock basic stats query
            mock_execute.return_value = {
                "columns": ["total_count", "non_null_count", "null_count", "distinct_count"],
                "rows": [{
                    "total_count": "1000",
                    "non_null_count": "950",
                    "null_count": "50",
                    "distinct_count": "100"
                }],
                "row_count": 1
            }

            result = get_field_statistics.invoke({
                "table_name": "users",
                "field_name": "age"
            })

            data = json.loads(result)
            self.assertTrue(data["success"])
            self.assertEqual(data["data"]["table_name"], "users")
            self.assertEqual(data["data"]["field_name"], "age")
            self.assertEqual(data["data"]["total_count"], 1000)
            self.assertEqual(data["data"]["distinct_count"], 100)

    def test_get_field_statistics_numeric_field(self):
        """Test statistics for numeric field includes min/max/avg"""
        query_tools._db_config = self.db_config

        with patch('app.tools.query_tools._execute_safe_query') as mock_execute:
            # Mock basic stats
            mock_execute.side_effect = [
                {
                    "columns": ["total_count", "non_null_count", "null_count", "distinct_count"],
                    "rows": [{
                        "total_count": "1000",
                        "non_null_count": "1000",
                        "null_count": "0",
                        "distinct_count": "100"
                    }],
                    "row_count": 1
                },
                # Mock numeric stats
                {
                    "columns": ["min_value", "max_value", "avg_value"],
                    "rows": [{
                        "min_value": "18",
                        "max_value": "65",
                        "avg_value": "35.5"
                    }],
                    "row_count": 1
                }
            ]

            result = get_field_statistics.invoke({
                "table_name": "users",
                "field_name": "age"
            })

            data = json.loads(result)
            self.assertTrue(data["success"])
            self.assertEqual(data["data"]["min_value"], "18")
            self.assertEqual(data["data"]["max_value"], "65")
            self.assertEqual(data["data"]["avg_value"], "35.5")


@pytest.mark.real_db
class TestQueryToolsRealDatabase:
    """Real database integration tests - requires PostgreSQL running"""

    def test_real_execute_query(self):
        """Test with real PostgreSQL database"""
        pytest.skip("Real database test - enable manually with real DB")

    def test_real_sample_table_data(self):
        """Test table sampling with real database"""
        pytest.skip("Real database test - enable manually with real DB")

    def test_real_field_statistics(self):
        """Test field statistics with real database"""
        pytest.skip("Real database test - enable manually with real DB")


if __name__ == '__main__':
    unittest.main()

