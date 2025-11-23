"""
Loader de tabelas para Microsoft SQL Server
"""

import logging
from typing import Dict, List, Tuple, Optional

try:
    import pyodbc
    PYODBC_AVAILABLE = True
except ImportError:
    PYODBC_AVAILABLE = False

from app.core.models import (
    DatabaseConfig, DatabaseType, TableInfo, ColumnInfo,
    IndexInfo, ForeignKeyInfo, TableLoadError, ValidationError
)
from app.io.table_base import TableLoaderBase
from app.io.table_factory import register_table_loader

logger = logging.getLogger(__name__)


class MSSQLTableLoader(TableLoaderBase):
    """Loader de tabelas para Microsoft SQL Server"""

    def __init__(self):
        """Inicializa o loader SQL Server"""
        if not PYODBC_AVAILABLE:
            raise ImportError(
                "pyodbc não está instalado. "
                "Instale com: pip install pyodbc>=5.0.0"
            )

    def get_database_type(self) -> DatabaseType:
        """Retorna o tipo de banco de dados"""
        return DatabaseType.MSSQL

    def load_tables(self, config: DatabaseConfig) -> Dict[str, TableInfo]:
        """
        Carrega tabelas do SQL Server

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
            raise ValidationError("SQL Server requer o nome do banco de dados (database)")

        port = config.port or 1433

        # Constrói connection string
        driver = config.extra_params.get('driver', 'ODBC Driver 17 for SQL Server')
        connection_string = (
            f"DRIVER={{{driver}}};"
            f"SERVER={config.host},{port};"
            f"DATABASE={config.database};"
            f"UID={config.user};"
            f"PWD={config.password}"
        )

        try:
            connection = pyodbc.connect(connection_string)
            cursor = connection.cursor()

            # Lista tabelas
            query = """
                SELECT TABLE_SCHEMA, TABLE_NAME
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_TYPE = 'BASE TABLE'
            """

            params = []
            if config.schema:
                query += " AND TABLE_SCHEMA = ?"
                params.append(config.schema)

            cursor.execute(query, params)
            tables_list = cursor.fetchall()

            tables = {}
            for row in tables_list:
                schema_name = row[0]
                table_name = row[1]
                full_name = f"{schema_name}.{table_name}" if schema_name != 'dbo' else table_name

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

            logger.info(f"Total de {len(tables)} tabelas carregadas do SQL Server")
            return tables

        except pyodbc.Error as e:
            logger.error(f"Erro de conexão SQL Server: {e}")
            raise TableLoadError(f"Erro ao conectar ao SQL Server: {e}")
        except Exception as e:
            logger.error(f"Erro inesperado ao carregar tabelas do SQL Server: {e}")
            raise TableLoadError(f"Erro ao carregar tabelas do SQL Server: {e}")

    def _load_table_details(
        self, cursor, schema: str, table_name: str, config: DatabaseConfig
    ) -> TableInfo:
        """Carrega detalhes completos de uma tabela"""

        # 1. Carrega DDL
        ddl = self.load_table_ddl(config, schema, table_name)

        # 2. Carrega colunas
        columns = self._load_columns(cursor, schema, table_name)

        # 3. Carrega índices
        indexes = self._load_indexes(cursor, schema, table_name)

        # 4. Carrega foreign keys
        foreign_keys = self._load_foreign_keys(cursor, schema, table_name)

        # 5. Identifica primary key
        primary_key_columns = [
            col.name for col in columns if col.is_primary_key
        ]

        # 6. Estatísticas
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
                c.COLUMN_NAME,
                c.DATA_TYPE,
                c.CHARACTER_MAXIMUM_LENGTH,
                c.NUMERIC_PRECISION,
                c.NUMERIC_SCALE,
                c.IS_NULLABLE,
                c.COLUMN_DEFAULT,
                CASE WHEN pk.COLUMN_NAME IS NOT NULL THEN 1 ELSE 0 END as IS_PK,
                CASE WHEN fk.COLUMN_NAME IS NOT NULL THEN 1 ELSE 0 END as IS_FK,
                fk.REFERENCED_TABLE,
                fk.REFERENCED_COLUMN
            FROM INFORMATION_SCHEMA.COLUMNS c
            LEFT JOIN (
                SELECT ku.COLUMN_NAME
                FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
                JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE ku
                    ON tc.CONSTRAINT_NAME = ku.CONSTRAINT_NAME
                WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
                    AND tc.TABLE_SCHEMA = ?
                    AND tc.TABLE_NAME = ?
            ) pk ON pk.COLUMN_NAME = c.COLUMN_NAME
            LEFT JOIN (
                SELECT
                    ku.COLUMN_NAME,
                    ccu.TABLE_SCHEMA + '.' + ccu.TABLE_NAME as REFERENCED_TABLE,
                    ccu.COLUMN_NAME as REFERENCED_COLUMN
                FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
                JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE ku
                    ON tc.CONSTRAINT_NAME = ku.CONSTRAINT_NAME
                JOIN INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc
                    ON tc.CONSTRAINT_NAME = rc.CONSTRAINT_NAME
                JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE ccu
                    ON rc.UNIQUE_CONSTRAINT_NAME = ccu.CONSTRAINT_NAME
                WHERE tc.CONSTRAINT_TYPE = 'FOREIGN KEY'
                    AND tc.TABLE_SCHEMA = ?
                    AND tc.TABLE_NAME = ?
            ) fk ON fk.COLUMN_NAME = c.COLUMN_NAME
            WHERE c.TABLE_SCHEMA = ?
                AND c.TABLE_NAME = ?
            ORDER BY c.ORDINAL_POSITION
        """

        cursor.execute(query, (schema, table_name, schema, table_name, schema, table_name))
        rows = cursor.fetchall()

        columns = []
        for row in rows:
            # Determina tipo completo
            data_type = row[1]  # DATA_TYPE
            if row[2]:  # CHARACTER_MAXIMUM_LENGTH
                data_type += f"({row[2]})"
            elif row[3]:  # NUMERIC_PRECISION
                if row[4] is not None:  # NUMERIC_SCALE
                    data_type += f"({row[3]},{row[4]})"
                else:
                    data_type += f"({row[3]})"

            columns.append(ColumnInfo(
                name=row[0],
                data_type=data_type,
                nullable=row[5] == 'YES',
                default_value=str(row[6]) if row[6] else None,
                is_primary_key=row[7] == 1,
                is_foreign_key=row[8] == 1,
                foreign_key_table=row[9],
                foreign_key_column=row[10]
            ))

        return columns

    def _load_indexes(self, cursor, schema: str, table_name: str) -> List[IndexInfo]:
        """Carrega informações dos índices"""
        query = """
            SELECT
                i.name as INDEX_NAME,
                i.is_unique,
                i.type_desc as INDEX_TYPE,
                STRING_AGG(c.name, ', ') WITHIN GROUP (ORDER BY ic.key_ordinal) as COLUMNS,
                CASE WHEN pk.name IS NOT NULL THEN 1 ELSE 0 END as IS_PRIMARY
            FROM sys.indexes i
            JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
            JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
            JOIN sys.tables t ON i.object_id = t.object_id
            JOIN sys.schemas s ON t.schema_id = s.schema_id
            LEFT JOIN sys.key_constraints pk ON i.object_id = pk.parent_object_id AND i.name = pk.name
            WHERE s.name = ? AND t.name = ?
                AND i.type_desc != 'HEAP'
            GROUP BY i.name, i.is_unique, i.type_desc, pk.name
        """

        cursor.execute(query, (schema, table_name))
        rows = cursor.fetchall()

        indexes = []
        for row in rows:
            columns_list = [col.strip() for col in row[3].split(',')] if row[3] else []

            indexes.append(IndexInfo(
                name=row[0],
                table_name=table_name,
                columns=columns_list,
                is_unique=row[1] == 1,
                is_primary=row[4] == 1,
                index_type=row[2]
            ))

        return indexes

    def _load_foreign_keys(self, cursor, schema: str, table_name: str) -> List[ForeignKeyInfo]:
        """Carrega informações das foreign keys"""
        query = """
            SELECT
                fk.name as CONSTRAINT_NAME,
                STRING_AGG(cp.name, ', ') WITHIN GROUP (ORDER BY cp.column_id) as COLUMNS,
                OBJECT_SCHEMA_NAME(fk.referenced_object_id) + '.' + OBJECT_NAME(fk.referenced_object_id) as REFERENCED_TABLE,
                STRING_AGG(cr.name, ', ') WITHIN GROUP (ORDER BY cr.column_id) as REFERENCED_COLUMNS,
                fk.delete_referential_action_desc,
                fk.update_referential_action_desc
            FROM sys.foreign_keys fk
            JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
            JOIN sys.columns cp ON fkc.parent_object_id = cp.object_id AND fkc.parent_column_id = cp.column_id
            JOIN sys.columns cr ON fkc.referenced_object_id = cr.object_id AND fkc.referenced_column_id = cr.column_id
            JOIN sys.tables t ON fk.parent_object_id = t.object_id
            JOIN sys.schemas s ON t.schema_id = s.schema_id
            WHERE s.name = ? AND t.name = ?
            GROUP BY fk.name, fk.referenced_object_id, fk.delete_referential_action_desc, fk.update_referential_action_desc
        """

        cursor.execute(query, (schema, table_name))
        rows = cursor.fetchall()

        foreign_keys = []
        for row in rows:
            columns_list = [col.strip() for col in row[1].split(',')] if row[1] else []
            referenced_columns_list = [col.strip() for col in row[3].split(',')] if row[3] else []

            foreign_keys.append(ForeignKeyInfo(
                name=row[0],
                table_name=table_name,
                columns=columns_list,
                referenced_table=row[2],
                referenced_columns=referenced_columns_list,
                on_delete=row[4].replace('_', ' ') if row[4] else None,
                on_update=row[5].replace('_', ' ') if row[5] else None
            ))

        return foreign_keys

    def load_table_ddl(self, config: DatabaseConfig, schema: str, table_name: str) -> str:
        """Carrega DDL usando sp_help ou query direta"""
        port = config.port or 1433
        driver = config.extra_params.get('driver', 'ODBC Driver 17 for SQL Server')
        connection_string = (
            f"DRIVER={{{driver}}};"
            f"SERVER={config.host},{port};"
            f"DATABASE={config.database};"
            f"UID={config.user};"
            f"PWD={config.password}"
        )

        try:
            connection = pyodbc.connect(connection_string)
            cursor = connection.cursor()

            # Tenta obter DDL via query
            # SQL Server não tem função nativa, então reconstrói
            ddl = self._generate_ddl_from_info(cursor, schema, table_name)
            connection.close()
            return ddl
        except Exception as e:
            logger.warning(f"Erro ao obter DDL: {e}")
            return f"-- DDL para {schema}.{table_name}\n-- (Erro ao reconstruir: {e})"

    def _generate_ddl_from_info(self, cursor, schema: str, table_name: str) -> str:
        """Gera DDL a partir das informações coletadas"""
        columns = self._load_columns(cursor, schema, table_name)
        foreign_keys = self._load_foreign_keys(cursor, schema, table_name)

        ddl_lines = [f"CREATE TABLE [{schema}].[{table_name}] ("]

        col_defs = []
        for col in columns:
            col_def = f"    [{col.name}] {col.data_type}"
            if not col.nullable:
                col_def += " NOT NULL"
            if col.default_value:
                col_def += f" DEFAULT {col.default_value}"
            col_defs.append(col_def)

        ddl_lines.append(",\n".join(col_defs))

        # Adiciona primary key
        pk_cols = [col.name for col in columns if col.is_primary_key]
        if pk_cols:
            ddl_lines.append(f",\n    PRIMARY KEY ([{'], ['.join(pk_cols)}])")

        # Adiciona foreign keys
        for fk in foreign_keys:
            fk_def = f"    CONSTRAINT [{fk.name}] FOREIGN KEY ([{'], ['.join(fk.columns)}])"
            fk_def += f" REFERENCES {fk.referenced_table} ([{'], ['.join(fk.referenced_columns)}])"
            if fk.on_delete:
                fk_def += f" ON DELETE {fk.on_delete}"
            if fk.on_update:
                fk_def += f" ON UPDATE {fk.on_update}"
            ddl_lines.append(f",\n{fk_def}")

        ddl_lines.append("\n);")
        return "\n".join(ddl_lines)

    def _get_table_stats(self, cursor, schema: str, table_name: str) -> Tuple[Optional[int], Optional[str]]:
        """Obtém estatísticas da tabela"""
        query = """
            SELECT
                p.rows as ROW_COUNT,
                CAST(ROUND(((SUM(a.total_pages) * 8) / 1024.0), 2) AS VARCHAR) + ' MB' as SIZE_MB
            FROM sys.tables t
            JOIN sys.schemas s ON t.schema_id = s.schema_id
            JOIN sys.indexes i ON t.object_id = i.object_id
            JOIN sys.partitions p ON i.object_id = p.object_id AND i.index_id = p.index_id
            JOIN sys.allocation_units a ON p.partition_id = a.container_id
            WHERE s.name = ? AND t.name = ?
            GROUP BY p.rows
        """
        try:
            cursor.execute(query, (schema, table_name))
            row = cursor.fetchone()
            if row:
                return row[0], row[1]
        except Exception as e:
            logger.debug(f"Erro ao obter estatísticas: {e}")

        return None, None


# Registra o loader no factory
if PYODBC_AVAILABLE:
    register_table_loader(DatabaseType.MSSQL, MSSQLTableLoader)

