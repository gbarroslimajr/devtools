"""
Testes para integração OpenAI
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from analyzer import LLMAnalyzer
from app.config.config import Config
from app.core.models import LLMAnalysisError


class TestOpenAIIntegration:
    """Testes para integração OpenAI"""

    @patch('analyzer.ChatOpenAI')
    def test_init_openai_success(self, mock_chat_openai):
        """Testa inicialização bem-sucedida do OpenAI"""
        mock_llm = MagicMock()
        mock_chat_openai.return_value = mock_llm

        config = Config()
        config.llm_mode = 'api'
        config.llm_provider = 'openai'
        config.openai = {
            'api_key': 'sk-test-key',
            'model': 'gpt-5.1',
            'base_url': None,
            'timeout': 60,
            'temperature': 0.3,
            'max_tokens': 4000
        }

        analyzer = LLMAnalyzer(config=config)

        assert analyzer.llm == mock_llm
        mock_chat_openai.assert_called_once()
        call_kwargs = mock_chat_openai.call_args[1]
        assert call_kwargs['api_key'] == 'sk-test-key'
        assert call_kwargs['model'] == 'gpt-5.1'
        assert call_kwargs['temperature'] == 0.3
        assert call_kwargs['max_tokens'] == 4000
        assert call_kwargs['timeout'] == 60

    @patch('analyzer.ChatOpenAI')
    def test_init_openai_different_models(self, mock_chat_openai):
        """Testa inicialização com diferentes modelos OpenAI"""
        mock_llm = MagicMock()
        mock_chat_openai.return_value = mock_llm

        models = ['gpt-5.1', 'gpt-5-mini', 'gpt-5-nano']

        for model in models:
            config = Config()
            config.llm_mode = 'api'
            config.llm_provider = 'openai'
            config.openai = {
                'api_key': 'sk-test-key',
                'model': model,
                'base_url': None,
                'timeout': 60,
                'temperature': 0.3,
                'max_tokens': 4000
            }

            analyzer = LLMAnalyzer(config=config)

            assert analyzer.llm == mock_llm
            call_kwargs = mock_chat_openai.call_args[1]
            assert call_kwargs['model'] == model

    @patch('analyzer.ChatOpenAI')
    def test_init_openai_with_base_url(self, mock_chat_openai):
        """Testa inicialização com base_url customizado (Azure OpenAI)"""
        mock_llm = MagicMock()
        mock_chat_openai.return_value = mock_llm

        config = Config()
        config.llm_mode = 'api'
        config.llm_provider = 'openai'
        config.openai = {
            'api_key': 'sk-test-key',
            'model': 'gpt-5.1',
            'base_url': 'https://azure-openai.example.com/v1',
            'timeout': 60,
            'temperature': 0.3,
            'max_tokens': 4000
        }

        analyzer = LLMAnalyzer(config=config)

        assert analyzer.llm == mock_llm
        call_kwargs = mock_chat_openai.call_args[1]
        assert call_kwargs['base_url'] == 'https://azure-openai.example.com/v1'

    def test_init_openai_missing_api_key(self):
        """Testa erro quando API key está faltando"""
        config = Config()
        config.llm_mode = 'api'
        config.llm_provider = 'openai'
        config.openai = {
            'api_key': '',
            'model': 'gpt-5.1',
            'base_url': None,
            'timeout': 60,
            'temperature': 0.3,
            'max_tokens': 4000
        }

        with pytest.raises(LLMAnalysisError, match="OpenAI API key é obrigatória"):
            LLMAnalyzer(config=config)

    def test_init_openai_none_config(self):
        """Testa erro quando config.openai é None"""
        config = Config()
        config.llm_mode = 'api'
        config.llm_provider = 'openai'
        config.openai = None

        with pytest.raises(LLMAnalysisError, match="OpenAI API key é obrigatória"):
            LLMAnalyzer(config=config)

