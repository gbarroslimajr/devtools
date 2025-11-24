"""
Loader de procedures para PostgreSQL
"""

import logging
from typing import Dict

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor

    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

from app.core.models import DatabaseConfig, DatabaseType, ProcedureLoadError, ValidationError
from app.io.base import ProcedureLoaderBase
from app.io.factory import register_loader

logger = logging.getLogger(__name__)


class PostgreSQLLoader(ProcedureLoaderBase):
    """Loader de procedures para PostgreSQL"""

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

    def test_connection_only(self, config: DatabaseConfig) -> bool:
        """
        Testa apenas a conexão com o banco usando query simples

        Args:
            config: Configuração de conexão

        Returns:
            True se conexão bem-sucedida, False caso contrário

        Raises:
            ProcedureLoadError: Se houver erro de conexão
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
            cursor = connection.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            cursor.close()
            connection.close()
            return result[0] == 1
        except psycopg2.Error as e:
            logger.error(f"Erro de conexão PostgreSQL: {e}")
            raise ProcedureLoadError(f"Erro ao conectar ao PostgreSQL: {e}")
        except Exception as e:
            logger.error(f"Erro inesperado ao testar conexão PostgreSQL: {e}")
            raise ProcedureLoadError(f"Erro ao testar conexão PostgreSQL: {e}")

    def load_procedures(self, config: DatabaseConfig) -> Dict[str, str]:
        """
        Carrega procedures do PostgreSQL

        Args:
            config: Configuração de conexão

        Returns:
            Dict com schema.procedure como chave e código-fonte como valor

        Raises:
            ProcedureLoadError: Se houver erro ao carregar
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

            # Lista procedures
            # PostgreSQL usa information_schema.routines
            query = """
                    SELECT routine_schema,
                           routine_name
                    FROM information_schema.routines
                    WHERE routine_type = 'PROCEDURE' \
                    """

            params = []
            if config.schema:
                query += " AND routine_schema = %s"
                params.append(config.schema)

            cursor.execute(query, params)
            proc_list = cursor.fetchall()

            procedures = {}
            for row in proc_list:
                schema_name = row['routine_schema']
                proc_name = row['routine_name']

                try:
                    # Busca código fonte usando pg_get_functiondef
                    # Para procedures, precisamos usar pg_proc
                    cursor.execute("""
                                   SELECT pg_get_functiondef(p.oid) as definition
                                   FROM pg_proc p
                                            JOIN pg_namespace n ON p.pronamespace = n.oid
                                   WHERE n.nspname = %s
                                     AND p.proname = %s
                                     AND p.prokind = 'p'
                                   """, (schema_name, proc_name))

                    result = cursor.fetchone()
                    if result and result['definition']:
                        source = result['definition']
                    else:
                        # Fallback: tenta obter de information_schema
                        cursor.execute("""
                                       SELECT routine_definition
                                       FROM information_schema.routines
                                       WHERE routine_schema = %s
                                         AND routine_name = %s
                                         AND routine_type = 'PROCEDURE'
                                       """, (schema_name, proc_name))

                        result = cursor.fetchone()
                        if result and result.get('routine_definition'):
                            source = result['routine_definition']
                        else:
                            logger.warning(f"Não foi possível obter código de {schema_name}.{proc_name}")
                            continue

                    # Validação: código não pode estar vazio
                    if not source or not source.strip():
                        logger.warning(f"Procedure vazia ignorada: {schema_name}.{proc_name}")
                        continue

                    full_name = f"{schema_name}.{proc_name}" if schema_name != 'public' else proc_name
                    procedures[full_name] = source
                    logger.info(f"Carregado: {full_name}")
                except Exception as e:
                    logger.error(f"Erro ao carregar {schema_name}.{proc_name}: {e}")
                    # Continua com outras procedures mesmo se uma falhar

            connection.close()

            if not procedures:
                raise ProcedureLoadError("Nenhuma procedure encontrada no banco de dados")

            logger.info(f"Total de {len(procedures)} procedures carregadas do PostgreSQL")
            return procedures

        except psycopg2.Error as e:
            logger.error(f"Erro de conexão PostgreSQL: {e}")
            raise ProcedureLoadError(f"Erro ao conectar ao PostgreSQL: {e}")
        except Exception as e:
            logger.error(f"Erro inesperado ao carregar procedures do PostgreSQL: {e}")
            raise ProcedureLoadError(f"Erro ao carregar procedures do PostgreSQL: {e}")


# Registra o loader no factory
if PSYCOPG2_AVAILABLE:
    register_loader(DatabaseType.POSTGRESQL, PostgreSQLLoader)
