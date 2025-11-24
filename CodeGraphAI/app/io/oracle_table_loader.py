"""
Loader de tabelas para Oracle Database
"""

import logging
from typing import Dict, List, Tuple, Optional

try:
    import oracledb

    ORACLEDB_AVAILABLE = True
except ImportError:
    ORACLEDB_AVAILABLE = False

from app.core.models import (
    DatabaseConfig, DatabaseType, TableInfo, ColumnInfo,
    IndexInfo, ForeignKeyInfo, TableLoadError, ValidationError
)
from app.io.table_base import TableLoaderBase
from app.io.table_factory import register_table_loader

logger = logging.getLogger(__name__)


class OracleTableLoader(TableLoaderBase):
    """Loader de tabelas para Oracle Database"""

    def __init__(self):
        """Inicializa o loader Oracle"""
        if not ORACLEDB_AVAILABLE:
            raise ImportError(
                "oracledb não está instalado. "
                "Instale com: pip install oracledb>=1.4.0"
            )

    def get_database_type(self) -> DatabaseType:
        """Retorna o tipo de banco de dados"""
        return DatabaseType.ORACLE

    def load_tables(self, config: DatabaseConfig) -> Dict[str, TableInfo]:
        """
        Carrega tabelas do Oracle Database

        Args:
            config: Configuração de conexão

        Returns:
            Dict com schema.table como chave e TableInfo como valor

        Raises:
            TableLoadError: Se houver erro ao carregar
            ValidationError: Se a configuração for inválida
        """
        self.validate_config(config)

        # Parse DSN
        dsn_parts = config.host.split('/')
        if len(dsn_parts) == 2:
            host_port = dsn_parts[0]
            service = dsn_parts[1]
        else:
            host_port = config.host
            service = None

        if ':' in host_port:
            host, port_str = host_port.split(':')
            try:
                port = int(port_str)
            except ValueError:
                port = 1521
        else:
            host = host_port
            port = 1521

        dsn = f"{host}:{port}/{service}" if service else f"{host}:{port}"

        try:
            connection = oracledb.connect(
                user=config.user,
                password=config.password,
                dsn=dsn
            )
            cursor = connection.cursor()

            # Lista tabelas
            query = """
                    SELECT owner, table_name
                    FROM all_tables
                    WHERE owner NOT IN ('SYS', 'SYSTEM', 'SYSAUX') \
                    """

            params = []
            if config.schema:
                query += " AND owner = :schema"
                params.append(config.schema)

            cursor.execute(query, params)
            tables_list = cursor.fetchall()

            tables = {}
            for row in tables_list:
                schema_name = row[0]
                table_name = row[1]
                full_name = f"{schema_name}.{table_name}"

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

            logger.info(f"Total de {len(tables)} tabelas carregadas do Oracle")
            return tables

        except oracledb.Error as e:
            logger.error(f"Erro de conexão Oracle: {e}")
            raise TableLoadError(f"Erro ao conectar ao Oracle: {e}")
        except Exception as e:
            logger.error(f"Erro inesperado ao carregar tabelas do Oracle: {e}")
            raise TableLoadError(f"Erro ao carregar tabelas do Oracle: {e}")

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
                SELECT c.column_name,
                       c.data_type,
                       c.data_length,
                       c.data_precision,
                       c.data_scale,
                       c.nullable,
                       c.data_default,
                       CASE WHEN pk.column_name IS NOT NULL THEN 'Y' ELSE 'N' END as is_pk,
                       CASE WHEN fk.column_name IS NOT NULL THEN 'Y' ELSE 'N' END as is_fk,
                       fk.referenced_table,
                       fk.referenced_column,
                       c.comments
                FROM all_tab_columns c
                         LEFT JOIN (SELECT ku.column_name
                                    FROM all_constraints tc
                                             JOIN all_cons_columns ku ON tc.constraint_name = ku.constraint_name
                                    WHERE tc.constraint_type = 'P'
                                      AND tc.owner = :schema
                                      AND tc.table_name = :table_name) pk ON pk.column_name = c.column_name
                         LEFT JOIN (SELECT ku.column_name,
                                           ccu.owner || '.' || ccu.table_name as referenced_table,
                                           ccu.column_name                    as referenced_column
                                    FROM all_constraints tc
                                             JOIN all_cons_columns ku ON tc.constraint_name = ku.constraint_name
                                             JOIN all_constraints ccu_const
                                                  ON tc.r_constraint_name = ccu_const.constraint_name
                                             JOIN all_cons_columns ccu ON ccu_const.constraint_name = ccu.constraint_name
                                    WHERE tc.constraint_type = 'R'
                                      AND tc.owner = :schema
                                      AND tc.table_name = :table_name) fk ON fk.column_name = c.column_name
                WHERE c.owner = :schema
                  AND c.table_name = :table_name
                ORDER BY c.column_id \
                """

        cursor.execute(query, {'schema': schema, 'table_name': table_name})
        rows = cursor.fetchall()

        columns = []
        for row in rows:
            # Determina tipo completo
            data_type = row[1]  # data_type
            if row[2]:  # data_length
                if row[4] is not None:  # data_scale
                    data_type += f"({row[3]},{row[4]})"  # precision, scale
                elif row[3] is not None:  # data_precision
                    data_type += f"({row[3]})"
                else:
                    data_type += f"({row[2]})"

            columns.append(ColumnInfo(
                name=row[0],
                data_type=data_type,
                nullable=row[5] == 'Y',
                default_value=str(row[6]) if row[6] else None,
                is_primary_key=row[7] == 'Y',
                is_foreign_key=row[8] == 'Y',
                foreign_key_table=row[9],
                foreign_key_column=row[10],
                comments=row[11]
            ))

        return columns

    def _load_indexes(self, cursor, schema: str, table_name: str) -> List[IndexInfo]:
        """Carrega informações dos índices"""
        query = """
                SELECT i.index_name,
                       i.uniqueness,
                       i.index_type,
                       LISTAGG(ic.column_name, ', ') WITHIN GROUP (ORDER BY ic.column_position) as columns,
                       CASE WHEN pk.constraint_name IS NOT NULL THEN 'Y' ELSE 'N' END           as is_primary
                FROM all_indexes i
                         JOIN all_ind_columns ic ON i.index_name = ic.index_name AND i.owner = ic.index_owner
                         LEFT JOIN (SELECT constraint_name
                                    FROM all_constraints
                                    WHERE constraint_type = 'P'
                                      AND owner = :schema
                                      AND table_name = :table_name) pk ON i.index_name = pk.constraint_name
                WHERE i.table_owner = :schema
                  AND i.table_name = :table_name
                  AND i.index_type != 'LOB'
                GROUP BY i.index_name, i.uniqueness, i.index_type, pk.constraint_name \
                """

        cursor.execute(query, {'schema': schema, 'table_name': table_name})
        rows = cursor.fetchall()

        indexes = []
        for row in rows:
            columns_list = [col.strip() for col in row[3].split(',')] if row[3] else []

            indexes.append(IndexInfo(
                name=row[0],
                table_name=table_name,
                columns=columns_list,
                is_unique=row[1] == 'UNIQUE',
                is_primary=row[4] == 'Y',
                index_type=row[2]
            ))

        return indexes

    def _load_foreign_keys(self, cursor, schema: str, table_name: str) -> List[ForeignKeyInfo]:
        """Carrega informações das foreign keys"""
        query = """
                SELECT tc.constraint_name,
                       LISTAGG(ku.column_name, ', ') WITHIN GROUP (ORDER BY ku.position)   as columns,
                       ccu.owner || '.' || ccu.table_name                                  as referenced_table,
                       LISTAGG(ccu.column_name, ', ') WITHIN GROUP (ORDER BY ccu.position) as referenced_columns,
                       rc.delete_rule,
                       rc.update_rule
                FROM all_constraints tc
                         JOIN all_cons_columns ku ON tc.constraint_name = ku.constraint_name
                         JOIN all_constraints ccu_const ON tc.r_constraint_name = ccu_const.constraint_name
                         JOIN all_cons_columns ccu ON ccu_const.constraint_name = ccu.constraint_name
                         JOIN all_constraints rc ON tc.constraint_name = rc.constraint_name
                WHERE tc.constraint_type = 'R'
                  AND tc.owner = :schema
                  AND tc.table_name = :table_name
                GROUP BY tc.constraint_name, ccu.owner, ccu.table_name, rc.delete_rule, rc.update_rule \
                """

        cursor.execute(query, {'schema': schema, 'table_name': table_name})
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
                on_delete=row[4],
                on_update=row[5]
            ))

        return foreign_keys

    def load_table_ddl(self, config: DatabaseConfig, schema: str, table_name: str) -> str:
        """
        Carrega DDL completo usando DBMS_METADATA

        Args:
            config: Configuração de conexão
            schema: Schema da tabela
            table_name: Nome da tabela

        Returns:
            DDL completo da tabela
        """
        # Parse DSN
        dsn_parts = config.host.split('/')
        if len(dsn_parts) == 2:
            host_port = dsn_parts[0]
            service = dsn_parts[1]
        else:
            host_port = config.host
            service = None

        if ':' in host_port:
            host, port_str = host_port.split(':')
            try:
                port = int(port_str)
            except ValueError:
                port = 1521
        else:
            host = host_port
            port = 1521

        dsn = f"{host}:{port}/{service}" if service else f"{host}:{port}"

        try:
            connection = oracledb.connect(
                user=config.user,
                password=config.password,
                dsn=dsn
            )
            cursor = connection.cursor()

            # Usa DBMS_METADATA para obter DDL
            cursor.execute("""
                           SELECT DBMS_METADATA.GET_DDL('TABLE', :table_name, :schema)
                           FROM DUAL
                           """, {'table_name': table_name, 'schema': schema})

            result = cursor.fetchone()
            connection.close()

            if result and result[0]:
                return result[0]
            else:
                return self._generate_ddl_from_info(config, schema, table_name)
        except Exception as e:
            logger.warning(f"Erro ao obter DDL via DBMS_METADATA: {e}, usando método alternativo")
            return self._generate_ddl_from_info(config, schema, table_name)

    def _generate_ddl_from_info(self, config: DatabaseConfig, schema: str, table_name: str) -> str:
        """Gera DDL básico a partir das informações coletadas"""
        return f"-- DDL para {schema}.{table_name}\n-- (Reconstruído a partir de metadados)"

    def _get_table_stats(self, cursor, schema: str, table_name: str) -> Tuple[Optional[int], Optional[str]]:
        """Obtém estatísticas da tabela"""
        query = """
                SELECT num_rows,
                       ROUND(blocks * 8192 / 1024 / 1024, 2) || ' MB' as size_mb
                FROM all_tables
                WHERE owner = :schema
                  AND table_name = :table_name \
                """
        try:
            cursor.execute(query, {'schema': schema, 'table_name': table_name})
            row = cursor.fetchone()
            if row:
                return row[0], row[1]
        except Exception as e:
            logger.debug(f"Erro ao obter estatísticas da tabela {schema}.{table_name}: {e}")

        return None, None


# Registra o loader no factory
if ORACLEDB_AVAILABLE:
    register_table_loader(DatabaseType.ORACLE, OracleTableLoader)
