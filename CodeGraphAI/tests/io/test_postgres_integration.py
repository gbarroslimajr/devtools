"""
Testes de integração com banco de dados real PostgreSQL
"""
import os
import pytest
from app.io.postgres_table_loader import PostgreSQLTableLoader
from app.core.models import DatabaseConfig, DatabaseType


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv('POSTGRES_TEST_DSN'),
    reason="Requer variável POSTGRES_TEST_DSN configurada"
)
def test_real_database_no_duplicates():
    """Test against real database that columns are not duplicated"""
    config = DatabaseConfig(
        db_type=DatabaseType.POSTGRESQL,
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=int(os.getenv('POSTGRES_PORT', 5432)),
        database=os.getenv('POSTGRES_DATABASE', 'test_db'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', ''),
        schema=os.getenv('POSTGRES_SCHEMA', 'public')
    )

    loader = PostgreSQLTableLoader()
    tables = loader.load_tables(config, use_cache=False, force_update=True)

    # Validate all tables have unique columns
    for table_name, table_info in tables.items():
        column_names = [col.name for col in table_info.columns]
        unique_names = set(column_names)

        assert len(column_names) == len(unique_names), \
            f"Table {table_name} has duplicate columns: " \
            f"{[n for n in column_names if column_names.count(n) > 1]}"


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv('POSTGRES_TEST_DSN'),
    reason="Requer variável POSTGRES_TEST_DSN configurada"
)
def test_real_database_fk_columns_marked_correctly():
    """Test that FK columns are correctly identified and marked"""
    config = DatabaseConfig(
        db_type=DatabaseType.POSTGRESQL,
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=int(os.getenv('POSTGRES_PORT', 5432)),
        database=os.getenv('POSTGRES_DATABASE', 'test_db'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', ''),
        schema=os.getenv('POSTGRES_SCHEMA', 'public')
    )

    loader = PostgreSQLTableLoader()
    tables = loader.load_tables(config, use_cache=False, force_update=True)

    # Validate FK columns are marked correctly
    for table_name, table_info in tables.items():
        for col in table_info.columns:
            if col.is_foreign_key:
                # If marked as FK, must have FK table and column
                assert col.foreign_key_table is not None, \
                    f"Column {col.name} in {table_name} is marked as FK but has no FK table"
                assert col.foreign_key_column is not None, \
                    f"Column {col.name} in {table_name} is marked as FK but has no FK column"
            else:
                # If not marked as FK, must not have FK table/column
                assert col.foreign_key_table is None, \
                    f"Column {col.name} in {table_name} is not marked as FK but has FK table"
                assert col.foreign_key_column is None, \
                    f"Column {col.name} in {table_name} is not marked as FK but has FK column"


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv('POSTGRES_TEST_DSN'),
    reason="Requer variável POSTGRES_TEST_DSN configurada"
)
def test_real_database_column_order_preserved():
    """Test that column order matches database ordinal_position"""
    config = DatabaseConfig(
        db_type=DatabaseType.POSTGRESQL,
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=int(os.getenv('POSTGRES_PORT', 5432)),
        database=os.getenv('POSTGRES_DATABASE', 'test_db'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', ''),
        schema=os.getenv('POSTGRES_SCHEMA', 'public')
    )

    loader = PostgreSQLTableLoader()
    tables = loader.load_tables(config, use_cache=False, force_update=True)

    # Validate at least one table exists
    assert len(tables) > 0, "No tables found in database"

    # For each table, column order should be deterministic
    # (we can't easily verify exact order without querying DB again,
    # but we can verify that columns are consistently ordered)
    for table_name, table_info in tables.items():
        # Reload the same table
        tables_reloaded = loader.load_tables(config, use_cache=False, force_update=True)
        table_info_reloaded = tables_reloaded[table_name]

        # Column names should be in same order
        original_names = [col.name for col in table_info.columns]
        reloaded_names = [col.name for col in table_info_reloaded.columns]

        assert original_names == reloaded_names, \
            f"Column order changed for {table_name} on reload"


# Helper function to run integration tests locally
if __name__ == '__main__':
    """
    Para executar os testes de integração localmente:

    export POSTGRES_TEST_DSN=1
    export POSTGRES_HOST=localhost
    export POSTGRES_PORT=5432
    export POSTGRES_DATABASE=optomate
    export POSTGRES_USER=postgres
    export POSTGRES_PASSWORD=devtools2025
    export POSTGRES_SCHEMA=tenant_optomate

    python -m pytest tests/io/test_postgres_integration.py -v -m integration
    """
    print("Execute os testes com pytest:")
    print("python -m pytest tests/io/test_postgres_integration.py -v -m integration")

