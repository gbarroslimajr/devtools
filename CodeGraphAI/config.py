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


class Config:
    """Configurações do CodeGraphAI"""

    def __init__(self):
        """Inicializa configurações carregando variáveis de ambiente"""
        # Carrega .env se disponível
        if DOTENV_AVAILABLE:
            env_path = Path(__file__).parent / '.env'
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

        # Oracle Database (opcional)
        self.oracle_user = os.getenv('CODEGRAPHAI_ORACLE_USER')
        self.oracle_password = os.getenv('CODEGRAPHAI_ORACLE_PASSWORD')
        self.oracle_dsn = os.getenv('CODEGRAPHAI_ORACLE_DSN')
        self.oracle_schema = os.getenv('CODEGRAPHAI_ORACLE_SCHEMA')

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

    def has_oracle_config(self) -> bool:
        """Verifica se configuração Oracle está completa"""
        return all([self.oracle_user, self.oracle_password, self.oracle_dsn])

    def get_oracle_config(self) -> dict:
        """
        Retorna configuração Oracle como dict

        Returns:
            Dict com user, password, dsn, schema

        Raises:
            ValueError: Se configuração Oracle estiver incompleta
        """
        if not self.has_oracle_config():
            raise ValueError("Configuração Oracle incompleta. Defina CODEGRAPHAI_ORACLE_USER, "
                           "CODEGRAPHAI_ORACLE_PASSWORD e CODEGRAPHAI_ORACLE_DSN")

        return {
            'user': self.oracle_user,
            'password': self.oracle_password,
            'dsn': self.oracle_dsn,
            'schema': self.oracle_schema
        }

    def __repr__(self) -> str:
        """Representação string da configuração"""
        return (f"Config(model_name={self.model_name}, device={self.device}, "
                f"output_dir={self.output_dir}, env_loaded={self._env_loaded})")


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

