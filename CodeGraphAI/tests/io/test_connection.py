"""
Testes para teste de conexão de banco de dados
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from app.core.models import DatabaseConfig, DatabaseType, ProcedureLoadError, ValidationError
from app.io.base import ProcedureLoaderBase
from app.io.factory import create_loader


class TestPostgreSQLConnection:
    """Testes para teste de conexão PostgreSQL"""

    @pytest.fixture
    def config(self):
        """Cria configuração PostgreSQL"""
        return DatabaseConfig(
            db_type=DatabaseType.POSTGRESQL,
            user="testuser",
            password="testpass",
            host="localhost",
            port=5432,
            database="testdb"
        )

    @patch('app.io.postgres_loader.psycopg2')
    def test_connection_only_success(self, mock_psycopg2, config):
        """Testa conexão bem-sucedida"""
        # Mock da conexão
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)
        mock_conn.cursor.return_value = mock_cursor
        mock_psycopg2.connect.return_value = mock_conn

        try:
            loader = create_loader(DatabaseType.POSTGRESQL)
            result = loader.test_connection_only(config)
            assert result is True
            mock_psycopg2.connect.assert_called_once()
            mock_cursor.execute.assert_called_once_with("SELECT 1")
        except ImportError:
            pytest.skip("psycopg2 não disponível")

    @patch('app.io.postgres_loader.psycopg2')
    def test_connection_only_failure(self, mock_psycopg2, config):
        """Testa falha de conexão"""
        mock_psycopg2.connect.side_effect = Exception("Connection failed")
        mock_psycopg2.Error = Exception

        try:
            loader = create_loader(DatabaseType.POSTGRESQL)
            with pytest.raises(ProcedureLoadError):
                loader.test_connection_only(config)
        except ImportError:
            pytest.skip("psycopg2 não disponível")

    def test_connection_only_missing_database(self, config):
        """Testa erro quando database não fornecido"""
        config.database = None
        try:
            loader = create_loader(DatabaseType.POSTGRESQL)
            with pytest.raises(ValidationError, match="database"):
                loader.test_connection_only(config)
        except ImportError:
            pytest.skip("psycopg2 não disponível")


class TestOracleConnection:
    """Testes para teste de conexão Oracle"""

    @pytest.fixture
    def config(self):
        """Cria configuração Oracle"""
        return DatabaseConfig(
            db_type=DatabaseType.ORACLE,
            user="testuser",
            password="testpass",
            host="localhost:1521/ORCL"
        )

    @patch('app.io.oracle_loader.oracledb')
    def test_connection_only_success(self, mock_oracledb, config):
        """Testa conexão bem-sucedida"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)
        mock_conn.cursor.return_value = mock_cursor
        mock_oracledb.connect.return_value = mock_conn

        try:
            loader = create_loader(DatabaseType.ORACLE)
            result = loader.test_connection_only(config)
            assert result is True
            mock_oracledb.connect.assert_called_once()
            mock_cursor.execute.assert_called_once_with("SELECT 1 FROM DUAL")
        except ImportError:
            pytest.skip("oracledb não disponível")

    @patch('app.io.oracle_loader.oracledb')
    def test_connection_only_failure(self, mock_oracledb, config):
        """Testa falha de conexão"""
        mock_oracledb.connect.side_effect = Exception("Connection failed")
        mock_oracledb.Error = Exception

        try:
            loader = create_loader(DatabaseType.ORACLE)
            with pytest.raises(ProcedureLoadError):
                loader.test_connection_only(config)
        except ImportError:
            pytest.skip("oracledb não disponível")


class TestMySQLConnection:
    """Testes para teste de conexão MySQL"""

    @pytest.fixture
    def config(self):
        """Cria configuração MySQL"""
        return DatabaseConfig(
            db_type=DatabaseType.MYSQL,
            user="testuser",
            password="testpass",
            host="localhost",
            port=3306,
            database="testdb"
        )

    @patch('app.io.mysql_loader.mysql')
    def test_connection_only_success_mysql_connector(self, mock_mysql, config):
        """Testa conexão bem-sucedida com mysql-connector"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)
        mock_conn.cursor.return_value = mock_cursor
        mock_mysql.connector.connect.return_value = mock_conn

        try:
            loader = create_loader(DatabaseType.MYSQL)
            # Força uso de mysql-connector
            loader.driver = 'mysql-connector'
            result = loader.test_connection_only(config)
            assert result is True
            mock_mysql.connector.connect.assert_called_once()
            mock_cursor.execute.assert_called_once_with("SELECT 1")
        except ImportError:
            pytest.skip("mysql-connector não disponível")

    def test_connection_only_missing_database(self, config):
        """Testa erro quando database não fornecido"""
        config.database = None
        try:
            loader = create_loader(DatabaseType.MYSQL)
            with pytest.raises(ValidationError, match="database"):
                loader.test_connection_only(config)
        except ImportError:
            pytest.skip("MySQL driver não disponível")


class TestMSSQLConnection:
    """Testes para teste de conexão SQL Server"""

    @pytest.fixture
    def config(self):
        """Cria configuração SQL Server"""
        return DatabaseConfig(
            db_type=DatabaseType.MSSQL,
            user="testuser",
            password="testpass",
            host="localhost",
            port=1433,
            database="testdb"
        )

    @patch('app.io.mssql_loader.pyodbc')
    def test_connection_only_success(self, mock_pyodbc, config):
        """Testa conexão bem-sucedida"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)
        mock_conn.cursor.return_value = mock_cursor
        mock_pyodbc.connect.return_value = mock_conn

        try:
            loader = create_loader(DatabaseType.MSSQL)
            result = loader.test_connection_only(config)
            assert result is True
            mock_pyodbc.connect.assert_called_once()
            mock_cursor.execute.assert_called_once_with("SELECT 1")
        except ImportError:
            pytest.skip("pyodbc não disponível")

    @patch('app.io.mssql_loader.pyodbc')
    def test_connection_only_failure(self, mock_pyodbc, config):
        """Testa falha de conexão"""
        mock_pyodbc.connect.side_effect = Exception("Connection failed")
        mock_pyodbc.Error = Exception

        try:
            loader = create_loader(DatabaseType.MSSQL)
            with pytest.raises(ProcedureLoadError):
                loader.test_connection_only(config)
        except ImportError:
            pytest.skip("pyodbc não disponível")

    def test_connection_only_missing_database(self, config):
        """Testa erro quando database não fornecido"""
        config.database = None
        try:
            loader = create_loader(DatabaseType.MSSQL)
            with pytest.raises(ValidationError, match="database"):
                loader.test_connection_only(config)
        except ImportError:
            pytest.skip("pyodbc não disponível")

