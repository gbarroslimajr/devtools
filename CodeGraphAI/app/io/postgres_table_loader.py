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
from app.io.table_cache import TableCache

logger = logging.getLogger(__name__)


class PostgreSQLTableLoader(TableLoaderBase):
    """
    Loader de tabelas para PostgreSQL

    Este loader carrega metadados completos de tabelas do PostgreSQL, incluindo:
    - Estrutura de colunas (nome, tipo, nullable, default, etc.)
    - Primary keys
    - Foreign keys e relacionamentos
    - Índices
    - Comentários
    - Estatísticas (row count, size)

    Versão 2.0 - Arquitetura Melhorada:
        A partir da versão 2.0, as foreign keys são carregadas separadamente
        das colunas através do método _load_fk_column_mapping(). Isso evita
        duplicatas causadas por múltiplas constraints na mesma coluna e
        melhora a separação de concerns.

    Notas Importantes:
        - Se uma coluna tem múltiplas FKs, apenas a primeira é retornada
        - DISTINCT ON é usado nas queries para garantir unicidade
        - O loader respeita .gitignore e usa cache quando disponível
    """

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

    def load_tables(
        self,
        config: DatabaseConfig,
        use_cache: bool = True,
        force_update: bool = False
    ) -> Dict[str, TableInfo]:
        """
        Carrega tabelas do PostgreSQL

        Args:
            config: Configuração de conexão
            use_cache: Se True, usa cache quando disponível (padrão: True)
            force_update: Se True, ignora cache e força atualização do banco (padrão: False)

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
                      AND table_schema NOT IN ('pg_catalog', 'information_schema') \
                    """

            params = []
            if config.schema:
                query += " AND table_schema = %s"
                params.append(config.schema)
                logger.info(f"Buscando tabelas no schema: {config.schema}")
            else:
                logger.info("Buscando tabelas em todos os schemas (exceto pg_catalog e information_schema)")

            cursor.execute(query, params)
            tables_list = cursor.fetchall()
            logger.info(f"Encontradas {len(tables_list)} tabelas na query inicial")

            # Se nenhuma tabela encontrada, tenta listar schemas disponíveis para debug
            if not tables_list:
                try:
                    debug_query = """
                                  SELECT DISTINCT table_schema
                                  FROM information_schema.tables
                                  WHERE table_type = 'BASE TABLE'
                                    AND table_schema NOT IN ('pg_catalog', 'information_schema')
                                  ORDER BY table_schema \
                                  """
                    cursor.execute(debug_query)
                    available_schemas = [row['table_schema'] for row in cursor.fetchall()]
                    if available_schemas:
                        logger.warning(f"Schemas disponíveis com tabelas: {', '.join(available_schemas)}")
                    else:
                        # Tenta listar todos os schemas existentes
                        cursor.execute("""
                                       SELECT schema_name
                                       FROM information_schema.schemata
                                       WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
                                       ORDER BY schema_name
                                       """)
                        all_schemas = [row['schema_name'] for row in cursor.fetchall()]
                        if all_schemas:
                            logger.warning(f"Schemas existentes no banco (sem tabelas): {', '.join(all_schemas)}")
                        else:
                            logger.warning("Nenhum schema encontrado no banco de dados")
                except Exception as e:
                    logger.debug(f"Erro ao buscar schemas para debug: {e}")

            tables = {}
            for row in tables_list:
                schema_name = row['table_schema']
                table_name = row['table_name']
                full_name = f"{schema_name}.{table_name}" if schema_name != 'public' else table_name

                try:
                    # Tenta carregar do cache primeiro
                    table_info = None
                    if use_cache and not force_update:
                        table_info = TableCache.load_table_from_cache(config, schema_name, table_name)
                        if table_info:
                            logger.debug(f"Cache hit para {full_name}")
                            tables[full_name] = table_info
                            continue

                    # Se não encontrou no cache ou force_update, carrega do banco
                    if not table_info:
                        table_info = self._load_table_details(
                            cursor, schema_name, table_name, config
                        )
                        tables[full_name] = table_info
                        logger.info(f"Carregado do banco: {full_name}")

                        # Salva no cache
                        if use_cache:
                            TableCache.save_table_to_cache(config, table_info)

                except Exception as e:
                    logger.error(f"Erro ao carregar {full_name}: {e}")
                    import traceback
                    logger.debug(f"Traceback completo: {traceback.format_exc()}")
                    continue

            connection.close()

            if not tables:
                schema_msg = f" no schema '{config.schema}'" if config.schema else ""
                error_msg = f"Nenhuma tabela encontrada no banco de dados{schema_msg}"

                # Lista schemas disponíveis na mensagem de erro
                try:
                    # Reutiliza conexão existente se ainda estiver aberta
                    if connection.closed == 0:
                        debug_cursor = connection.cursor(cursor_factory=RealDictCursor)
                    else:
                        connection = psycopg2.connect(
                            host=config.host,
                            port=port,
                            database=config.database,
                            user=config.user,
                            password=config.password
                        )
                        debug_cursor = connection.cursor(cursor_factory=RealDictCursor)

                    # Lista todos os schemas com tabelas
                    debug_cursor.execute("""
                                         SELECT DISTINCT table_schema
                                         FROM information_schema.tables
                                         WHERE table_type = 'BASE TABLE'
                                           AND table_schema NOT IN ('pg_catalog', 'information_schema')
                                         ORDER BY table_schema
                                         """)
                    schemas_with_tables = [row['table_schema'] for row in debug_cursor.fetchall()]

                    # Lista todos os schemas existentes
                    debug_cursor.execute("""
                                         SELECT schema_name
                                         FROM information_schema.schemata
                                         WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
                                         ORDER BY schema_name
                                         """)
                    all_schemas = [row['schema_name'] for row in debug_cursor.fetchall()]

                    if connection.closed == 0 and not connection.closed:
                        debug_cursor.close()
                    else:
                        connection.close()

                    if schemas_with_tables:
                        error_msg += f"\nSchemas com tabelas disponíveis: {', '.join(schemas_with_tables)}"
                    elif all_schemas:
                        error_msg += f"\nSchemas existentes no banco (sem tabelas): {', '.join(all_schemas)}"
                    else:
                        error_msg += "\nNenhum schema encontrado no banco de dados"

                    if config.schema and config.schema not in all_schemas:
                        error_msg += f"\n⚠️  O schema '{config.schema}' não existe no banco de dados."
                except Exception as e:
                    logger.debug(f"Erro ao buscar schemas para mensagem: {e}")

                raise TableLoadError(error_msg)

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
        try:
            columns = self._load_columns(cursor, schema, table_name)
        except Exception as e:
            logger.error(f"Erro ao carregar colunas de {schema}.{table_name}: {e}")
            raise

        # 3. Carrega índices
        try:
            indexes = self._load_indexes(cursor, schema, table_name)
        except Exception as e:
            logger.error(f"Erro ao carregar índices de {schema}.{table_name}: {e}")
            raise

        # 4. Carrega foreign keys
        try:
            foreign_keys = self._load_foreign_keys(cursor, schema, table_name)
        except Exception as e:
            logger.error(f"Erro ao carregar foreign keys de {schema}.{table_name}: {e}")
            raise

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
        """
        Carrega informações das colunas (sem FK inline para evitar duplicatas)

        Note:
            A partir da versão 2.0, as foreign keys são carregadas separadamente
            via _load_fk_column_mapping() para evitar duplicatas causadas por
            múltiplas constraints na mesma coluna.
        """
        # Query simplificada - apenas colunas básicas + PK (sem FK inline)
        # DISTINCT ON garante que não haja duplicatas mesmo sem FK inline
        query = """
                SELECT DISTINCT ON (c.column_name)
                       c.column_name,
                       c.data_type,
                       c.is_nullable,
                       c.column_default,
                       c.character_maximum_length,
                       c.numeric_precision,
                       c.numeric_scale,
                       CASE WHEN pk.column_name IS NOT NULL THEN true ELSE false END as is_pk,
                       col_description(pgc.oid, c.ordinal_position)                  as column_comment,
                       c.ordinal_position
                FROM information_schema.columns c
                         JOIN pg_class pgc ON pgc.relname = c.table_name
                         JOIN pg_namespace pgn ON pgn.oid = pgc.relnamespace AND pgn.nspname = c.table_schema
                         LEFT JOIN (SELECT ku.column_name
                                    FROM information_schema.key_column_usage ku
                                    JOIN information_schema.table_constraints tc
                                         ON tc.constraint_name = ku.constraint_name
                                    WHERE tc.constraint_type = 'PRIMARY KEY'
                                      AND tc.table_schema = %s
                                      AND tc.table_name = %s) pk ON pk.column_name = c.column_name
                WHERE c.table_schema = %s
                  AND c.table_name = %s
                ORDER BY c.column_name, c.ordinal_position \
                """

        cursor.execute(query, (schema, table_name, schema, table_name))
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
                is_foreign_key=False,  # Será preenchido depois
                foreign_key_table=None,
                foreign_key_column=None,
                comments=row.get('column_comment')
            ))

        # Enriquecer com informações de FK (separadamente para evitar duplicatas)
        fk_map = self._load_fk_column_mapping(cursor, schema, table_name)
        for col in columns:
            if col.name in fk_map:
                col.is_foreign_key = True
                col.foreign_key_table = fk_map[col.name]['table']
                col.foreign_key_column = fk_map[col.name]['column']

        return columns

    def _load_fk_column_mapping(
        self, cursor, schema: str, table_name: str
    ) -> Dict[str, Dict[str, str]]:
        """
        Carrega mapeamento de colunas FK (sem duplicatas)

        Args:
            cursor: Database cursor
            schema: Schema name
            table_name: Table name

        Returns:
            Dict mapeando column_name -> {table, column}

        Note:
            Se uma coluna tem múltiplas FKs, apenas a primeira é retornada.
            Isso é uma simplificação, mas evita duplicatas e é suficiente
            para a maioria dos casos de uso.
        """
        query = """
            SELECT DISTINCT
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
        """
        cursor.execute(query, (schema, table_name))

        fk_map = {}
        for row in cursor.fetchall():
            col_name = row['column_name']
            # Pega apenas a primeira referência para cada coluna
            if col_name not in fk_map:
                fk_map[col_name] = {
                    'table': row['referenced_table'],
                    'column': row['referenced_column']
                }
            else:
                logger.debug(
                    f"Column '{col_name}' in {schema}.{table_name} has multiple FK constraints, "
                    f"using first: {fk_map[col_name]['table']}"
                )

        return fk_map

    def _load_indexes(self, cursor, schema: str, table_name: str) -> List[IndexInfo]:
        """Carrega informações dos índices"""
        # Query simplificada para evitar problemas com JOINs complexos
        # Primeiro, busca os índices
        query = """
                SELECT i.indexname as index_name,
                       i.indexdef
                FROM pg_indexes i
                WHERE i.schemaname = %s
                  AND i.tablename = %s \
                """

        cursor.execute(query, (schema, table_name))
        rows = cursor.fetchall()

        # Busca primary keys separadamente
        pk_query = """
                   SELECT constraint_name
                   FROM information_schema.table_constraints
                   WHERE constraint_type = 'PRIMARY KEY'
                     AND table_schema = %s
                     AND table_name = %s \
                   """
        cursor.execute(pk_query, (schema, table_name))
        pk_rows = cursor.fetchall()
        pk_constraint_names = {row['constraint_name'] for row in pk_rows} if pk_rows else set()

        indexes = []
        for row in rows:
            # Extrai colunas do indexdef
            # Exemplo: "CREATE INDEX idx_name ON table (col1, col2)"
            indexdef = row['indexdef']
            index_name = row['index_name']

            # Verifica se é unique
            is_unique = 'UNIQUE' in indexdef.upper()

            # Verifica se é primary key
            is_primary = any(pk_name in index_name for pk_name in pk_constraint_names)

            # Extrai colunas
            columns_str = ""
            if '(' in indexdef:
                try:
                    columns_str = indexdef.split('(')[1].split(')')[0]
                except IndexError:
                    columns_str = ""
            columns = [col.strip().strip('"') for col in columns_str.split(',') if col.strip()] if columns_str else []

            indexes.append(IndexInfo(
                name=index_name,
                table_name=table_name,
                columns=columns,
                is_unique=is_unique,
                is_primary=is_primary,
                index_type='btree'  # Default para PostgreSQL
            ))

        return indexes

    def _load_foreign_keys(self, cursor, schema: str, table_name: str) -> List[ForeignKeyInfo]:
        """Carrega informações das foreign keys"""
        query = """
                SELECT tc.constraint_name,
                       ku.column_name,
                       ccu.table_schema || '.' || ccu.table_name as referenced_table,
                       ccu.column_name                           as referenced_column,
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
                ORDER BY tc.constraint_name, ku.ordinal_position \
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

    def _generate_ddl_from_info(self, columns: List[ColumnInfo], foreign_keys: List[ForeignKeyInfo], schema: str,
                                table_name: str) -> str:
        """Gera DDL a partir das informações coletadas"""
        ddl_lines = [f"CREATE TABLE {schema}.{table_name} ("]

        col_defs = []
        for col in columns:
            col_def = f"    {col.name} {col.data_type}"
            if not col.nullable:
                col_def += " NOT NULL"
            if col.default_value:
                col_def += f" DEFAULT {col.default_value}"
            col_defs.append(col_def)

        ddl_lines.append(",\n".join(col_defs))

        # Adiciona primary key
        pk_cols = [col.name for col in columns if col.is_primary_key]
        if pk_cols:
            ddl_lines.append(f",\n    PRIMARY KEY ({', '.join(pk_cols)})")

        # Adiciona foreign keys
        for fk in foreign_keys:
            fk_def = f"    CONSTRAINT {fk.name} FOREIGN KEY ({', '.join(fk.columns)})"
            fk_def += f" REFERENCES {fk.referenced_table} ({', '.join(fk.referenced_columns)})"
            if fk.on_delete:
                fk_def += f" ON DELETE {fk.on_delete}"
            if fk.on_update:
                fk_def += f" ON UPDATE {fk.on_update}"
            ddl_lines.append(f",\n{fk_def}")

        ddl_lines.append("\n);")
        return "\n".join(ddl_lines)

    def _get_table_stats(self, cursor, schema: str, table_name: str) -> Tuple[Optional[int], Optional[str]]:
        """Obtém estatísticas da tabela (row count, size)"""
        query = """
                SELECT n_live_tup                                                           as row_count,
                       pg_size_pretty(pg_total_relation_size(schemaname || '.' || relname)) as size
                FROM pg_stat_user_tables
                WHERE schemaname = %s
                  AND relname = %s \
                """
        try:
            cursor.execute(query, (schema, table_name))
            row = cursor.fetchone()
            if row:
                # RealDictCursor retorna dicionário
                row_count = row.get('row_count') if isinstance(row, dict) else row[0] if row else None
                size = row.get('size') if isinstance(row, dict) else row[1] if row and len(row) > 1 else None
                return row_count, size
        except Exception as e:
            logger.debug(f"Erro ao obter estatísticas da tabela {schema}.{table_name}: {e}")

        return None, None


# Registra o loader no factory
if PSYCOPG2_AVAILABLE:
    register_table_loader(DatabaseType.POSTGRESQL, PostgreSQLTableLoader)
