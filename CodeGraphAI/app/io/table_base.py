"""
Interface abstrata para carregadores de tabelas
"""

from abc import ABC, abstractmethod
from typing import Dict
import logging

from app.core.models import DatabaseConfig, DatabaseType, TableInfo, ValidationError

logger = logging.getLogger(__name__)


class TableLoaderBase(ABC):
    """Interface abstrata para carregadores de tabelas de banco de dados"""

    @abstractmethod
    def load_tables(self, config: DatabaseConfig) -> Dict[str, TableInfo]:
        """
        Carrega tabelas do banco de dados

        Args:
            config: Configuração de conexão com o banco

        Returns:
            Dict com nome da tabela como chave e TableInfo como valor.
            Formato da chave: "schema.table" ou apenas "table"

        Raises:
            TableLoadError: Se houver erro ao carregar tabelas
            ValidationError: Se a configuração for inválida
        """
        pass

    @abstractmethod
    def get_database_type(self) -> DatabaseType:
        """
        Retorna o tipo de banco de dados suportado por este loader

        Returns:
            DatabaseType do banco suportado
        """
        pass

    def load_table_ddl(self, config: DatabaseConfig, schema: str, table_name: str) -> str:
        """
        Carrega DDL completo de uma tabela específica

        Args:
            config: Configuração de conexão
            schema: Schema da tabela
            table_name: Nome da tabela

        Returns:
            DDL completo da tabela

        Raises:
            TableLoadError: Se houver erro ao carregar DDL
        """
        # Implementação padrão pode ser sobrescrita
        raise NotImplementedError("load_table_ddl deve ser implementado pelo loader específico")

    def validate_config(self, config: DatabaseConfig) -> None:
        """
        Valida a configuração antes de tentar conectar

        Args:
            config: Configuração a validar

        Raises:
            ValidationError: Se a configuração for inválida
        """
        if config.db_type != self.get_database_type():
            raise ValidationError(
                f"Configuração de banco {config.db_type} não é compatível "
                f"com loader {self.get_database_type()}"
            )

        if not config.user or not config.user.strip():
            raise ValidationError("Usuário do banco não pode ser vazio")
        if not config.password or not config.password.strip():
            raise ValidationError("Senha do banco não pode ser vazia")
        if not config.host or not config.host.strip():
            raise ValidationError("Host do banco não pode ser vazio")

