"""
Modelos de dados e exceções para CodeGraphAI
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional


# Exceções customizadas
class CodeGraphAIError(Exception):
    """Exceção base para erros do CodeGraphAI"""
    pass


class ProcedureLoadError(CodeGraphAIError):
    """Erro ao carregar procedures"""
    pass


class LLMAnalysisError(CodeGraphAIError):
    """Erro na análise com LLM"""
    pass


class DependencyAnalysisError(CodeGraphAIError):
    """Erro na análise de dependências"""
    pass


class ExportError(CodeGraphAIError):
    """Erro na exportação de resultados"""
    pass


class ValidationError(CodeGraphAIError):
    """Erro de validação"""
    pass


class DatabaseType(str, Enum):
    """Tipos de banco de dados suportados"""
    ORACLE = "oracle"
    POSTGRESQL = "postgresql"
    MSSQL = "mssql"
    MYSQL = "mysql"


class LLMProvider(str, Enum):
    """Providers LLM disponíveis"""
    GENFACTORY_LLAMA70B = "genfactory_llama70b"
    GENFACTORY_CODESTRAL = "genfactory_codestral"
    GENFACTORY_GPTOSS120B = "genfactory_gptoss120b"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"

    @classmethod
    def from_string(cls, value: str) -> 'LLMProvider':
        """Cria provider a partir de string com validação"""
        try:
            return cls(value)
        except ValueError:
            valid = [p.value for p in cls]
            raise ValueError(f"Provider inválido: {value}. Válidos: {valid}")


@dataclass
class DatabaseConfig:
    """Configuração de conexão com banco de dados"""
    db_type: DatabaseType
    user: str
    password: str
    host: str
    port: Optional[int] = None
    database: Optional[str] = None
    schema: Optional[str] = None
    extra_params: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        """Validação pós-inicialização"""
        if not self.user or not self.user.strip():
            raise ValidationError("Usuário do banco não pode ser vazio")
        if not self.password or not self.password.strip():
            raise ValidationError("Senha do banco não pode ser vazia")
        if not self.host or not self.host.strip():
            raise ValidationError("Host do banco não pode ser vazio")

    def get_connection_string(self) -> str:
        """
        Retorna string de conexão formatada para o tipo de banco

        Returns:
            String de conexão formatada (apenas host para Oracle, URL completa para outros)
        """
        if self.db_type == DatabaseType.ORACLE:
            # Oracle usa DSN no formato host:port/service
            # Retorna apenas host (DSN será construído no loader)
            return self.host
        elif self.db_type == DatabaseType.POSTGRESQL:
            port = self.port or 5432
            return f"postgresql://{self.user}:{self.password}@{self.host}:{port}/{self.database or ''}"
        elif self.db_type == DatabaseType.MSSQL:
            port = self.port or 1433
            return f"mssql+pyodbc://{self.user}:{self.password}@{self.host}:{port}/{self.database or ''}"
        elif self.db_type == DatabaseType.MYSQL:
            port = self.port or 3306
            return f"mysql://{self.user}:{self.password}@{self.host}:{port}/{self.database or ''}"
        else:
            raise ValidationError(f"Tipo de banco não suportado: {self.db_type}")


@dataclass
class ProcedureInfo:
    """Informações sobre uma procedure"""
    name: str
    schema: str
    source_code: str
    parameters: List[Dict[str, str]]
    called_procedures: Set[str]
    called_tables: Set[str]
    business_logic: str
    complexity_score: int
    dependencies_level: int

