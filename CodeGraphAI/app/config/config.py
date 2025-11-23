"""
Módulo de configuração para CodeGraphAI
Suporta configuração via variáveis de ambiente e arquivo .env
"""

import os
from typing import Optional
from pathlib import Path

try:
    from dotenv import load_dotenv

    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False

from app.core.models import DatabaseType, LLMProvider


class DefaultConfig:
    """Valores padrão das configurações"""
    # LLM Local
    MODEL_NAME = 'gpt-oss-120b'
    DEVICE = 'cuda'
    LLM_MAX_NEW_TOKENS = 1024
    LLM_TEMPERATURE = 0.3
    LLM_TOP_P = 0.95
    LLM_REPETITION_PENALTY = 1.15

    # LLM API
    LLM_MODE = 'local'
    LLM_PROVIDER = 'genfactory_llama70b'
    LLM_API_MAX_OUTPUT_TOKENS = 4000
    LLM_REASONING_EFFORT = 'high'
    LLM_USE_TOON = False  # Usar TOON para otimização de tokens (padrão: False)

    # OpenAI
    OPENAI_MODEL = 'gpt-5.1'
    OPENAI_TIMEOUT = 60
    OPENAI_TEMPERATURE = 0.3
    OPENAI_MAX_TOKENS = 4000

    # Anthropic
    ANTHROPIC_MODEL = 'claude-sonnet-4-5-20250929'
    ANTHROPIC_TIMEOUT = 60
    ANTHROPIC_TEMPERATURE = 0.3
    ANTHROPIC_MAX_TOKENS = 4000

    # GenFactory
    GENFACTORY_TIMEOUT = 20000
    GENFACTORY_VERIFY_SSL = 'true'
    GENFACTORY_WIRE_API = 'chat'

    # Database
    DB_TYPE = 'oracle'

    # Paths
    OUTPUT_DIR = './output'
    PROCEDURES_DIR = './procedures'

    # Logging
    LOG_LEVEL = 'INFO'


