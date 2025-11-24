"""
Modelos de dados e exceções para CodeGraphAI
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional
from datetime import datetime


# Exceções customizadas
class CodeGraphAIError(Exception):
    """Exceção base para erros do CodeGraphAI"""
    pass


class ProcedureLoadError(CodeGraphAIError):
    """Erro ao carregar procedures"""
    pass


class TableLoadError(CodeGraphAIError):
    """Erro ao carregar tabelas"""
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


@dataclass
class ColumnInfo:
    """Informações sobre uma coluna de tabela"""
    name: str
    data_type: str
    nullable: bool
    default_value: Optional[str] = None
    is_primary_key: bool = False
    is_foreign_key: bool = False
    foreign_key_table: Optional[str] = None
    foreign_key_column: Optional[str] = None
    constraints: List[str] = field(default_factory=list)
    comments: Optional[str] = None


@dataclass
class IndexInfo:
    """Informações sobre um índice"""
    name: str
    table_name: str
    columns: List[str]
    is_unique: bool
    is_primary: bool
    index_type: Optional[str] = None  # B-tree, Hash, GIN, etc.
    where_clause: Optional[str] = None  # Para índices parciais


@dataclass
class ForeignKeyInfo:
    """Informações sobre uma foreign key"""
    name: str
    table_name: str
    columns: List[str]
    referenced_table: str
    referenced_columns: List[str]
    on_delete: Optional[str] = None  # CASCADE, SET NULL, etc.
    on_update: Optional[str] = None


@dataclass
class TableInfo:
    """Informações sobre uma tabela"""
    name: str
    schema: str
    ddl: str  # DDL completo
    columns: List[ColumnInfo]
    indexes: List[IndexInfo]
    foreign_keys: List[ForeignKeyInfo]
    primary_key_columns: List[str]
    row_count: Optional[int] = None
    table_size: Optional[str] = None  # Tamanho em bytes/human readable
    business_purpose: str = ""  # Gerado por LLM
    complexity_score: int = 0  # Baseado em colunas, FKs, índices
    relationships: Dict[str, List[str]] = field(default_factory=dict)  # {table: [relationship_type]}


@dataclass
class TokenUsage:
    """Informações de uso de tokens em uma requisição LLM"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class LLMRequestMetrics:
    """Métricas de uma requisição LLM"""
    request_id: str
    operation: str  # "analyze_business_logic", "extract_dependencies", "calculate_complexity", "analyze_table_purpose"
    tokens_in: int
    tokens_out: int
    tokens_total: int
    timestamp: datetime
    use_toon: bool = False  # Se TOON foi usado nesta requisição
