"""
Interface abstrata para carregadores de procedures
"""

from abc import ABC, abstractmethod
from typing import Dict
import logging

from app.core.models import DatabaseConfig, DatabaseType

logger = logging.getLogger(__name__)


class ProcedureLoaderBase(ABC):
    """Interface abstrata para carregadores de procedures de banco de dados"""

    @abstractmethod
    def load_procedures(self, config: DatabaseConfig) -> Dict[str, str]:
        """
        Carrega procedures do banco de dados

        Args:
            config: Configuração de conexão com o banco

        Returns:
            Dict com nome da procedure como chave e código-fonte como valor.
            Formato da chave: "schema.procedure" ou apenas "procedure"

        Raises:
            ProcedureLoadError: Se houver erro ao carregar procedures
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

    def test_connection(self, config: DatabaseConfig) -> bool:
        """
        Testa a conexão com o banco de dados (opcional)

        Args:
            config: Configuração de conexão

        Returns:
            True se a conexão foi bem-sucedida, False caso contrário

        Raises:
            ProcedureLoadError: Se houver erro de conexão
        """
        # Implementação padrão: tenta carregar procedures e verifica se não está vazio
        try:
            procedures = self.load_procedures(config)
            return len(procedures) >= 0  # Aceita mesmo se não houver procedures
        except Exception as e:
            logger.error(f"Erro ao testar conexão: {e}")
            return False

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

