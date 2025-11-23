"""
Testes para integração Anthropic Claude
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from analyzer import LLMAnalyzer
from app.config.config import Config
from app.core.models import LLMAnalysisError


class TestAnthropicIntegration:
    """Testes para integração Anthropic Claude"""

    @patch('analyzer.ChatAnthropic')
    def test_init_anthropic_success(self, mock_chat_anthropic):
        """Testa inicialização bem-sucedida do Anthropic"""
        mock_llm = MagicMock()
        mock_chat_anthropic.return_value = mock_llm

        config = Config()
        config.llm_mode = 'api'
        config.llm_provider = 'anthropic'
        config.anthropic = {
            'api_key': 'sk-ant-test-key',
            'model': 'claude-sonnet-4-5-20250929',
            'timeout': 60,
            'temperature': 0.3,
            'max_tokens': 4000
        }

        analyzer = LLMAnalyzer(config=config)

        assert analyzer.llm == mock_llm
        mock_chat_anthropic.assert_called_once()
        call_kwargs = mock_chat_anthropic.call_args[1]
        assert call_kwargs['api_key'] == 'sk-ant-test-key'
        assert call_kwargs['model'] == 'claude-sonnet-4-5-20250929'
        assert call_kwargs['temperature'] == 0.3
        assert call_kwargs['max_tokens'] == 4000
        assert call_kwargs['timeout'] == 60

    @patch('analyzer.ChatAnthropic')
    def test_init_anthropic_default_model(self, mock_chat_anthropic):
        """Testa inicialização com modelo padrão"""
        mock_llm = MagicMock()
        mock_chat_anthropic.return_value = mock_llm

        config = Config()
        config.llm_mode = 'api'
        config.llm_provider = 'anthropic'
        config.anthropic = {
            'api_key': 'sk-ant-test-key',
            'model': 'claude-sonnet-4-5-20250929',  # Modelo padrão
            'timeout': 60,
            'temperature': 0.3,
            'max_tokens': 4000
        }

        analyzer = LLMAnalyzer(config=config)

        assert analyzer.llm == mock_llm
        call_kwargs = mock_chat_anthropic.call_args[1]
        assert call_kwargs['model'] == 'claude-sonnet-4-5-20250929'

    def test_init_anthropic_missing_api_key(self):
        """Testa erro quando API key está faltando"""
        config = Config()
        config.llm_mode = 'api'
        config.llm_provider = 'anthropic'
        config.anthropic = {
            'api_key': '',
            'model': 'claude-sonnet-4-5-20250929',
            'timeout': 60,
            'temperature': 0.3,
            'max_tokens': 4000
        }

        with pytest.raises(LLMAnalysisError, match="Anthropic API key é obrigatória"):
            LLMAnalyzer(config=config)

    def test_init_anthropic_none_config(self):
        """Testa erro quando config.anthropic é None"""
        config = Config()
        config.llm_mode = 'api'
        config.llm_provider = 'anthropic'
        config.anthropic = None

        with pytest.raises(LLMAnalysisError, match="Anthropic API key é obrigatória"):
            LLMAnalyzer(config=config)

