"""
Loader de procedures para Oracle Database
"""

import logging
from typing import Dict

try:
    import oracledb

    ORACLEDB_AVAILABLE = True
except ImportError:
    ORACLEDB_AVAILABLE = False

from app.core.models import DatabaseConfig, DatabaseType, ProcedureLoadError, ValidationError
from app.io.base import ProcedureLoaderBase
from app.io.factory import register_loader

logger = logging.getLogger(__name__)


class OracleLoader(ProcedureLoaderBase):
    """Loader de procedures para Oracle Database"""

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

        # Oracle usa DSN no formato host:port/service
        if config.database:
            if config.port:
                dsn = f"{config.host}:{config.port}/{config.database}"
            else:
                dsn = f"{config.host}/{config.database}"
        else:
            # Assume que host já é DSN completo
            dsn = config.host

        try:
            connection = oracledb.connect(
                user=config.user,
                password=config.password,
                dsn=dsn
            )
            cursor = connection.cursor()
            cursor.execute("SELECT 1 FROM DUAL")
            result = cursor.fetchone()
            cursor.close()
            connection.close()
            return result[0] == 1
        except oracledb.Error as e:
            logger.error(f"Erro de conexão Oracle: {e}")
            raise ProcedureLoadError(f"Erro ao conectar ao Oracle: {e}")
        except Exception as e:
            logger.error(f"Erro inesperado ao testar conexão Oracle: {e}")
            raise ProcedureLoadError(f"Erro ao testar conexão Oracle: {e}")

    def load_procedures(self, config: DatabaseConfig) -> Dict[str, str]:
        """
        Carrega procedures do Oracle Database

        Args:
            config: Configuração de conexão

        Returns:
            Dict com schema.procedure como chave e código-fonte como valor

        Raises:
            ProcedureLoadError: Se houver erro ao carregar
            ValidationError: Se a configuração for inválida
        """
        self.validate_config(config)

        # Oracle usa DSN no formato host:port/service
        # Se config.database está vazio, usa apenas host (assumindo que é DSN completo)
        if config.database:
            # Se database fornecido, constrói DSN
            if config.port:
                dsn = f"{config.host}:{config.port}/{config.database}"
            else:
                dsn = f"{config.host}/{config.database}"
        else:
            # Assume que host já é DSN completo (formato host:port/service ou apenas host)
            dsn = config.host

        try:
            connection = oracledb.connect(
                user=config.user,
                password=config.password,
                dsn=dsn
            )
            cursor = connection.cursor()

            # Lista procedures
            query = "SELECT OWNER, OBJECT_NAME FROM ALL_PROCEDURES WHERE OBJECT_TYPE = 'PROCEDURE'"
            if config.schema:
                # Previne SQL injection usando bind variables
                query += " AND OWNER = :schema"
                cursor.execute(query, schema=config.schema)
            else:
                cursor.execute(query)

            proc_list = cursor.fetchall()

            procedures = {}
            for owner, proc_name in proc_list:
                try:
                    # Busca código fonte
                    cursor.execute("""
                                   SELECT TEXT
                                   FROM ALL_SOURCE
                                   WHERE OWNER = :owner
                                     AND NAME = :name
                                   ORDER BY LINE
                                   """, owner=owner, name=proc_name)

                    lines = cursor.fetchall()
                    source = ''.join([line[0] for line in lines])

                    # Validação: código não pode estar vazio
                    if not source.strip():
                        logger.warning(f"Procedure vazia ignorada: {owner}.{proc_name}")
                        continue

                    full_name = f"{owner}.{proc_name}"
                    procedures[full_name] = source
                    logger.info(f"Carregado: {full_name}")
                except Exception as e:
                    logger.error(f"Erro ao carregar {owner}.{proc_name}: {e}")
                    # Continua com outras procedures mesmo se uma falhar

            connection.close()

            if not procedures:
                raise ProcedureLoadError("Nenhuma procedure encontrada no banco de dados")

            logger.info(f"Total de {len(procedures)} procedures carregadas do Oracle")
            return procedures

        except oracledb.Error as e:
            logger.error(f"Erro de conexão Oracle: {e}")
            raise ProcedureLoadError(f"Erro ao conectar ao banco Oracle: {e}")
        except Exception as e:
            logger.error(f"Erro inesperado ao carregar procedures do Oracle: {e}")
            raise ProcedureLoadError(f"Erro ao carregar procedures do Oracle: {e}")


# Registra o loader no factory
if ORACLEDB_AVAILABLE:
    register_loader(DatabaseType.ORACLE, OracleLoader)
