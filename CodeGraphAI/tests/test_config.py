"""
Testes para módulo de configuração
"""

import pytest
import os
from unittest.mock import patch, MagicMock

from app.config.config import Config, DefaultConfig, get_config, reload_config
from app.core.models import LLMProvider, DatabaseType


class TestDefaultConfig:
    """Testes para DefaultConfig"""

    def test_default_values_exist(self):
        """Testa que todos os valores padrão existem"""
        assert hasattr(DefaultConfig, 'MODEL_NAME')
        assert hasattr(DefaultConfig, 'DEVICE')
        assert hasattr(DefaultConfig, 'LLM_MODE')
        assert hasattr(DefaultConfig, 'LLM_PROVIDER')
        assert hasattr(DefaultConfig, 'OPENAI_MODEL')
        assert hasattr(DefaultConfig, 'ANTHROPIC_MODEL')
        assert hasattr(DefaultConfig, 'DB_TYPE')
        assert hasattr(DefaultConfig, 'OUTPUT_DIR')
        assert hasattr(DefaultConfig, 'LOG_LEVEL')

    def test_default_values_types(self):
        """Testa tipos dos valores padrão"""
        assert isinstance(DefaultConfig.MODEL_NAME, str)
        assert isinstance(DefaultConfig.LLM_MAX_NEW_TOKENS, int)
        assert isinstance(DefaultConfig.LLM_TEMPERATURE, float)
        assert isinstance(DefaultConfig.OPENAI_TIMEOUT, int)
        assert isinstance(DefaultConfig.ANTHROPIC_TEMPERATURE, float)


class TestLLMProvider:
    """Testes para LLMProvider Enum"""

    def test_provider_values(self):
        """Testa valores do Enum"""
        assert LLMProvider.GENFACTORY_LLAMA70B.value == 'genfactory_llama70b'
        assert LLMProvider.OPENAI.value == 'openai'
        assert LLMProvider.ANTHROPIC.value == 'anthropic'

    def test_from_string_valid(self):
        """Testa from_string com valores válidos"""
        assert LLMProvider.from_string('openai') == LLMProvider.OPENAI
        assert LLMProvider.from_string('anthropic') == LLMProvider.ANTHROPIC
        assert LLMProvider.from_string('genfactory_llama70b') == LLMProvider.GENFACTORY_LLAMA70B

    def test_from_string_invalid(self):
        """Testa from_string com valor inválido"""
        with pytest.raises(ValueError, match="Provider inválido"):
            LLMProvider.from_string('invalid_provider')


class TestConfigHelpers:
    """Testes para métodos helper do Config"""

    def test_getenv_int(self):
        """Testa _getenv_int"""
        with patch.dict(os.environ, {'TEST_INT': '42'}):
            assert Config._getenv_int('TEST_INT', 10) == 42
            assert Config._getenv_int('TEST_INT_MISSING', 10) == 10

    def test_getenv_int_invalid(self):
        """Testa _getenv_int com valor inválido"""
        with patch.dict(os.environ, {'TEST_INT': 'not_a_number'}):
            assert Config._getenv_int('TEST_INT', 10) == 10  # Retorna default

    def test_getenv_float(self):
        """Testa _getenv_float"""
        with patch.dict(os.environ, {'TEST_FLOAT': '3.14'}):
            assert Config._getenv_float('TEST_FLOAT', 1.0) == 3.14
            assert Config._getenv_float('TEST_FLOAT_MISSING', 1.0) == 1.0

    def test_getenv_bool(self):
        """Testa _getenv_bool"""
        with patch.dict(os.environ, {
            'TEST_BOOL_TRUE': 'true',
            'TEST_BOOL_1': '1',
            'TEST_BOOL_YES': 'yes',
            'TEST_BOOL_FALSE': 'false',
            'TEST_BOOL_EMPTY': ''
        }):
            assert Config._getenv_bool('TEST_BOOL_TRUE', False) is True
            assert Config._getenv_bool('TEST_BOOL_1', False) is True
            assert Config._getenv_bool('TEST_BOOL_YES', False) is True
            assert Config._getenv_bool('TEST_BOOL_FALSE', False) is False
            assert Config._getenv_bool('TEST_BOOL_EMPTY', True) is True  # Default quando vazio

    def test_parse_ca_bundle_path_semicolon(self):
        """Testa _parse_ca_bundle_path com ponto-e-vírgula"""
        with patch.dict(os.environ, {'TEST_CA': 'path1.cer;path2.cer;path3.cer'}):
            result = Config._parse_ca_bundle_path('TEST_CA')
            assert result == ['path1.cer', 'path2.cer', 'path3.cer']

    def test_parse_ca_bundle_path_comma(self):
        """Testa _parse_ca_bundle_path com vírgula"""
        with patch.dict(os.environ, {'TEST_CA': 'path1.cer,path2.cer,path3.cer'}):
            result = Config._parse_ca_bundle_path('TEST_CA')
            assert result == ['path1.cer', 'path2.cer', 'path3.cer']

    def test_parse_ca_bundle_path_empty(self):
        """Testa _parse_ca_bundle_path vazio"""
        with patch.dict(os.environ, {}, clear=True):
            result = Config._parse_ca_bundle_path('TEST_CA_MISSING')
            assert result == []

    def test_get_db_value(self):
        """Testa _get_db_value"""
        config = Config()
        with patch.dict(os.environ, {
            'CODEGRAPHAI_ORACLE_USER': 'oracle_user',
            'CODEGRAPHAI_DB_PASSWORD': 'generic_password'
        }):
            # Testa fallback Oracle -> genérico
            user = config._get_db_value('CODEGRAPHAI_ORACLE_USER', 'CODEGRAPHAI_DB_USER')
            assert user == 'oracle_user'

            password = config._get_db_value('CODEGRAPHAI_ORACLE_PASSWORD', 'CODEGRAPHAI_DB_PASSWORD')
            assert password == 'generic_password'

            # Testa fallback para None
            missing = config._get_db_value('CODEGRAPHAI_MISSING', 'CODEGRAPHAI_ALSO_MISSING')
            assert missing is None


