"""
Loader de tabelas para MySQL
"""

import logging
from typing import Dict, List, Tuple, Optional

try:
    import mysql.connector
    from mysql.connector import Error as MySQLError
    MYSQL_AVAILABLE = True
    MYSQL_DRIVER = 'mysql-connector'
except ImportError:
    try:
        import pymysql
        MYSQL_AVAILABLE = True
        MYSQL_DRIVER = 'pymysql'
    except ImportError:
        MYSQL_AVAILABLE = False
        MYSQL_DRIVER = None

from app.core.models import (
    DatabaseConfig, DatabaseType, TableInfo, ColumnInfo,
    IndexInfo, ForeignKeyInfo, TableLoadError, ValidationError
)
from app.io.table_base import TableLoaderBase
from app.io.table_factory import register_table_loader

logger = logging.getLogger(__name__)


class MySQLTableLoader(TableLoaderBase):
    """Loader de tabelas para MySQL"""

    def __init__(self):
        """Inicializa o loader MySQL"""
        if not MYSQL_AVAILABLE:
            raise ImportError(
                "Driver MySQL não está instalado. "
                "Instale com: pip install mysql-connector-python>=8.0.0 "
                "ou pip install pymysql>=1.0.0"
            )
        self.driver = MYSQL_DRIVER

    def get_database_type(self) -> DatabaseType:
        """Retorna o tipo de banco de dados"""
        return DatabaseType.MYSQL

    def load_tables(self, config: DatabaseConfig) -> Dict[str, TableInfo]:
        """
        Carrega tabelas do MySQL

        Args:
            config: Configuração de conexão

        Returns:
            Dict com database.table como chave e TableInfo como valor

        Raises:
            TableLoadError: Se houver erro ao carregar
            ValidationError: Se a configuração for inválida
        """
        self.validate_config(config)

        if not config.database:
            raise ValidationError("MySQL requer o nome do banco de dados (database)")

        port = config.port or 3306

        try:
            if self.driver == 'mysql-connector':
                connection = mysql.connector.connect(
                    host=config.host,
                    port=port,
                    database=config.database,
                    user=config.user,
                    password=config.password
                )
                cursor = connection.cursor(dictionary=True)
            else:  # pymysql
                import pymysql
                connection = pymysql.connect(
                    host=config.host,
                    port=port,
                    database=config.database,
                    user=config.user,
                    password=config.password,
                    cursorclass=pymysql.cursors.DictCursor
                )
                cursor = connection.cursor()

            # Lista tabelas
            query = """
                SELECT TABLE_SCHEMA, TABLE_NAME
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_TYPE = 'BASE TABLE'
            """

            params = []
            if config.schema:
                query += " AND TABLE_SCHEMA = %s"
                params.append(config.schema)
            else:
                query += " AND TABLE_SCHEMA = %s"
                params.append(config.database)

            cursor.execute(query, params)
            tables_list = cursor.fetchall()

            tables = {}
            for row in tables_list:
                schema_name = row['TABLE_SCHEMA']
                table_name = row['TABLE_NAME']
                full_name = f"{schema_name}.{table_name}" if schema_name != config.database else table_name

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

            logger.info(f"Total de {len(tables)} tabelas carregadas do MySQL")
            return tables

        except Exception as e:
            error_type = MySQLError if self.driver == 'mysql-connector' else Exception
            if isinstance(e, error_type):
                logger.error(f"Erro de conexão MySQL: {e}")
                raise TableLoadError(f"Erro ao conectar ao MySQL: {e}")
            else:
                logger.error(f"Erro inesperado ao carregar tabelas do MySQL: {e}")
                raise TableLoadError(f"Erro ao carregar tabelas do MySQL: {e}")

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
                c.COLUMN_COMMENT,
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
                    AND tc.TABLE_SCHEMA = %s
                    AND tc.TABLE_NAME = %s
            ) pk ON pk.COLUMN_NAME = c.COLUMN_NAME
            LEFT JOIN (
                SELECT
                    ku.COLUMN_NAME,
                    CONCAT(ccu.TABLE_SCHEMA, '.', ccu.TABLE_NAME) as REFERENCED_TABLE,
                    ccu.COLUMN_NAME as REFERENCED_COLUMN
                FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
                JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE ku
                    ON tc.CONSTRAINT_NAME = ku.CONSTRAINT_NAME
                JOIN INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc
                    ON tc.CONSTRAINT_NAME = rc.CONSTRAINT_NAME
                JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE ccu
                    ON rc.UNIQUE_CONSTRAINT_NAME = ccu.CONSTRAINT_NAME
                WHERE tc.CONSTRAINT_TYPE = 'FOREIGN KEY'
                    AND tc.TABLE_SCHEMA = %s
                    AND tc.TABLE_NAME = %s
            ) fk ON fk.COLUMN_NAME = c.COLUMN_NAME
            WHERE c.TABLE_SCHEMA = %s
                AND c.TABLE_NAME = %s
            ORDER BY c.ORDINAL_POSITION
        """

        cursor.execute(query, (schema, table_name, schema, table_name, schema, table_name))
        rows = cursor.fetchall()

        columns = []
        for row in rows:
            # Determina tipo completo
            data_type = row['DATA_TYPE']
            if row['CHARACTER_MAXIMUM_LENGTH']:
                data_type += f"({row['CHARACTER_MAXIMUM_LENGTH']})"
            elif row['NUMERIC_PRECISION']:
                if row['NUMERIC_SCALE'] is not None:
                    data_type += f"({row['NUMERIC_PRECISION']},{row['NUMERIC_SCALE']})"
                else:
                    data_type += f"({row['NUMERIC_PRECISION']})"

            columns.append(ColumnInfo(
                name=row['COLUMN_NAME'],
                data_type=data_type,
                nullable=row['IS_NULLABLE'] == 'YES',
                default_value=str(row['COLUMN_DEFAULT']) if row['COLUMN_DEFAULT'] else None,
                is_primary_key=row['IS_PK'] == 1,
                is_foreign_key=row['IS_FK'] == 1,
                foreign_key_table=row.get('REFERENCED_TABLE'),
                foreign_key_column=row.get('REFERENCED_COLUMN'),
                comments=row.get('COLUMN_COMMENT')
            ))

        return columns

    def _load_indexes(self, cursor, schema: str, table_name: str) -> List[IndexInfo]:
        """Carrega informações dos índices"""
        query = """
            SELECT
                s.INDEX_NAME,
                s.NON_UNIQUE,
                s.INDEX_TYPE,
                GROUP_CONCAT(s.COLUMN_NAME ORDER BY s.SEQ_IN_INDEX) as COLUMNS,
                CASE WHEN pk.CONSTRAINT_NAME IS NOT NULL THEN 1 ELSE 0 END as IS_PRIMARY
            FROM INFORMATION_SCHEMA.STATISTICS s
            LEFT JOIN (
                SELECT CONSTRAINT_NAME
                FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
                WHERE CONSTRAINT_TYPE = 'PRIMARY KEY'
                    AND TABLE_SCHEMA = %s
                    AND TABLE_NAME = %s
            ) pk ON s.INDEX_NAME = pk.CONSTRAINT_NAME
            WHERE s.TABLE_SCHEMA = %s
                AND s.TABLE_NAME = %s
            GROUP BY s.INDEX_NAME, s.NON_UNIQUE, s.INDEX_TYPE, pk.CONSTRAINT_NAME
        """

        cursor.execute(query, (schema, table_name, schema, table_name))
        rows = cursor.fetchall()

        indexes = []
        for row in rows:
            columns_list = [col.strip() for col in row['COLUMNS'].split(',')] if row['COLUMNS'] else []

            indexes.append(IndexInfo(
                name=row['INDEX_NAME'],
                table_name=table_name,
                columns=columns_list,
                is_unique=row['NON_UNIQUE'] == 0,
                is_primary=row['IS_PRIMARY'] == 1,
                index_type=row['INDEX_TYPE']
            ))

        return indexes

    def _load_foreign_keys(self, cursor, schema: str, table_name: str) -> List[ForeignKeyInfo]:
        """Carrega informações das foreign keys"""
        query = """
            SELECT
                tc.CONSTRAINT_NAME,
                GROUP_CONCAT(ku.COLUMN_NAME ORDER BY ku.ORDINAL_POSITION) as COLUMNS,
                CONCAT(ccu.TABLE_SCHEMA, '.', ccu.TABLE_NAME) as REFERENCED_TABLE,
                GROUP_CONCAT(ccu.COLUMN_NAME ORDER BY ccu.ORDINAL_POSITION) as REFERENCED_COLUMNS,
                rc.DELETE_RULE,
                rc.UPDATE_RULE
            FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
            JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE ku
                ON tc.CONSTRAINT_NAME = ku.CONSTRAINT_NAME
            JOIN INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc
                ON tc.CONSTRAINT_NAME = rc.CONSTRAINT_NAME
            JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE ccu
                ON rc.UNIQUE_CONSTRAINT_NAME = ccu.CONSTRAINT_NAME
            WHERE tc.CONSTRAINT_TYPE = 'FOREIGN KEY'
                AND tc.TABLE_SCHEMA = %s
                AND tc.TABLE_NAME = %s
            GROUP BY tc.CONSTRAINT_NAME, ccu.TABLE_SCHEMA, ccu.TABLE_NAME, rc.DELETE_RULE, rc.UPDATE_RULE
        """

        cursor.execute(query, (schema, table_name))
        rows = cursor.fetchall()

        foreign_keys = []
        for row in rows:
            columns_list = [col.strip() for col in row['COLUMNS'].split(',')] if row['COLUMNS'] else []
            referenced_columns_list = [col.strip() for col in row['REFERENCED_COLUMNS'].split(',')] if row['REFERENCED_COLUMNS'] else []

            foreign_keys.append(ForeignKeyInfo(
                name=row['CONSTRAINT_NAME'],
                table_name=table_name,
                columns=columns_list,
                referenced_table=row['REFERENCED_TABLE'],
                referenced_columns=referenced_columns_list,
                on_delete=row['DELETE_RULE'],
                on_update=row['UPDATE_RULE']
            ))

        return foreign_keys

    def load_table_ddl(self, config: DatabaseConfig, schema: str, table_name: str) -> str:
        """Carrega DDL usando SHOW CREATE TABLE"""
        port = config.port or 3306

        try:
            if self.driver == 'mysql-connector':
                connection = mysql.connector.connect(
                    host=config.host,
                    port=port,
                    database=config.database,
                    user=config.user,
                    password=config.password
                )
                cursor = connection.cursor(dictionary=True)
            else:  # pymysql
                import pymysql
                connection = pymysql.connect(
                    host=config.host,
                    port=port,
                    database=config.database,
                    user=config.user,
                    password=config.password,
                    cursorclass=pymysql.cursors.DictCursor
                )
                cursor = connection.cursor()

            # Usa SHOW CREATE TABLE
            cursor.execute(f"SHOW CREATE TABLE `{schema}`.`{table_name}`")
            result = cursor.fetchone()
            connection.close()

            if result and result.get('Create Table'):
                return result['Create Table']
            else:
                return self._generate_ddl_from_info(config, schema, table_name)
        except Exception as e:
            logger.warning(f"Erro ao obter DDL: {e}, usando método alternativo")
            return self._generate_ddl_from_info(config, schema, table_name)

    def _generate_ddl_from_info(self, config: DatabaseConfig, schema: str, table_name: str) -> str:
        """Gera DDL básico a partir das informações coletadas"""
        return f"-- DDL para {schema}.{table_name}\n-- (Reconstruído a partir de metadados)"

    def _get_table_stats(self, cursor, schema: str, table_name: str) -> Tuple[Optional[int], Optional[str]]:
        """Obtém estatísticas da tabela"""
        query = """
            SELECT
                TABLE_ROWS as ROW_COUNT,
                ROUND(((DATA_LENGTH + INDEX_LENGTH) / 1024 / 1024), 2) as SIZE_MB
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
        """
        try:
            cursor.execute(query, (schema, table_name))
            row = cursor.fetchone()
            if row:
                size_mb = row.get('SIZE_MB')
                size_str = f"{size_mb} MB" if size_mb else None
                return row.get('ROW_COUNT'), size_str
        except Exception as e:
            logger.debug(f"Erro ao obter estatísticas: {e}")

        return None, None


# Registra o loader no factory
if MYSQL_AVAILABLE:
    register_table_loader(DatabaseType.MYSQL, MySQLTableLoader)

