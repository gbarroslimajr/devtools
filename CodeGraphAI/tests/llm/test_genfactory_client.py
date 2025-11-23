"""
Testes para GenFactoryClient
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import requests

from app.llm.genfactory_client import GenFactoryClient
from app.core.models import LLMAnalysisError


class TestGenFactoryClient:
    """Testes para GenFactoryClient"""

    def test_init_success(self):
        """Testa inicialização bem-sucedida"""
        config = {
            'base_url': 'https://api.example.com',
            'model': 'test-model',
            'authorization_token': 'test-token',
            'timeout': 20000,
            'verify_ssl': True,
            'ca_bundle_path': []
        }

        with patch('app.llm.genfactory_client.requests.Session') as mock_session:
            mock_session_instance = MagicMock()
            mock_session.return_value = mock_session_instance

            client = GenFactoryClient(config)

            assert client.base_url == 'https://api.example.com'
            assert client.model == 'test-model'
            assert client.authorization_token == 'test-token'
            assert client.timeout_sec == 20.0

    def test_init_missing_base_url(self):
        """Testa erro quando base_url está faltando"""
        config = {
            'model': 'test-model',
            'authorization_token': 'test-token'
        }

        with pytest.raises(LLMAnalysisError, match="base_url é obrigatório"):
            GenFactoryClient(config)

    def test_init_missing_token(self):
        """Testa erro quando token está faltando"""
        config = {
            'base_url': 'https://api.example.com',
            'model': 'test-model'
        }

        with pytest.raises(LLMAnalysisError, match="authorization_token é obrigatório"):
            GenFactoryClient(config)

    def test_init_missing_model(self):
        """Testa erro quando model está faltando"""
        config = {
            'base_url': 'https://api.example.com',
            'authorization_token': 'test-token'
        }

        with pytest.raises(LLMAnalysisError, match="model é obrigatório"):
            GenFactoryClient(config)

    @patch('app.llm.genfactory_client.requests.Session')
    def test_chat_success(self, mock_session_class):
        """Testa chamada bem-sucedida da API"""
        # Configurar mock
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'choices': [{
                'message': {
                    'content': 'Resposta do modelo'
                }
            }]
        }
        mock_response.raise_for_status = Mock()
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session

        config = {
            'base_url': 'https://api.example.com',
            'model': 'test-model',
            'authorization_token': 'test-token',
            'timeout': 20000,
            'verify_ssl': False,
            'ca_bundle_path': []
        }

        client = GenFactoryClient(config)
        messages = [{'role': 'user', 'content': 'Test prompt'}]

        result = client.chat(messages)

        assert result == 'Resposta do modelo'
        mock_session.post.assert_called_once()
        call_args = mock_session.post.call_args
        assert call_args[0][0] == 'https://api.example.com/chat/completions'
        assert 'json' in call_args[1]
        assert call_args[1]['json']['model'] == 'test-model'
        assert call_args[1]['json']['messages'] == messages

    @patch('app.llm.genfactory_client.requests.Session')
    def test_chat_timeout(self, mock_session_class):
        """Testa tratamento de timeout"""
        mock_session = MagicMock()
        mock_session.post.side_effect = requests.exceptions.Timeout()
        mock_session_class.return_value = mock_session

        config = {
            'base_url': 'https://api.example.com',
            'model': 'test-model',
            'authorization_token': 'test-token',
            'timeout': 20000,
            'verify_ssl': False,
            'ca_bundle_path': []
        }

        client = GenFactoryClient(config)
        messages = [{'role': 'user', 'content': 'Test'}]

        with pytest.raises(LLMAnalysisError, match="Timeout"):
            client.chat(messages)

    @patch('app.llm.genfactory_client.requests.Session')
    def test_chat_http_error_401(self, mock_session_class):
        """Testa tratamento de erro 401 (não autorizado)"""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = 'Unauthorized'
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response)
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session

        config = {
            'base_url': 'https://api.example.com',
            'model': 'test-model',
            'authorization_token': 'test-token',
            'timeout': 20000,
            'verify_ssl': False,
            'ca_bundle_path': []
        }

        client = GenFactoryClient(config)
        messages = [{'role': 'user', 'content': 'Test'}]

        with pytest.raises(LLMAnalysisError, match="autenticação"):
            client.chat(messages)

    @patch('app.llm.genfactory_client.requests.Session')
    def test_chat_invalid_response_format(self, mock_session_class):
        """Testa tratamento de formato de resposta inválido"""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {'invalid': 'format'}
        mock_response.raise_for_status = Mock()
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session

        config = {
            'base_url': 'https://api.example.com',
            'model': 'test-model',
            'authorization_token': 'test-token',
            'timeout': 20000,
            'verify_ssl': False,
            'ca_bundle_path': []
        }

        client = GenFactoryClient(config)
        messages = [{'role': 'user', 'content': 'Test'}]

        with pytest.raises(LLMAnalysisError, match="Formato de resposta"):
            client.chat(messages)

