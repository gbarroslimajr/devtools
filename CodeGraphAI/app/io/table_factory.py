"""
Factory para criar loaders de tabelas baseado no tipo de banco
"""

import logging
from typing import Dict, List

from app.core.models import DatabaseType, ValidationError
from app.io.table_base import TableLoaderBase

logger = logging.getLogger(__name__)

# Registry de loaders (será populado quando os módulos forem importados)
_TABLE_LOADER_REGISTRY: Dict[DatabaseType, type] = {}


def register_table_loader(db_type: DatabaseType, loader_class: type) -> None:
    """
    Registra um loader de tabelas no factory

    Args:
        db_type: Tipo de banco de dados
        loader_class: Classe do loader (deve herdar de TableLoaderBase)
    """
    if not issubclass(loader_class, TableLoaderBase):
        raise ValueError(f"Loader deve herdar de TableLoaderBase: {loader_class}")

    _TABLE_LOADER_REGISTRY[db_type] = loader_class
    logger.debug(f"Table loader registrado: {db_type} -> {loader_class.__name__}")


def create_table_loader(db_type: DatabaseType) -> TableLoaderBase:
    """
    Cria um loader de tabelas baseado no tipo de banco de dados

    Args:
        db_type: Tipo de banco de dados

    Returns:
        Instância do loader apropriado

    Raises:
        ValidationError: Se o tipo de banco não for suportado
        ImportError: Se o driver necessário não estiver instalado
    """
    if db_type not in _TABLE_LOADER_REGISTRY:
        # Tenta importar o loader dinamicamente
        _try_import_table_loader(db_type)

    if db_type not in _TABLE_LOADER_REGISTRY:
        available = ", ".join([str(dt.value) for dt in _TABLE_LOADER_REGISTRY.keys()])
        raise ValidationError(
            f"Tipo de banco '{db_type.value}' não é suportado para carregamento de tabelas. "
            f"Tipos disponíveis: {available}"
        )

    loader_class = _TABLE_LOADER_REGISTRY[db_type]

    try:
        return loader_class()
    except Exception as e:
        logger.error(f"Erro ao criar table loader para {db_type}: {e}")
        raise ValidationError(
            f"Erro ao criar table loader para {db_type}. "
            f"Verifique se o driver necessário está instalado: {e}"
        )


def get_available_table_loaders() -> List[DatabaseType]:
    """
    Retorna lista de tipos de banco com loaders de tabelas disponíveis

    Returns:
        Lista de DatabaseType disponíveis
    """
    # Tenta importar todos os loaders conhecidos
    known_loaders = {
        DatabaseType.ORACLE: "app.io.oracle_table_loader",
        DatabaseType.POSTGRESQL: "app.io.postgres_table_loader",
        DatabaseType.MSSQL: "app.io.mssql_table_loader",
        DatabaseType.MYSQL: "app.io.mysql_table_loader",
    }

    for db_type, module_name in known_loaders.items():
        if db_type not in _TABLE_LOADER_REGISTRY:
            _try_import_table_loader(db_type)

    return list(_TABLE_LOADER_REGISTRY.keys())


def _try_import_table_loader(db_type: DatabaseType) -> None:
    """
    Tenta importar o loader de tabelas para um tipo de banco

    Args:
        db_type: Tipo de banco de dados
    """
    module_map = {
        DatabaseType.ORACLE: "app.io.oracle_table_loader",
        DatabaseType.POSTGRESQL: "app.io.postgres_table_loader",
        DatabaseType.MSSQL: "app.io.mssql_table_loader",
        DatabaseType.MYSQL: "app.io.mysql_table_loader",
    }

    if db_type not in module_map:
        return

    module_name = module_map[db_type]

    try:
        module = __import__(module_name, fromlist=[''])
        # O módulo deve registrar seu loader automaticamente ao ser importado
        logger.debug(f"Módulo {module_name} importado com sucesso")
    except ImportError as e:
        logger.debug(f"Não foi possível importar {module_name}: {e}")
        # Não levanta exceção - apenas loga, pois o driver pode não estar instalado