class Config:
    """Configurações do CodeGraphAI"""

    def __init__(self):
        """Inicializa configurações carregando variáveis de ambiente"""
        # Carrega .env ou environment.env se disponível
        if DOTENV_AVAILABLE:
            base_path = Path(__file__).parent.parent.parent
            # Tenta carregar .env primeiro, depois environment.env
            env_path = base_path / '.env'
            if not env_path.exists():
                env_path = base_path / 'environment.env'

            if env_path.exists():
                load_dotenv(env_path)
                self._env_loaded = True
            else:
                self._env_loaded = False
        else:
            self._env_loaded = False

        # Modelo LLM
        self.model_name = os.getenv('CODEGRAPHAI_MODEL_NAME', DefaultConfig.MODEL_NAME)
        self.device = os.getenv('CODEGRAPHAI_DEVICE', DefaultConfig.DEVICE)

        # Parâmetros LLM
        self.llm_max_new_tokens = self._getenv_int('CODEGRAPHAI_LLM_MAX_NEW_TOKENS', DefaultConfig.LLM_MAX_NEW_TOKENS)
        self.llm_temperature = self._getenv_float('CODEGRAPHAI_LLM_TEMPERATURE', DefaultConfig.LLM_TEMPERATURE)
        self.llm_top_p = self._getenv_float('CODEGRAPHAI_LLM_TOP_P', DefaultConfig.LLM_TOP_P)
        self.llm_repetition_penalty = self._getenv_float('CODEGRAPHAI_LLM_REPETITION_PENALTY',
                                                         DefaultConfig.LLM_REPETITION_PENALTY)

        # Modo LLM (local ou api)
        self.llm_mode = os.getenv('CODEGRAPHAI_LLM_MODE', DefaultConfig.LLM_MODE).lower()

        # Provider API (se modo api)
        self.llm_provider = os.getenv('CODEGRAPHAI_LLM_PROVIDER', DefaultConfig.LLM_PROVIDER)

        # Configuração TOON (otimização de tokens)
        self.llm_use_toon = self._getenv_bool('CODEGRAPHAI_LLM_USE_TOON', DefaultConfig.LLM_USE_TOON)

        # Configurações GenFactory (apenas se modo api)
        if self.llm_mode == 'api':
            # GenFactory Llama 70B
            self.genfactory_llama70b = self._load_genfactory_config(
                'LLAMA70B',
                'BNP GenFactory Llama 70B',
                'meta-llama-3.3-70b-instruct'
            )

            # GenFactory Codestral
            self.genfactory_codestral = self._load_genfactory_config(
                'CODESTRAL',
                'BNP GenFactory Codestral Latest',
                'codestral-latest'
            )

            # GenFactory GPT-OSS-120B
            self.genfactory_gptoss120b = self._load_genfactory_config(
                'GPTOSS120B',
                'BNP GenFactory GPT-OSS-120B',
                'gpt-oss-120b'
            )

            # OpenAI
            self.openai = self._load_simple_api_config(
                'OPENAI',
                'CODEGRAPHAI_OPENAI_API_KEY',
                'CODEGRAPHAI_OPENAI_MODEL',
                DefaultConfig.OPENAI_MODEL,
                DefaultConfig.OPENAI_TIMEOUT,
                DefaultConfig.OPENAI_TEMPERATURE,
                DefaultConfig.OPENAI_MAX_TOKENS
            )
            # Base URL é específico do OpenAI (para Azure)
            self.openai['base_url'] = os.getenv('CODEGRAPHAI_OPENAI_BASE_URL')

            # Anthropic Claude
            self.anthropic = self._load_simple_api_config(
                'ANTHROPIC',
                'CODEGRAPHAI_ANTHROPIC_API_KEY',
                'CODEGRAPHAI_ANTHROPIC_MODEL',
                DefaultConfig.ANTHROPIC_MODEL,
                DefaultConfig.ANTHROPIC_TIMEOUT,
                DefaultConfig.ANTHROPIC_TEMPERATURE,
                DefaultConfig.ANTHROPIC_MAX_TOKENS
            )

            # Configurações globais API
            self.llm_api_max_output_tokens = self._getenv_int('CODEGRAPHAI_LLM_API_MAX_OUTPUT_TOKENS',
                                                              DefaultConfig.LLM_API_MAX_OUTPUT_TOKENS)
            self.llm_reasoning_effort = os.getenv('CODEGRAPHAI_LLM_REASONING_EFFORT',
                                                  DefaultConfig.LLM_REASONING_EFFORT)
        else:
            # Inicializar como None se modo local
            self.genfactory_llama70b = None
            self.genfactory_codestral = None
            self.genfactory_gptoss120b = None
            self.openai = None
            self.anthropic = None
            self.llm_api_max_output_tokens = None
            self.llm_reasoning_effort = None

        # Configuração de banco de dados (genérica)
        db_type_str = os.getenv('CODEGRAPHAI_DB_TYPE', DefaultConfig.DB_TYPE).lower()
        try:
            self.db_type = DatabaseType(db_type_str)
        except ValueError:
            self.db_type = DatabaseType.ORACLE  # Default para backward compatibility

        self.db_host = os.getenv('CODEGRAPHAI_DB_HOST')
        self.db_port = os.getenv('CODEGRAPHAI_DB_PORT')
        self.db_database = os.getenv('CODEGRAPHAI_DB_NAME') or os.getenv('CODEGRAPHAI_DB_DATABASE')
        self.db_schema = os.getenv('CODEGRAPHAI_DB_SCHEMA')

        # Oracle Database (mantido para backward compatibility)
        self.oracle_user = self._get_db_value('CODEGRAPHAI_ORACLE_USER', 'CODEGRAPHAI_DB_USER')
        self.oracle_password = self._get_db_value('CODEGRAPHAI_ORACLE_PASSWORD', 'CODEGRAPHAI_DB_PASSWORD')
        self.oracle_dsn = os.getenv('CODEGRAPHAI_ORACLE_DSN') or self.db_host
        self.oracle_schema = os.getenv('CODEGRAPHAI_ORACLE_SCHEMA') or self.db_schema

        # Caminhos padrão
        self.output_dir = os.getenv('CODEGRAPHAI_OUTPUT_DIR', DefaultConfig.OUTPUT_DIR)
        self.procedures_dir = os.getenv('CODEGRAPHAI_PROCEDURES_DIR', DefaultConfig.PROCEDURES_DIR)

        # Logging
        self.log_level = os.getenv('CODEGRAPHAI_LOG_LEVEL', DefaultConfig.LOG_LEVEL)
        self.log_file = os.getenv('CODEGRAPHAI_LOG_FILE')  # Opcional

        # Criar mapeamento de providers para validação
        if self.llm_mode == 'api':
            self._provider_config_map = {
                'genfactory_llama70b': self.genfactory_llama70b,
                'genfactory_codestral': self.genfactory_codestral,
                'genfactory_gptoss120b': self.genfactory_gptoss120b,
                'openai': self.openai,
                'anthropic': self.anthropic
            }
        else:
            self._provider_config_map = {}

        # Validação
        self._validate()

    @staticmethod
    def _getenv_int(key: str, default: int) -> int:
        """Obtém variável de ambiente como int"""
        try:
            return int(os.getenv(key, str(default)))
        except ValueError:
            return default

    @staticmethod
    def _getenv_float(key: str, default: float) -> float:
        """Obtém variável de ambiente como float"""
        try:
            return float(os.getenv(key, str(default)))
        except ValueError:
            return default

    @staticmethod
    def _getenv_bool(key: str, default: bool = False) -> bool:
        """Obtém variável de ambiente como bool"""
        value = os.getenv(key, '').lower()
        if not value:
            return default
        return value in ('true', '1', 'yes', 'on')

    @staticmethod
    def _parse_ca_bundle_path(env_var: str) -> list:
        """Processa CA bundle path, suportando ; e , como separadores"""
        path_str = os.getenv(env_var, '')
        if not path_str:
            return []
        # Tenta primeiro com ; (Windows), depois com , (Linux/Mac)
        if ';' in path_str:
            return [p.strip() for p in path_str.split(';') if p.strip()]
        else:
            return [p.strip() for p in path_str.split(',') if p.strip()]

    def _load_genfactory_config(self, provider_prefix: str, default_name: str, default_model: str) -> dict:
        """
        Carrega configuração GenFactory de forma genérica

        Args:
            provider_prefix: Prefixo do provider (ex: 'LLAMA70B')
            default_name: Nome padrão do provider
            default_model: Modelo padrão

        Returns:
            Dict com configuração do provider
        """
        return {
            'name': os.getenv(f'CODEGRAPHAI_GENFACTORY_{provider_prefix}_NAME', default_name),
            'base_url': os.getenv(f'CODEGRAPHAI_GENFACTORY_{provider_prefix}_BASE_URL', ''),
            'wire_api': os.getenv(f'CODEGRAPHAI_GENFACTORY_{provider_prefix}_WIRE_API',
                                  DefaultConfig.GENFACTORY_WIRE_API),
            'model': os.getenv(f'CODEGRAPHAI_GENFACTORY_{provider_prefix}_MODEL', default_model),
            'authorization_token': os.getenv(f'CODEGRAPHAI_GENFACTORY_{provider_prefix}_AUTHORIZATION_TOKEN', ''),
            'timeout': self._getenv_int(f'CODEGRAPHAI_GENFACTORY_{provider_prefix}_TIMEOUT',
                                        DefaultConfig.GENFACTORY_TIMEOUT),
            'verify_ssl': self._getenv_bool(f'CODEGRAPHAI_GENFACTORY_{provider_prefix}_VERIFY_SSL', True),
            'ca_bundle_path': self._parse_ca_bundle_path(f'CODEGRAPHAI_GENFACTORY_{provider_prefix}_CA_BUNDLE_PATH')
        }

    def _load_simple_api_config(self, provider: str, api_key_var: str, model_var: str,
                                default_model: str, default_timeout: int = 60,
                                default_temp: float = 0.3, default_max_tokens: int = 4000) -> dict:
        """
        Carrega configuração para providers simples (OpenAI, Anthropic)

        Args:
            provider: Nome do provider (OPENAI, ANTHROPIC)
            api_key_var: Variável de ambiente para API key
            model_var: Variável de ambiente para modelo
            default_model: Modelo padrão
            default_timeout: Timeout padrão
            default_temp: Temperature padrão
            default_max_tokens: Max tokens padrão

        Returns:
            Dict com configuração do provider
        """
        return {
            'api_key': os.getenv(api_key_var, ''),
            'model': os.getenv(model_var, default_model),
            'timeout': self._getenv_int(f'CODEGRAPHAI_{provider}_TIMEOUT', default_timeout),
            'temperature': self._getenv_float(f'CODEGRAPHAI_{provider}_TEMPERATURE', default_temp),
            'max_tokens': self._getenv_int(f'CODEGRAPHAI_{provider}_MAX_TOKENS', default_max_tokens)
        }

    def _get_db_value(self, oracle_var: str, generic_var: str, fallback: Optional[str] = None) -> Optional[str]:
        """
        Obtém valor de banco com fallback Oracle -> genérico -> fallback

        Args:
            oracle_var: Variável Oracle específica
            generic_var: Variável genérica
            fallback: Valor de fallback opcional

        Returns:
            Valor encontrado ou None
        """
        return os.getenv(oracle_var) or os.getenv(generic_var) or fallback

    def _validate(self) -> None:
        """Valida configurações"""
        # Validar device
        valid_devices = ['cuda', 'cpu']
        if self.device not in valid_devices:
            raise ValueError(f"Device deve ser um de: {valid_devices}")

        # Validar parâmetros LLM
        if self.llm_temperature < 0 or self.llm_temperature > 2:
            raise ValueError("LLM temperature deve estar entre 0 e 2")

        if self.llm_top_p < 0 or self.llm_top_p > 1:
            raise ValueError("LLM top_p deve estar entre 0 e 1")

        if self.llm_repetition_penalty < 0:
            raise ValueError("LLM repetition_penalty deve ser positivo")

        # Validar modo LLM
        valid_modes = ['local', 'api']
        if self.llm_mode not in valid_modes:
            raise ValueError(f"LLM mode deve ser um de: {valid_modes}")

        # Validar configuração API se modo api
        if self.llm_mode == 'api':
            # Validar provider usando Enum
            try:
                LLMProvider.from_string(self.llm_provider)
            except ValueError as e:
                raise ValueError(str(e))

            # Obter configuração do provider
            provider_config = self._provider_config_map.get(self.llm_provider)
            if not provider_config:
                raise ValueError(f"Configuração do provider {self.llm_provider} não encontrada")

            # Validação específica por provider
            if self.llm_provider.startswith('genfactory_'):
                if not provider_config.get('authorization_token'):
                    raise ValueError(f"Authorization token é obrigatório para {self.llm_provider}")
                if not provider_config.get('base_url'):
                    raise ValueError(f"Base URL é obrigatória para {self.llm_provider}")
            elif self.llm_provider == 'openai':
                if not provider_config.get('api_key'):
                    raise ValueError("OpenAI API key é obrigatória")
            elif self.llm_provider == 'anthropic':
                if not provider_config.get('api_key'):
                    raise ValueError("Anthropic API key é obrigatória")

    def has_database_config(self) -> bool:
        """Verifica se configuração de banco está completa"""
        user = self._get_db_value('CODEGRAPHAI_ORACLE_USER', 'CODEGRAPHAI_DB_USER')
        password = self._get_db_value('CODEGRAPHAI_ORACLE_PASSWORD', 'CODEGRAPHAI_DB_PASSWORD')
        host = self.db_host or self.oracle_dsn

        return all([user, password, host])

    def get_database_config(self) -> dict:
        """
        Retorna configuração de banco como dict (genérico)

        Returns:
            Dict com user, password, host, port, database, schema, db_type

        Raises:
            ValueError: Se configuração estiver incompleta
        """
        user = self._get_db_value('CODEGRAPHAI_ORACLE_USER', 'CODEGRAPHAI_DB_USER')
        password = self._get_db_value('CODEGRAPHAI_ORACLE_PASSWORD', 'CODEGRAPHAI_DB_PASSWORD')
        host = self.db_host or self.oracle_dsn

        if not all([user, password, host]):
            raise ValueError(
                "Configuração de banco incompleta. "
                "Defina CODEGRAPHAI_DB_USER, CODEGRAPHAI_DB_PASSWORD e CODEGRAPHAI_DB_HOST "
                "(ou variáveis Oracle para backward compatibility)"
            )

        port = None
        if self.db_port:
            try:
                port = int(self.db_port)
            except ValueError:
                pass

        return {
            'user': user,
            'password': password,
            'host': host,
            'port': port,
            'database': self.db_database,
            'schema': self.db_schema or self.oracle_schema,
            'db_type': self.db_type
        }

    def has_oracle_config(self) -> bool:
        """Verifica se configuração Oracle está completa (backward compatibility)"""
        return all([self.oracle_user, self.oracle_password, self.oracle_dsn])

    def get_oracle_config(self) -> dict:
        """
        Retorna configuração Oracle como dict (backward compatibility)

        Returns:
            Dict com user, password, dsn, schema

        Raises:
            ValueError: Se configuração Oracle estiver incompleta
        """
        if not self.has_oracle_config():
            raise ValueError(
                "Configuração Oracle incompleta. Defina CODEGRAPHAI_ORACLE_USER, "
                "CODEGRAPHAI_ORACLE_PASSWORD e CODEGRAPHAI_ORACLE_DSN"
            )

        return {
            'user': self.oracle_user,
            'password': self.oracle_password,
            'dsn': self.oracle_dsn,
            'schema': self.oracle_schema
        }

    def __repr__(self) -> str:
        """Representação string da configuração"""
        return (f"Config(model_name={self.model_name}, device={self.device}, "
                f"db_type={self.db_type.value}, output_dir={self.output_dir}, "
                f"env_loaded={self._env_loaded})")


# Instância global de configuração
_config: Optional[Config] = None


def get_config() -> Config:
    """
    Retorna instância global de configuração (singleton)

    Returns:
        Instância de Config
    """
    global _config
    if _config is None:
        _config = Config()
    return _config


def reload_config() -> Config:
    """
    Recarrega configuração (útil para testes)

    Returns:
        Nova instância de Config
    """
    global _config
    _config = Config()
    return _config
