"""
Loader de tabelas para PostgreSQL
"""

import logging
from typing import Dict, List, Tuple, Optional

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

from app.core.models import (
    DatabaseConfig, DatabaseType, TableInfo, ColumnInfo,
    IndexInfo, ForeignKeyInfo, TableLoadError, ValidationError
)
from app.io.table_base import TableLoaderBase
from app.io.table_factory import register_table_loader

logger = logging.getLogger(__name__)


class PostgreSQLTableLoader(TableLoaderBase):
    """Loader de tabelas para PostgreSQL"""

    def __init__(self):
        """Inicializa o loader PostgreSQL"""
        if not PSYCOPG2_AVAILABLE:
            raise ImportError(
                "psycopg2 não está instalado. "
                "Instale com: pip install psycopg2-binary>=2.9.0"
            )

    def get_database_type(self) -> DatabaseType:
        """Retorna o tipo de banco de dados"""
        return DatabaseType.POSTGRESQL

    def load_tables(self, config: DatabaseConfig) -> Dict[str, TableInfo]:
        """
        Carrega tabelas do PostgreSQL

        Args:
            config: Configuração de conexão

        Returns:
            Dict com schema.table como chave e TableInfo como valor

        Raises:
            TableLoadError: Se houver erro ao carregar
            ValidationError: Se a configuração for inválida
        """
        self.validate_config(config)

        if not config.database:
            raise ValidationError("PostgreSQL requer o nome do banco de dados (database)")

        port = config.port or 5432

        try:
            connection = psycopg2.connect(
                host=config.host,
                port=port,
                database=config.database,
                user=config.user,
                password=config.password
            )
            cursor = connection.cursor(cursor_factory=RealDictCursor)

            # Lista tabelas
            query = """
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_type = 'BASE TABLE'
                AND table_schema NOT IN ('pg_catalog', 'information_schema')
            """

            params = []
            if config.schema:
                query += " AND table_schema = %s"
                params.append(config.schema)

            cursor.execute(query, params)
            tables_list = cursor.fetchall()

            tables = {}
            for row in tables_list:
                schema_name = row['table_schema']
                table_name = row['table_name']
                full_name = f"{schema_name}.{table_name}" if schema_name != 'public' else table_name

                try:
                    table_info = self._load_table_details(
                        cursor, schema_name, table_name, config
                    )
                    tables[full_name] = table_info
                    logger.info(f"Carregado: {full_name}")
                except Exception as e:
                    logger.error(f"Erro ao carregar {full_name}: {e}")
                    continue

            connection.close()

            if not tables:
                raise TableLoadError("Nenhuma tabela encontrada no banco de dados")

            logger.info(f"Total de {len(tables)} tabelas carregadas do PostgreSQL")
            return tables

        except psycopg2.Error as e:
            logger.error(f"Erro de conexão PostgreSQL: {e}")
            raise TableLoadError(f"Erro ao conectar ao PostgreSQL: {e}")
        except Exception as e:
            logger.error(f"Erro inesperado ao carregar tabelas do PostgreSQL: {e}")
            raise TableLoadError(f"Erro ao carregar tabelas do PostgreSQL: {e}")

    def _load_table_details(
        self, cursor, schema: str, table_name: str, config: DatabaseConfig
    ) -> TableInfo:
        """Carrega detalhes completos de uma tabela"""

        # 1. Carrega colunas
        columns = self._load_columns(cursor, schema, table_name)

        # 3. Carrega índices
        indexes = self._load_indexes(cursor, schema, table_name)

        # 4. Carrega foreign keys
        foreign_keys = self._load_foreign_keys(cursor, schema, table_name)

        # 5. Identifica primary key
        primary_key_columns = [
            col.name for col in columns if col.is_primary_key
        ]

        # 6. Gera DDL a partir das informações coletadas
        ddl = self._generate_ddl_from_info(columns, foreign_keys, schema, table_name)

        # 7. Estatísticas (opcional)
        row_count, table_size = self._get_table_stats(cursor, schema, table_name)

        return TableInfo(
            name=table_name,
            schema=schema,
            ddl=ddl,
            columns=columns,
            indexes=indexes,
            foreign_keys=foreign_keys,
            primary_key_columns=primary_key_columns,
            row_count=row_count,
            table_size=table_size
        )

    def _load_columns(self, cursor, schema: str, table_name: str) -> List[ColumnInfo]:
        """Carrega informações das colunas"""
        query = """
            SELECT
                c.column_name,
                c.data_type,
                c.is_nullable,
                c.column_default,
                c.character_maximum_length,
                c.numeric_precision,
                c.numeric_scale,
                CASE WHEN pk.column_name IS NOT NULL THEN true ELSE false END as is_pk,
                CASE WHEN fk.column_name IS NOT NULL THEN true ELSE false END as is_fk,
                fk.referenced_table,
                fk.referenced_column,
                col_description(pgc.oid, c.ordinal_position) as column_comment
            FROM information_schema.columns c
            JOIN pg_class pgc ON pgc.relname = c.table_name
            JOIN pg_namespace pgn ON pgn.oid = pgc.relnamespace AND pgn.nspname = c.table_schema
            LEFT JOIN (
                SELECT ku.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage ku
                    ON tc.constraint_name = ku.constraint_name
                WHERE tc.constraint_type = 'PRIMARY KEY'
                    AND tc.table_schema = %s
                    AND tc.table_name = %s
            ) pk ON pk.column_name = c.column_name
            LEFT JOIN (
                SELECT
                    ku.column_name,
                    ccu.table_schema || '.' || ccu.table_name as referenced_table,
                    ccu.column_name as referenced_column
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage ku
                    ON tc.constraint_name = ku.constraint_name
                JOIN information_schema.constraint_column_usage ccu
                    ON tc.constraint_name = ccu.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                    AND tc.table_schema = %s
                    AND tc.table_name = %s
            ) fk ON fk.column_name = c.column_name
            WHERE c.table_schema = %s
                AND c.table_name = %s
            ORDER BY c.ordinal_position
        """

        cursor.execute(query, (schema, table_name, schema, table_name, schema, table_name))
        rows = cursor.fetchall()

        columns = []
        for row in rows:
            # Determina tipo completo
            data_type = row['data_type']
            if row['character_maximum_length']:
                data_type += f"({row['character_maximum_length']})"
            elif row['numeric_precision']:
                if row['numeric_scale']:
                    data_type += f"({row['numeric_precision']},{row['numeric_scale']})"
                else:
                    data_type += f"({row['numeric_precision']})"

            columns.append(ColumnInfo(
                name=row['column_name'],
                data_type=data_type,
                nullable=row['is_nullable'] == 'YES',
                default_value=row['column_default'],
                is_primary_key=row['is_pk'],
                is_foreign_key=row['is_fk'],
                foreign_key_table=row.get('referenced_table'),
                foreign_key_column=row.get('referenced_column'),
                comments=row.get('column_comment')
            ))

        return columns

    def _load_indexes(self, cursor, schema: str, table_name: str) -> List[IndexInfo]:
        """Carrega informações dos índices"""
        query = """
            SELECT
                i.indexname as index_name,
                i.indexdef,
                CASE WHEN i.indexdef LIKE '%UNIQUE%' THEN true ELSE false END as is_unique,
                CASE WHEN pk.constraint_name IS NOT NULL THEN true ELSE false END as is_primary,
                am.amname as index_type
            FROM pg_indexes i
            JOIN pg_class pgc ON pgc.relname = i.tablename
            JOIN pg_namespace pgn ON pgn.oid = pgc.relnamespace AND pgn.nspname = i.schemaname
            JOIN pg_index pgi ON pgi.indexrelid = (
                SELECT oid FROM pg_class WHERE relname = i.indexname
            )
            JOIN pg_am am ON am.oid = (
                SELECT relam FROM pg_class WHERE relname = i.indexname
            )
            LEFT JOIN (
                SELECT constraint_name
                FROM information_schema.table_constraints
                WHERE constraint_type = 'PRIMARY KEY'
                    AND table_schema = %s
                    AND table_name = %s
            ) pk ON i.indexname LIKE '%' || pk.constraint_name || '%'
            WHERE i.schemaname = %s
                AND i.tablename = %s
        """

        cursor.execute(query, (schema, table_name, schema, table_name))
        rows = cursor.fetchall()

        indexes = []
        for row in rows:
            # Extrai colunas do indexdef
            # Exemplo: "CREATE INDEX idx_name ON table (col1, col2)"
            indexdef = row['indexdef']
            columns_str = ""
            if '(' in indexdef:
                try:
                    columns_str = indexdef.split('(')[1].split(')')[0]
                except IndexError:
                    columns_str = ""
            columns = [col.strip().strip('"') for col in columns_str.split(',') if col.strip()] if columns_str else []

            indexes.append(IndexInfo(
                name=row['index_name'],
                table_name=table_name,
                columns=columns,
                is_unique=row['is_unique'],
                is_primary=row['is_primary'],
                index_type=row.get('index_type')
            ))

        return indexes

    def _load_foreign_keys(self, cursor, schema: str, table_name: str) -> List[ForeignKeyInfo]:
        """Carrega informações das foreign keys"""
        query = """
            SELECT
                tc.constraint_name,
                ku.column_name,
                ccu.table_schema || '.' || ccu.table_name as referenced_table,
                ccu.column_name as referenced_column,
                rc.delete_rule,
                rc.update_rule
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage ku
                ON tc.constraint_name = ku.constraint_name
            JOIN information_schema.constraint_column_usage ccu
                ON tc.constraint_name = ccu.constraint_name
            JOIN information_schema.referential_constraints rc
                ON tc.constraint_name = rc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_schema = %s
                AND tc.table_name = %s
            ORDER BY tc.constraint_name, ku.ordinal_position
        """

        cursor.execute(query, (schema, table_name))
        rows = cursor.fetchall()

        # Agrupa por constraint_name
        fk_dict = {}
        for row in rows:
            constraint_name = row['constraint_name']
            if constraint_name not in fk_dict:
                fk_dict[constraint_name] = {
                    'columns': [],
                    'referenced_table': row['referenced_table'],
                    'referenced_columns': [],
                    'on_delete': row['delete_rule'],
                    'on_update': row['update_rule']
                }
            fk_dict[constraint_name]['columns'].append(row['column_name'])
            fk_dict[constraint_name]['referenced_columns'].append(row['referenced_column'])

        foreign_keys = []
        for constraint_name, fk_data in fk_dict.items():
            foreign_keys.append(ForeignKeyInfo(
                name=constraint_name,
                table_name=table_name,
                columns=fk_data['columns'],
                referenced_table=fk_data['referenced_table'],
                referenced_columns=fk_data['referenced_columns'],
                on_delete=fk_data['on_delete'],
                on_update=fk_data['on_update']
            ))

        return foreign_keys

    def load_table_ddl(self, config: DatabaseConfig, schema: str, table_name: str) -> str:
        """
        Carrega DDL completo reconstruindo a partir de metadados

        Args:
            config: Configuração de conexão
            schema: Schema da tabela
            table_name: Nome da tabela

        Returns:
            DDL completo da tabela
        """
        port = config.port or 5432
        try:
            connection = psycopg2.connect(
                host=config.host,
                port=port,
                database=config.database,
                user=config.user,
                password=config.password
            )
            cursor = connection.cursor(cursor_factory=RealDictCursor)

            # Carrega informações necessárias para reconstruir DDL
            columns = self._load_columns(cursor, schema, table_name)
            foreign_keys = self._load_foreign_keys(cursor, schema, table_name)

            ddl = self._generate_ddl_from_info(columns, foreign_keys, schema, table_name)
            connection.close()

            return ddl
        except Exception as e:
            logger.warning(f"Erro ao gerar DDL: {e}")
            return f"-- DDL para {schema}.{table_name}\n-- (Erro ao reconstruir: {e})"

    def _get_table_stats(self, cursor, schema: str, table_name: str) -> Tuple[Optional[int], Optional[str]]:
        """Obtém estatísticas da tabela (row count, size)"""
        query = """
            SELECT
                n_live_tup as row_count,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
            FROM pg_stat_user_tables
            WHERE schemaname = %s AND relname = %s
        """
        try:
            cursor.execute(query, (schema, table_name))
            row = cursor.fetchone()
            if row:
                return row.get('row_count'), row.get('size')
        except Exception as e:
            logger.debug(f"Erro ao obter estatísticas da tabela {schema}.{table_name}: {e}")

        return None, None


# Registra o loader no factory
if PSYCOPG2_AVAILABLE:
    register_table_loader(DatabaseType.POSTGRESQL, PostgreSQLTableLoader)