class TestConfigGenFactoryHelper:
    """Testes para _load_genfactory_config"""

    def test_load_genfactory_config(self):
        """Testa carregamento de configuração GenFactory"""
        config = Config()

        with patch.dict(os.environ, {
            'CODEGRAPHAI_GENFACTORY_TEST_NAME': 'Test Provider',
            'CODEGRAPHAI_GENFACTORY_TEST_BASE_URL': 'https://api.test.com',
            'CODEGRAPHAI_GENFACTORY_TEST_MODEL': 'test-model',
            'CODEGRAPHAI_GENFACTORY_TEST_AUTHORIZATION_TOKEN': 'test-token',
            'CODEGRAPHAI_GENFACTORY_TEST_TIMEOUT': '30000',
            'CODEGRAPHAI_GENFACTORY_TEST_VERIFY_SSL': 'false',
            'CODEGRAPHAI_GENFACTORY_TEST_CA_BUNDLE_PATH': 'cert1.cer;cert2.cer'
        }):
            result = config._load_genfactory_config('TEST', 'Default Name', 'default-model')

            assert result['name'] == 'Test Provider'
            assert result['base_url'] == 'https://api.test.com'
            assert result['model'] == 'test-model'
            assert result['authorization_token'] == 'test-token'
            assert result['timeout'] == 30000
            assert result['verify_ssl'] is False
            assert result['ca_bundle_path'] == ['cert1.cer', 'cert2.cer']

    def test_load_genfactory_config_defaults(self):
        """Testa carregamento com valores padrão"""
        config = Config()

        with patch.dict(os.environ, {}, clear=True):
            result = config._load_genfactory_config('TEST', 'Default Name', 'default-model')

            assert result['name'] == 'Default Name'
            assert result['model'] == 'default-model'
            assert result['wire_api'] == DefaultConfig.GENFACTORY_WIRE_API
            assert result['timeout'] == DefaultConfig.GENFACTORY_TIMEOUT
            assert result['verify_ssl'] is True  # Default
            assert result['ca_bundle_path'] == []


