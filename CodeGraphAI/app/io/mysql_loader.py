"""
Loader de procedures para MySQL
"""

import logging
from typing import Dict

try:
    import mysql.connector
    from mysql.connector import Error as MySQLError
    MYSQL_AVAILABLE = True
except ImportError:
    try:
        import pymysql
        MYSQL_AVAILABLE = True
        MYSQL_DRIVER = 'pymysql'
    except ImportError:
        MYSQL_AVAILABLE = False
        MYSQL_DRIVER = None
else:
    MYSQL_DRIVER = 'mysql-connector'

from app.core.models import DatabaseConfig, DatabaseType, ProcedureLoadError, ValidationError
from app.io.base import ProcedureLoaderBase
from app.io.factory import register_loader

logger = logging.getLogger(__name__)


class MySQLLoader(ProcedureLoaderBase):
    """Loader de procedures para MySQL"""

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

    def load_procedures(self, config: DatabaseConfig) -> Dict[str, str]:
        """
        Carrega procedures do MySQL

        Args:
            config: Configuração de conexão

        Returns:
            Dict com database.procedure como chave e código-fonte como valor

        Raises:
            ProcedureLoadError: Se houver erro ao carregar
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

            # Lista procedures usando INFORMATION_SCHEMA
            query = """
                SELECT
                    ROUTINE_SCHEMA,
                    ROUTINE_NAME
                FROM INFORMATION_SCHEMA.ROUTINES
                WHERE ROUTINE_TYPE = 'PROCEDURE'
            """

            params = []
            if config.schema:
                query += " AND ROUTINE_SCHEMA = %s"
                params.append(config.schema)
            else:
                # Se não especificado, usa o database da conexão
                query += " AND ROUTINE_SCHEMA = %s"
                params.append(config.database)

            cursor.execute(query, params)
            proc_list = cursor.fetchall()

            procedures = {}
            for row in proc_list:
                if self.driver == 'mysql-connector':
                    schema_name = row['ROUTINE_SCHEMA']
                    proc_name = row['ROUTINE_NAME']
                else:  # pymysql
                    schema_name = row['ROUTINE_SCHEMA']
                    proc_name = row['ROUTINE_NAME']

                try:
                    # Busca código fonte usando ROUTINE_DEFINITION
                    cursor.execute("""
                        SELECT ROUTINE_DEFINITION
                        FROM INFORMATION_SCHEMA.ROUTINES
                        WHERE ROUTINE_SCHEMA = %s
                        AND ROUTINE_NAME = %s
                        AND ROUTINE_TYPE = 'PROCEDURE'
                    """, (schema_name, proc_name))

                    result = cursor.fetchone()
                    if result:
                        if self.driver == 'mysql-connector':
                            source = result['ROUTINE_DEFINITION']
                        else:  # pymysql
                            source = result['ROUTINE_DEFINITION']
                    else:
                        logger.warning(f"Não foi possível obter código de {schema_name}.{proc_name}")
                        continue

                    # Validação: código não pode estar vazio
                    if not source or not source.strip():
                        logger.warning(f"Procedure vazia ignorada: {schema_name}.{proc_name}")
                        continue

                    # MySQL não usa schema da mesma forma, usa database
                    full_name = f"{schema_name}.{proc_name}" if schema_name != config.database else proc_name
                    procedures[full_name] = source
                    logger.info(f"Carregado: {full_name}")
                except Exception as e:
                    logger.error(f"Erro ao carregar {schema_name}.{proc_name}: {e}")
                    # Continua com outras procedures mesmo se uma falhar

            connection.close()

            if not procedures:
                raise ProcedureLoadError("Nenhuma procedure encontrada no banco de dados")

            logger.info(f"Total de {len(procedures)} procedures carregadas do MySQL")
            return procedures

        except Exception as e:
            error_type = MySQLError if self.driver == 'mysql-connector' else Exception
            if isinstance(e, error_type):
                logger.error(f"Erro de conexão MySQL: {e}")
                raise ProcedureLoadError(f"Erro ao conectar ao MySQL: {e}")
            else:
                logger.error(f"Erro inesperado ao carregar procedures do MySQL: {e}")
                raise ProcedureLoadError(f"Erro ao carregar procedures do MySQL: {e}")


# Registra o loader no factory
if MYSQL_AVAILABLE:
    register_loader(DatabaseType.MYSQL, MySQLLoader)

