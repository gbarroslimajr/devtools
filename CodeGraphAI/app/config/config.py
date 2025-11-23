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

from app.core.models import DatabaseType


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
        self.model_name = os.getenv('CODEGRAPHAI_MODEL_NAME', 'gpt-oss-120b')
        self.device = os.getenv('CODEGRAPHAI_DEVICE', 'cuda')

        # Parâmetros LLM
        self.llm_max_new_tokens = int(os.getenv('CODEGRAPHAI_LLM_MAX_NEW_TOKENS', '1024'))
        self.llm_temperature = float(os.getenv('CODEGRAPHAI_LLM_TEMPERATURE', '0.3'))
        self.llm_top_p = float(os.getenv('CODEGRAPHAI_LLM_TOP_P', '0.95'))
        self.llm_repetition_penalty = float(os.getenv('CODEGRAPHAI_LLM_REPETITION_PENALTY', '1.15'))

        # Modo LLM (local ou api)
        self.llm_mode = os.getenv('CODEGRAPHAI_LLM_MODE', 'local').lower()

        # Provider API (se modo api)
        self.llm_provider = os.getenv('CODEGRAPHAI_LLM_PROVIDER', 'genfactory_llama70b')

        # Configurações GenFactory (apenas se modo api)
        if self.llm_mode == 'api':
            # Helper para processar CA bundle path
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

            # GenFactory Llama 70B
            self.genfactory_llama70b = {
                'name': os.getenv('CODEGRAPHAI_GENFACTORY_LLAMA70B_NAME', 'BNP GenFactory Llama 70B'),
                'base_url': os.getenv('CODEGRAPHAI_GENFACTORY_LLAMA70B_BASE_URL', ''),
                'wire_api': os.getenv('CODEGRAPHAI_GENFACTORY_LLAMA70B_WIRE_API', 'chat'),
                'model': os.getenv('CODEGRAPHAI_GENFACTORY_LLAMA70B_MODEL', 'meta-llama-3.3-70b-instruct'),
                'authorization_token': os.getenv('CODEGRAPHAI_GENFACTORY_LLAMA70B_AUTHORIZATION_TOKEN', ''),
                'timeout': int(os.getenv('CODEGRAPHAI_GENFACTORY_LLAMA70B_TIMEOUT', '20000')),
                'verify_ssl': os.getenv('CODEGRAPHAI_GENFACTORY_LLAMA70B_VERIFY_SSL', 'true').lower() == 'true',
                'ca_bundle_path': _parse_ca_bundle_path('CODEGRAPHAI_GENFACTORY_LLAMA70B_CA_BUNDLE_PATH')
            }

            # GenFactory Codestral
            self.genfactory_codestral = {
                'name': os.getenv('CODEGRAPHAI_GENFACTORY_CODESTRAL_NAME', 'BNP GenFactory Codestral Latest'),
                'base_url': os.getenv('CODEGRAPHAI_GENFACTORY_CODESTRAL_BASE_URL', ''),
                'wire_api': os.getenv('CODEGRAPHAI_GENFACTORY_CODESTRAL_WIRE_API', 'chat'),
                'model': os.getenv('CODEGRAPHAI_GENFACTORY_CODESTRAL_MODEL', 'codestral-latest'),
                'authorization_token': os.getenv('CODEGRAPHAI_GENFACTORY_CODESTRAL_AUTHORIZATION_TOKEN', ''),
                'timeout': int(os.getenv('CODEGRAPHAI_GENFACTORY_CODESTRAL_TIMEOUT', '20000')),
                'verify_ssl': os.getenv('CODEGRAPHAI_GENFACTORY_CODESTRAL_VERIFY_SSL', 'true').lower() == 'true',
                'ca_bundle_path': _parse_ca_bundle_path('CODEGRAPHAI_GENFACTORY_CODESTRAL_CA_BUNDLE_PATH')
            }

            # GenFactory GPT-OSS-120B
            self.genfactory_gptoss120b = {
                'name': os.getenv('CODEGRAPHAI_GENFACTORY_GPTOSS120B_NAME', 'BNP GenFactory GPT-OSS-120B'),
                'base_url': os.getenv('CODEGRAPHAI_GENFACTORY_GPTOSS120B_BASE_URL', ''),
                'wire_api': os.getenv('CODEGRAPHAI_GENFACTORY_GPTOSS120B_WIRE_API', 'chat'),
                'model': os.getenv('CODEGRAPHAI_GENFACTORY_GPTOSS120B_MODEL', 'gpt-oss-120b'),
                'authorization_token': os.getenv('CODEGRAPHAI_GENFACTORY_GPTOSS120B_AUTHORIZATION_TOKEN', ''),
                'timeout': int(os.getenv('CODEGRAPHAI_GENFACTORY_GPTOSS120B_TIMEOUT', '20000')),
                'verify_ssl': os.getenv('CODEGRAPHAI_GENFACTORY_GPTOSS120B_VERIFY_SSL', 'true').lower() == 'true',
                'ca_bundle_path': _parse_ca_bundle_path('CODEGRAPHAI_GENFACTORY_GPTOSS120B_CA_BUNDLE_PATH')
            }

            # Configurações globais API
            self.llm_api_max_output_tokens = int(os.getenv('CODEGRAPHAI_LLM_API_MAX_OUTPUT_TOKENS', '4000'))
            self.llm_reasoning_effort = os.getenv('CODEGRAPHAI_LLM_REASONING_EFFORT', 'high')
        else:
            # Inicializar como None se modo local
            self.genfactory_llama70b = None
            self.genfactory_codestral = None
            self.genfactory_gptoss120b = None
            self.llm_api_max_output_tokens = None
            self.llm_reasoning_effort = None

        # Configuração de banco de dados (genérica)
        db_type_str = os.getenv('CODEGRAPHAI_DB_TYPE', 'oracle').lower()
        try:
            self.db_type = DatabaseType(db_type_str)
        except ValueError:
            self.db_type = DatabaseType.ORACLE  # Default para backward compatibility

        self.db_host = os.getenv('CODEGRAPHAI_DB_HOST')
        self.db_port = os.getenv('CODEGRAPHAI_DB_PORT')
        self.db_database = os.getenv('CODEGRAPHAI_DB_NAME') or os.getenv('CODEGRAPHAI_DB_DATABASE')
        self.db_schema = os.getenv('CODEGRAPHAI_DB_SCHEMA')

        # Oracle Database (mantido para backward compatibility)
        self.oracle_user = os.getenv('CODEGRAPHAI_ORACLE_USER') or os.getenv('CODEGRAPHAI_DB_USER')
        self.oracle_password = os.getenv('CODEGRAPHAI_ORACLE_PASSWORD') or os.getenv('CODEGRAPHAI_DB_PASSWORD')
        self.oracle_dsn = os.getenv('CODEGRAPHAI_ORACLE_DSN') or self.db_host
        self.oracle_schema = os.getenv('CODEGRAPHAI_ORACLE_SCHEMA') or self.db_schema

        # Caminhos padrão
        self.output_dir = os.getenv('CODEGRAPHAI_OUTPUT_DIR', './output')
        self.procedures_dir = os.getenv('CODEGRAPHAI_PROCEDURES_DIR', './procedures')

        # Logging
        self.log_level = os.getenv('CODEGRAPHAI_LOG_LEVEL', 'INFO')
        self.log_file = os.getenv('CODEGRAPHAI_LOG_FILE')  # Opcional

        # Validação
        self._validate()

    def _validate(self) -> None:
        """Valida configurações"""
        valid_devices = ['cuda', 'cpu']
        if self.device not in valid_devices:
            raise ValueError(f"Device deve ser um de: {valid_devices}")

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
            valid_providers = ['genfactory_llama70b', 'genfactory_codestral', 'genfactory_gptoss120b']
            if self.llm_provider not in valid_providers:
                raise ValueError(f"LLM provider deve ser um de: {valid_providers}")

            # Validar provider selecionado
            if self.llm_provider == 'genfactory_llama70b':
                provider_config = self.genfactory_llama70b
            elif self.llm_provider == 'genfactory_codestral':
                provider_config = self.genfactory_codestral
            elif self.llm_provider == 'genfactory_gptoss120b':
                provider_config = self.genfactory_gptoss120b
            else:
                provider_config = None

            if not provider_config:
                raise ValueError(f"Configuração do provider {self.llm_provider} não encontrada")

            if not provider_config.get('authorization_token'):
                raise ValueError(f"Authorization token é obrigatório para {self.llm_provider}")

            if not provider_config.get('base_url'):
                raise ValueError(f"Base URL é obrigatória para {self.llm_provider}")

    def has_database_config(self) -> bool:
        """Verifica se configuração de banco está completa"""
        user = self.oracle_user or os.getenv('CODEGRAPHAI_DB_USER')
        password = self.oracle_password or os.getenv('CODEGRAPHAI_DB_PASSWORD')
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
        user = self.oracle_user or os.getenv('CODEGRAPHAI_DB_USER')
        password = self.oracle_password or os.getenv('CODEGRAPHAI_DB_PASSWORD')
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