class TestConfigSimpleAPIHelper:
    """Testes para _load_simple_api_config"""

    def test_load_simple_api_config(self):
        """Testa carregamento de configuração API simples"""
        config = Config()

        with patch.dict(os.environ, {
            'CODEGRAPHAI_TEST_API_KEY': 'test-key',
            'CODEGRAPHAI_TEST_MODEL': 'test-model',
            'CODEGRAPHAI_TEST_TIMEOUT': '120',
            'CODEGRAPHAI_TEST_TEMPERATURE': '0.5',
            'CODEGRAPHAI_TEST_MAX_TOKENS': '8000'
        }):
            result = config._load_simple_api_config(
                'TEST',
                'CODEGRAPHAI_TEST_API_KEY',
                'CODEGRAPHAI_TEST_MODEL',
                'default-model',
                60,
                0.3,
                4000
            )

            assert result['api_key'] == 'test-key'
            assert result['model'] == 'test-model'
            assert result['timeout'] == 120
            assert result['temperature'] == 0.5
            assert result['max_tokens'] == 8000

    def test_load_simple_api_config_defaults(self):
        """Testa carregamento com valores padrão"""
        config = Config()

        with patch.dict(os.environ, {}, clear=True):
            result = config._load_simple_api_config(
                'TEST',
                'CODEGRAPHAI_TEST_API_KEY',
                'CODEGRAPHAI_TEST_MODEL',
                'default-model',
                60,
                0.3,
                4000
            )

            assert result['api_key'] == ''
            assert result['model'] == 'default-model'
            assert result['timeout'] == 60
            assert result['temperature'] == 0.3
            assert result['max_tokens'] == 4000


class TestConfigValidation:
    """Testes para validação de configuração"""

    def test_validate_llm_provider_enum(self):
        """Testa que validação usa Enum LLMProvider"""
        with patch.dict(os.environ, {
            'CODEGRAPHAI_LLM_MODE': 'api',
            'CODEGRAPHAI_LLM_PROVIDER': 'openai',
            'CODEGRAPHAI_OPENAI_API_KEY': 'test-key'
        }):
            config = Config()
            assert config.llm_provider == 'openai'

    def test_validate_invalid_provider(self):
        """Testa validação com provider inválido"""
        with patch.dict(os.environ, {
            'CODEGRAPHAI_LLM_MODE': 'api',
            'CODEGRAPHAI_LLM_PROVIDER': 'invalid_provider'
        }):
            with pytest.raises(ValueError, match="Provider inválido"):
                Config()

    def test_validate_provider_config_map(self):
        """Testa que _provider_config_map é criado corretamente"""
        with patch.dict(os.environ, {
            'CODEGRAPHAI_LLM_MODE': 'api',
            'CODEGRAPHAI_LLM_PROVIDER': 'openai',
            'CODEGRAPHAI_OPENAI_API_KEY': 'test-key'
        }):
            config = Config()
            assert 'openai' in config._provider_config_map
            assert config._provider_config_map['openai'] == config.openai

    def test_validate_provider_config_map_local_mode(self):
        """Testa que _provider_config_map é vazio em modo local"""
        with patch.dict(os.environ, {
            'CODEGRAPHAI_LLM_MODE': 'local'
        }):
            config = Config()
            assert config._provider_config_map == {}


class TestConfigBackwardCompatibility:
    """Testes para garantir backward compatibility"""

    def test_default_values_unchanged(self):
        """Testa que valores padrão não mudaram"""
        assert DefaultConfig.MODEL_NAME == 'gpt-oss-120b'
        assert DefaultConfig.DEVICE == 'cuda'
        assert DefaultConfig.LLM_MODE == 'local'
        assert DefaultConfig.LLM_PROVIDER == 'genfactory_llama70b'

    def test_config_initialization_unchanged(self):
        """Testa que inicialização básica ainda funciona"""
        with patch.dict(os.environ, {}, clear=True):
            config = Config()
            assert config.model_name == DefaultConfig.MODEL_NAME
            assert config.device == DefaultConfig.DEVICE
            assert config.llm_mode == DefaultConfig.LLM_MODE

    def test_genfactory_config_structure(self):
        """Testa que estrutura de configuração GenFactory não mudou"""
        with patch.dict(os.environ, {
            'CODEGRAPHAI_LLM_MODE': 'api',
            'CODEGRAPHAI_LLM_PROVIDER': 'genfactory_llama70b',
            'CODEGRAPHAI_GENFACTORY_LLAMA70B_BASE_URL': 'https://api.test.com',
            'CODEGRAPHAI_GENFACTORY_LLAMA70B_AUTHORIZATION_TOKEN': 'test-token'
        }):
            config = Config()
            assert 'name' in config.genfactory_llama70b
            assert 'base_url' in config.genfactory_llama70b
            assert 'model' in config.genfactory_llama70b
            assert 'authorization_token' in config.genfactory_llama70b
            assert 'timeout' in config.genfactory_llama70b
            assert 'verify_ssl' in config.genfactory_llama70b
            assert 'ca_bundle_path' in config.genfactory_llama70b

