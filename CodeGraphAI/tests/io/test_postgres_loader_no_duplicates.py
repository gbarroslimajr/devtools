"""
Testes para validar que o PostgreSQL Loader não retorna colunas duplicadas
"""
import pytest
from unittest.mock import Mock, MagicMock
from app.io.postgres_table_loader import PostgreSQLTableLoader


def test_load_columns_no_duplicates():
    """Ensure _load_columns doesn't return duplicate columns"""
    loader = PostgreSQLTableLoader()

    # Mock cursor with realistic data
    cursor = Mock()

    # Mock for main query (without FK inline)
    cursor.fetchall.return_value = [
        {
            'column_name': 'id',
            'data_type': 'bigint',
            'is_nullable': 'NO',
            'column_default': None,
            'character_maximum_length': None,
            'numeric_precision': 64,
            'numeric_scale': 0,
            'is_pk': True,
            'column_comment': None
        },
        {
            'column_name': 'created_by',
            'data_type': 'bigint',
            'is_nullable': 'YES',
            'column_default': None,
            'character_maximum_length': None,
            'numeric_precision': 64,
            'numeric_scale': 0,
            'is_pk': False,
            'column_comment': None
        }
    ]

    # Mock FK mapping (will be called by _load_fk_column_mapping)
    # We need to set up the cursor to return the FK data on the second fetchall call
    def fetchall_side_effect(*args, **kwargs):
        # First call: columns
        # Second call: FK mapping
        if cursor.fetchall.call_count == 1:
            return [
                {
                    'column_name': 'id',
                    'data_type': 'bigint',
                    'is_nullable': 'NO',
                    'column_default': None,
                    'character_maximum_length': None,
                    'numeric_precision': 64,
                    'numeric_scale': 0,
                    'is_pk': True,
                    'column_comment': None
                },
                {
                    'column_name': 'created_by',
                    'data_type': 'bigint',
                    'is_nullable': 'YES',
                    'column_default': None,
                    'character_maximum_length': None,
                    'numeric_precision': 64,
                    'numeric_scale': 0,
                    'is_pk': False,
                    'column_comment': None
                }
            ]
        else:
            # FK mapping data
            return [
                {
                    'column_name': 'created_by',
                    'referenced_table': 'tenant_optomate.users',
                    'referenced_column': 'id'
                }
            ]

    cursor.fetchall = Mock(side_effect=fetchall_side_effect)
    cursor.fetchall.call_count = 0

    columns = loader._load_columns(cursor, 'tenant_optomate', 'appointments')

    # Validate no duplicates
    column_names = [col.name for col in columns]
    unique_names = set(column_names)

    assert len(column_names) == len(unique_names), \
        f"Found duplicate columns: {[n for n in column_names if column_names.count(n) > 1]}"

    # Validate structure
    assert len(columns) == 2
    assert columns[0].name == 'id'
    assert columns[0].is_primary_key is True
    assert columns[1].name == 'created_by'
    assert columns[1].is_foreign_key is True
    assert columns[1].foreign_key_table == 'tenant_optomate.users'


def test_fk_column_mapping_handles_multiple_constraints():
    """Test that multiple FK constraints on same column only returns first"""
    loader = PostgreSQLTableLoader()

    cursor = Mock()
    cursor.fetchall.return_value = [
        {
            'column_name': 'created_by',
            'referenced_table': 'tenant_optomate.users',
            'referenced_column': 'id'
        },
        {
            'column_name': 'created_by',
            'referenced_table': 'tenant_optomate.audit_log',
            'referenced_column': 'user_id'
        },
        {
            'column_name': 'patient_id',
            'referenced_table': 'tenant_optomate.patients',
            'referenced_column': 'id'
        }
    ]

    fk_map = loader._load_fk_column_mapping(cursor, 'tenant_optomate', 'appointments')

    # Should only have 2 entries (created_by and patient_id)
    assert len(fk_map) == 2
    assert 'created_by' in fk_map
    assert 'patient_id' in fk_map

    # created_by should have the first constraint
    assert fk_map['created_by']['table'] == 'tenant_optomate.users'
    assert fk_map['created_by']['column'] == 'id'


def test_fk_column_mapping_empty_result():
    """Test that _load_fk_column_mapping handles tables with no FKs"""
    loader = PostgreSQLTableLoader()

    cursor = Mock()
    cursor.fetchall.return_value = []

    fk_map = loader._load_fk_column_mapping(cursor, 'tenant_optomate', 'simple_table')

    assert fk_map == {}


def test_load_columns_integrates_fk_correctly():
    """Test that _load_columns correctly integrates FK information from _load_fk_column_mapping"""
    loader = PostgreSQLTableLoader()

    cursor = Mock()

    # Setup mock to return different results for each query
    def fetchall_side_effect(*args, **kwargs):
        call_count = cursor.execute.call_count
        if call_count == 1:
            # First call: column data
            return [
                {
                    'column_name': 'id',
                    'data_type': 'uuid',
                    'is_nullable': 'NO',
                    'column_default': 'uuid_generate_v4()',
                    'character_maximum_length': None,
                    'numeric_precision': None,
                    'numeric_scale': None,
                    'is_pk': True,
                    'column_comment': None
                },
                {
                    'column_name': 'user_id',
                    'data_type': 'uuid',
                    'is_nullable': 'NO',
                    'column_default': None,
                    'character_maximum_length': None,
                    'numeric_precision': None,
                    'numeric_scale': None,
                    'is_pk': False,
                    'column_comment': None
                },
                {
                    'column_name': 'name',
                    'data_type': 'character varying',
                    'is_nullable': 'YES',
                    'column_default': None,
                    'character_maximum_length': 255,
                    'numeric_precision': None,
                    'numeric_scale': None,
                    'is_pk': False,
                    'column_comment': None
                }
            ]
        else:
            # Second call: FK mapping
            return [
                {
                    'column_name': 'user_id',
                    'referenced_table': 'tenant_optomate.users',
                    'referenced_column': 'id'
                }
            ]

    cursor.fetchall = Mock(side_effect=fetchall_side_effect)
    cursor.execute = Mock()

    columns = loader._load_columns(cursor, 'tenant_optomate', 'test_table')

    # Validate
    assert len(columns) == 3

    # id column - PK, not FK
    assert columns[0].name == 'id'
    assert columns[0].is_primary_key is True
    assert columns[0].is_foreign_key is False
    assert columns[0].foreign_key_table is None

    # user_id column - FK
    assert columns[1].name == 'user_id'
    assert columns[1].is_primary_key is False
    assert columns[1].is_foreign_key is True
    assert columns[1].foreign_key_table == 'tenant_optomate.users'
    assert columns[1].foreign_key_column == 'id'

    # name column - regular column
    assert columns[2].name == 'name'
    assert columns[2].is_primary_key is False
    assert columns[2].is_foreign_key is False
    assert columns[2].data_type == 'character varying(255)'

