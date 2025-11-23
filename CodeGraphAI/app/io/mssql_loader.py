"""
Loader de procedures para Microsoft SQL Server
"""

import logging
from typing import Dict

try:
    import pyodbc
    PYODBC_AVAILABLE = True
except ImportError:
    PYODBC_AVAILABLE = False

from app.core.models import DatabaseConfig, DatabaseType, ProcedureLoadError, ValidationError
from app.io.base import ProcedureLoaderBase
from app.io.factory import register_loader

logger = logging.getLogger(__name__)


class MSSQLLoader(ProcedureLoaderBase):
    """Loader de procedures para Microsoft SQL Server"""

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

    def load_procedures(self, config: DatabaseConfig) -> Dict[str, str]:
        """
        Carrega procedures do SQL Server

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
            raise ValidationError("SQL Server requer o nome do banco de dados (database)")

        port = config.port or 1433

        # Constrói connection string para SQL Server
        # Formato: DRIVER={ODBC Driver 17 for SQL Server};SERVER=host,port;DATABASE=db;UID=user;PWD=password
        driver = config.extra_params.get('driver', 'ODBC Driver 17 for SQL Server')
        connection_string = (
            f"DRIVER={{{driver}}};"
            f"SERVER={config.host},{port};"
            f"DATABASE={config.database};"
            f"UID={config.user};"
            f"PWD={config.password}"
        )

        # Adiciona parâmetros extras se houver
        if config.extra_params:
            for key, value in config.extra_params.items():
                if key != 'driver':
                    connection_string += f";{key}={value}"

        try:
            connection = pyodbc.connect(connection_string)
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
                query += " AND ROUTINE_SCHEMA = ?"
                params.append(config.schema)

            cursor.execute(query, params)
            proc_list = cursor.fetchall()

            procedures = {}
            for schema_name, proc_name in proc_list:
                try:
                    # Busca código fonte usando sys.sql_modules
                    cursor.execute("""
                        SELECT definition
                        FROM sys.sql_modules
                        WHERE object_id = OBJECT_ID(?)
                    """, f"{schema_name}.{proc_name}")

                    result = cursor.fetchone()
                    if result and result[0]:
                        source = result[0]
                    else:
                        logger.warning(f"Não foi possível obter código de {schema_name}.{proc_name}")
                        continue

                    # Validação: código não pode estar vazio
                    if not source or not source.strip():
                        logger.warning(f"Procedure vazia ignorada: {schema_name}.{proc_name}")
                        continue

                    full_name = f"{schema_name}.{proc_name}" if schema_name != 'dbo' else proc_name
                    procedures[full_name] = source
                    logger.info(f"Carregado: {full_name}")
                except Exception as e:
                    logger.error(f"Erro ao carregar {schema_name}.{proc_name}: {e}")
                    # Continua com outras procedures mesmo se uma falhar

            connection.close()

            if not procedures:
                raise ProcedureLoadError("Nenhuma procedure encontrada no banco de dados")

            logger.info(f"Total de {len(procedures)} procedures carregadas do SQL Server")
            return procedures

        except pyodbc.Error as e:
            logger.error(f"Erro de conexão SQL Server: {e}")
            raise ProcedureLoadError(f"Erro ao conectar ao SQL Server: {e}")
        except Exception as e:
            logger.error(f"Erro inesperado ao carregar procedures do SQL Server: {e}")
            raise ProcedureLoadError(f"Erro ao carregar procedures do SQL Server: {e}")


# Registra o loader no factory
if PYODBC_AVAILABLE:
    register_loader(DatabaseType.MSSQL, MSSQLLoader)

