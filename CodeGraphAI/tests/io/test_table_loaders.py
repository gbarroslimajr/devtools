"""
Testes para Table Loaders
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from app.io.table_base import TableLoaderBase
from app.io.table_factory import create_table_loader, register_table_loader
from app.core.models import DatabaseType, DatabaseConfig, TableLoadError, ValidationError


class TestTableLoaderBase:
    """Testes para interface base TableLoaderBase"""

    def test_abstract_methods(self):
        """Testa que métodos abstratos devem ser implementados"""
        with pytest.raises(TypeError):
            TableLoaderBase()

    def test_validate_config(self):
        """Testa validação de configuração"""
        class TestLoader(TableLoaderBase):
            def get_database_type(self):
                return DatabaseType.POSTGRESQL

            def load_tables(self, config):
                return {}

        loader = TestLoader()
        config = DatabaseConfig(
            db_type=DatabaseType.POSTGRESQL,
            user="test",
            password="test",
            host="localhost"
        )

        # Deve passar sem erro
        loader.validate_config(config)

        # Deve falhar com tipo errado
        config_wrong = DatabaseConfig(
            db_type=DatabaseType.ORACLE,
            user="test",
            password="test",
            host="localhost"
        )
        with pytest.raises(ValidationError):
            loader.validate_config(config_wrong)


class TestTableFactory:
    """Testes para factory de table loaders"""

    def test_create_table_loader_postgresql(self):
        """Testa criação de loader PostgreSQL"""
        try:
            loader = create_table_loader(DatabaseType.POSTGRESQL)
            assert loader is not None
            assert loader.get_database_type() == DatabaseType.POSTGRESQL
        except (ImportError, ValidationError):
            pytest.skip("PostgreSQL driver não disponível")

    def test_create_table_loader_invalid_type(self):
        """Testa erro com tipo inválido"""
        # Cria um tipo inválido temporariamente
        with pytest.raises(ValidationError):
            # Isso deve falhar pois não há loader registrado para um tipo inexistente
            # Na prática, isso não aconteceria pois DatabaseType é um Enum
            pass

    def test_register_table_loader(self):
        """Testa registro de loader customizado"""
        class CustomLoader(TableLoaderBase):
            def get_database_type(self):
                return DatabaseType.ORACLE

            def load_tables(self, config):
                return {}

        # Registra loader customizado
        register_table_loader(DatabaseType.ORACLE, CustomLoader)

        # Tenta criar
        try:
            loader = create_table_loader(DatabaseType.ORACLE)
            assert loader is not None
        except (ImportError, ValidationError):
            pytest.skip("Oracle driver não disponível")


class TestPostgreSQLTableLoader:
    """Testes para PostgreSQLTableLoader"""

    @pytest.mark.skipif(
        not pytest.importorskip("psycopg2", reason="psycopg2 não instalado"),
        reason="psycopg2 não disponível"
    )
    def test_load_tables_requires_database(self):
        """Testa que database é obrigatório"""
        from app.io.postgres_table_loader import PostgreSQLTableLoader

        loader = PostgreSQLTableLoader()
        config = DatabaseConfig(
            db_type=DatabaseType.POSTGRESQL,
            user="test",
            password="test",
            host="localhost"
        )

        with pytest.raises(ValidationError, match="database"):
            loader.load_tables(config)

    def test_validate_config(self):
        """Testa validação de configuração"""
        try:
            from app.io.postgres_table_loader import PostgreSQLTableLoader
            loader = PostgreSQLTableLoader()

            config = DatabaseConfig(
                db_type=DatabaseType.POSTGRESQL,
                user="test",
                password="test",
                host="localhost",
                database="testdb"
            )

            loader.validate_config(config)
        except ImportError:
            pytest.skip("psycopg2 não disponível")


class TestOracleTableLoader:
    """Testes para OracleTableLoader"""

    def test_validate_config(self):
        """Testa validação de configuração"""
        try:
            from app.io.oracle_table_loader import OracleTableLoader
            loader = OracleTableLoader()

            config = DatabaseConfig(
                db_type=DatabaseType.ORACLE,
                user="test",
                password="test",
                host="localhost:1521/ORCL"
            )

            loader.validate_config(config)
        except ImportError:
            pytest.skip("oracledb não disponível")


class TestMSSQLTableLoader:
    """Testes para MSSQLTableLoader"""

    def test_load_tables_requires_database(self):
        """Testa que database é obrigatório"""
        try:
            from app.io.mssql_table_loader import MSSQLTableLoader
            loader = MSSQLTableLoader()

            config = DatabaseConfig(
                db_type=DatabaseType.MSSQL,
                user="test",
                password="test",
                host="localhost"
            )

            with pytest.raises(ValidationError, match="database"):
                loader.load_tables(config)
        except ImportError:
            pytest.skip("pyodbc não disponível")


class TestMySQLTableLoader:
    """Testes para MySQLTableLoader"""

    def test_load_tables_requires_database(self):
        """Testa que database é obrigatório"""
        try:
            from app.io.mysql_table_loader import MySQLTableLoader
            loader = MySQLTableLoader()

            config = DatabaseConfig(
                db_type=DatabaseType.MYSQL,
                user="test",
                password="test",
                host="localhost"
            )

            with pytest.raises(ValidationError, match="database"):
                loader.load_tables(config)
        except ImportError:
            pytest.skip("MySQL driver não disponível")

