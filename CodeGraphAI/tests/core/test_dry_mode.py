"""
Testes para o módulo dry_mode
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from app.core.dry_mode import DryRunResult, DryRunValidator
from app.core.models import DatabaseType, ValidationError
from app.config.config import Config


class TestDryRunResult:
    """Testes para DryRunResult"""

    def test_dry_run_result_initialization(self):
        """Testa inicialização de DryRunResult"""
        result = DryRunResult()
        assert result.is_valid is True
        assert result.errors == []
        assert result.warnings == []
        assert result.info == []
        assert result.estimated_operations == {}

    def test_add_error(self):
        """Testa adicionar erro"""
        result = DryRunResult()
        result.add_error("Erro de teste")
        assert len(result.errors) == 1
        assert result.errors[0] == "Erro de teste"
        assert result.is_valid is False

    def test_add_warning(self):
        """Testa adicionar warning"""
        result = DryRunResult()
        result.add_warning("Warning de teste")
        assert len(result.warnings) == 1
        assert result.warnings[0] == "Warning de teste"
        assert result.is_valid is True  # Warnings não invalidam

    def test_add_info(self):
        """Testa adicionar informação"""
        result = DryRunResult()
        result.add_info("Info de teste")
        assert len(result.info) == 1
        assert result.info[0] == "Info de teste"
        assert result.is_valid is True


class TestDryRunValidator:
    """Testes para DryRunValidator"""

    @pytest.fixture
    def mock_config(self):
        """Cria um mock de Config"""
        config = Mock(spec=Config)
        config.llm_mode = 'api'
        config.llm_provider = 'anthropic'
        config.model_name = 'gpt-oss-120b'
        config.device = 'cuda'
        config.output_dir = './output'
        config.anthropic = {'api_key': 'test-key', 'model': 'claude-sonnet-4-5'}
        config.openai = None
        config.genfactory_llama70b = None
        return config

    @pytest.fixture
    def validator(self, mock_config):
        """Cria instância de DryRunValidator"""
        return DryRunValidator(mock_config)

    def test_validate_database_config_valid(self, validator):
        """Testa validação de config de banco válida"""
        result = validator.validate_database_config(
            db_type='postgresql',
            user='testuser',
            password='testpass',
            host='localhost',
            port=5432,
            database='testdb',
            schema='public'
        )
        assert result.is_valid is True
        assert len(result.errors) == 0
        assert 'postgresql' in result.info[0].lower()

    def test_validate_database_config_invalid_type(self, validator):
        """Testa validação com tipo de banco inválido"""
        result = validator.validate_database_config(
            db_type='invalid',
            user='testuser',
            password='testpass',
            host='localhost'
        )
        assert result.is_valid is False
        assert len(result.errors) > 0
        assert 'inválido' in result.errors[0].lower()

    def test_validate_database_config_missing_params(self, validator):
        """Testa validação com parâmetros faltando"""
        result = validator.validate_database_config(
            db_type='postgresql',
            user='',
            password='',
            host=''
        )
        assert result.is_valid is False
        assert len(result.errors) >= 3  # user, password, host, database

    def test_validate_database_config_invalid_port(self, validator):
        """Testa validação com porta inválida"""
        result = validator.validate_database_config(
            db_type='postgresql',
            user='testuser',
            password='testpass',
            host='localhost',
            port=70000,  # Porta inválida
            database='testdb'
        )
        assert result.is_valid is False
        assert any('porta' in error.lower() for error in result.errors)

    def test_validate_database_config_non_oracle_requires_database(self, validator):
        """Testa que bancos não-Oracle requerem database"""
        result = validator.validate_database_config(
            db_type='postgresql',
            user='testuser',
            password='testpass',
            host='localhost'
        )
        assert result.is_valid is False
        assert any('database' in error.lower() for error in result.errors)

    def test_validate_database_config_oracle_no_database_required(self, validator):
        """Testa que Oracle não requer database"""
        result = validator.validate_database_config(
            db_type='oracle',
            user='testuser',
            password='testpass',
            host='localhost:1521/ORCL'
        )
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_validate_llm_config_local_mode(self, validator):
        """Testa validação de LLM em modo local"""
        result = validator.validate_llm_config(
            llm_mode='local',
            model_name='test-model',
            device='cuda'
        )
        assert result.is_valid is True
        assert 'local' in result.info[0].lower()

    def test_validate_llm_config_api_mode(self, validator):
        """Testa validação de LLM em modo API"""
        result = validator.validate_llm_config(
            llm_mode='api',
            llm_provider='anthropic'
        )
        assert result.is_valid is True
        assert 'api' in result.info[0].lower()

    def test_validate_llm_config_missing_api_key(self, validator):
        """Testa validação com API key faltando"""
        validator.config.anthropic = None
        result = validator.validate_llm_config(
            llm_mode='api',
            llm_provider='anthropic'
        )
        assert result.is_valid is True  # Warning não invalida
        assert len(result.warnings) > 0
        assert any('key' in warning.lower() for warning in result.warnings)

    def test_validate_llm_config_invalid_mode(self, validator):
        """Testa validação com modo inválido"""
        result = validator.validate_llm_config(llm_mode='invalid')
        assert result.is_valid is False
        assert len(result.errors) > 0

    def test_validate_llm_config_invalid_provider(self, validator):
        """Testa validação com provider inválido"""
        result = validator.validate_llm_config(
            llm_mode='api',
            llm_provider='invalid_provider'
        )
        assert result.is_valid is False
        assert len(result.errors) > 0

    def test_validate_analysis_params_valid(self, validator):
        """Testa validação de parâmetros válidos"""
        result = validator.validate_analysis_params(
            analysis_type='both',
            limit=10,
            output_dir='./test_output'
        )
        assert result.is_valid is True
        assert 'both' in result.info[0].lower()

    def test_validate_analysis_params_invalid_type(self, validator):
        """Testa validação com tipo de análise inválido"""
        result = validator.validate_analysis_params(analysis_type='invalid')
        assert result.is_valid is False
        assert len(result.errors) > 0

    def test_validate_analysis_params_invalid_limit(self, validator):
        """Testa validação com limit inválido"""
        result = validator.validate_analysis_params(
            analysis_type='both',
            limit=0
        )
        assert result.is_valid is False
        assert any('limit' in error.lower() for error in result.errors)

    def test_validate_analysis_params_output_dir(self, validator, tmp_path):
        """Testa validação de diretório de saída"""
        test_dir = tmp_path / "test_output"
        test_dir.mkdir()

        result = validator.validate_analysis_params(
            analysis_type='both',
            output_dir=str(test_dir)
        )
        assert result.is_valid is True
        assert any('gravável' in info.lower() or 'saída' in info.lower() for info in result.info)

    def test_validate_full_analysis_valid(self, validator):
        """Testa validação completa válida"""
        result = validator.validate_full_analysis(
            analysis_type='both',
            db_type='postgresql',
            user='testuser',
            password='testpass',
            host='localhost',
            port=5432,
            database='testdb',
            schema='public',
            limit=10,
            output_dir='./test_output'
        )
        # Pode ter warnings mas não erros
        assert len(result.errors) == 0

    def test_validate_full_analysis_invalid(self, validator):
        """Testa validação completa inválida"""
        result = validator.validate_full_analysis(
            analysis_type='invalid',
            db_type='invalid',
            user='',
            password='',
            host='',
            limit=-1
        )
        assert result.is_valid is False
        assert len(result.errors) > 0

