"""
Cliente para API GenFactory (BNP Paribas)
Gerencia conexão HTTP, SSL e requisições para LLM via API
"""

import ssl
import logging
from typing import List, Dict, Optional, Any
from pathlib import Path
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

from app.core.models import LLMAnalysisError, TokenUsage

logger = logging.getLogger(__name__)


class GenFactoryClient:
    """Cliente para API GenFactory"""

    def __init__(self, config: Dict[str, Any]):
        """
        Inicializa cliente GenFactory

        Args:
            config: Dicionário com configuração do provider
                - base_url: URL base da API
                - model: Nome do modelo
                - authorization_token: Token de autorização
                - timeout: Timeout em milissegundos
                - verify_ssl: Se deve verificar SSL
                - ca_bundle_path: Lista de caminhos de certificados CA

        Raises:
            LLMAnalysisError: Se configuração for inválida
        """
        self.base_url = config.get('base_url', '').rstrip('/')
        self.model = config.get('model', '')
        self.authorization_token = config.get('authorization_token', '')
        self.timeout_ms = config.get('timeout', 20000)
        self.timeout_sec = self.timeout_ms / 1000.0  # Converter para segundos
        self.verify_ssl = config.get('verify_ssl', True)
        self.ca_bundle_paths = config.get('ca_bundle_path', [])

        # Validar configuração
        if not self.base_url:
            raise LLMAnalysisError("base_url é obrigatório para GenFactory")
        if not self.authorization_token:
            raise LLMAnalysisError("authorization_token é obrigatório para GenFactory")
        if not self.model:
            raise LLMAnalysisError("model é obrigatório para GenFactory")

        # Criar sessão HTTP
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.authorization_token}',
            'Content-Type': 'application/json'
        })

        # Configurar SSL
        if self.verify_ssl:
            if self.ca_bundle_paths:
                # Configurar SSL com certificados customizados
                self._setup_ssl_with_custom_certs()
            else:
                # Usar verificação SSL padrão
                self.session.verify = True
        else:
            # Desabilitar verificação SSL (não recomendado)
            self.session.verify = False
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        # Armazenar último usage capturado
        self.last_usage: Optional[TokenUsage] = None

        logger.info(f"GenFactoryClient inicializado: {self.base_url}, model={self.model}")

    def _setup_ssl_with_custom_certs(self) -> None:
        """
        Configura SSL com certificados customizados

        Cria um contexto SSL que inclui os certificados CA fornecidos
        """
        try:
            # Criar contexto SSL customizado
            ssl_context = ssl.create_default_context()

            # Carregar cada certificado CA
            for cert_path in self.ca_bundle_paths:
                cert_file = Path(cert_path)
                if cert_file.exists():
                    ssl_context.load_verify_locations(cert_file)
                    logger.debug(f"Certificado CA carregado: {cert_path}")
                else:
                    logger.warning(f"Certificado CA não encontrado: {cert_path}")

            # Criar adapter customizado com contexto SSL
            class SSLAdapter(HTTPAdapter):
                def init_poolmanager(self, *args, **kwargs):
                    kwargs['ssl_context'] = ssl_context
                    return super().init_poolmanager(*args, **kwargs)

            # Montar adapter na sessão
            self.session.mount('https://', SSLAdapter())
            self.session.verify = True

            logger.info(f"SSL configurado com {len(self.ca_bundle_paths)} certificados CA")

        except Exception as e:
            logger.error(f"Erro ao configurar SSL: {e}")
            raise LLMAnalysisError(f"Erro ao configurar SSL: {e}")

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        Envia mensagem para API e retorna resposta

        Args:
            messages: Lista de mensagens no formato [{"role": "user", "content": "..."}]
            **kwargs: Parâmetros adicionais (max_tokens, temperature, etc.)

        Returns:
            Conteúdo da resposta do modelo

        Raises:
            LLMAnalysisError: Se houver erro na requisição
        """
        # Construir endpoint (assumindo formato OpenAI-compatible)
        endpoint = f"{self.base_url}/chat/completions"

        # Construir payload
        payload = {
            'model': self.model,
            'messages': messages,
            **kwargs
        }

        try:
            logger.debug(f"Enviando requisição para {endpoint} com modelo {self.model}")

            response = self.session.post(
                endpoint,
                json=payload,
                timeout=self.timeout_sec
            )

            # Verificar status HTTP
            response.raise_for_status()

            # Parsear resposta
            response_data = response.json()

            # Extrair usage da resposta (se disponível)
            self.last_usage = self._extract_usage(response_data)

            # Extrair conteúdo da resposta
            # Formato esperado: {"choices": [{"message": {"content": "..."}}]}
            if 'choices' in response_data and len(response_data['choices']) > 0:
                content = response_data['choices'][0].get('message', {}).get('content', '')
                if content:
                    return content
                else:
                    raise LLMAnalysisError("Resposta da API não contém conteúdo")
            else:
                raise LLMAnalysisError(f"Formato de resposta inesperado: {response_data}")

        except requests.exceptions.Timeout:
            raise LLMAnalysisError(f"Timeout ao conectar com API GenFactory (>{self.timeout_sec}s)")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                raise LLMAnalysisError("Erro de autenticação: token inválido ou expirado")
            elif e.response.status_code == 403:
                raise LLMAnalysisError("Acesso negado: verifique permissões do token")
            elif e.response.status_code == 429:
                raise LLMAnalysisError("Rate limit excedido: tente novamente mais tarde")
            else:
                raise LLMAnalysisError(f"Erro HTTP {e.response.status_code}: {e.response.text}")
        except requests.exceptions.RequestException as e:
            raise LLMAnalysisError(f"Erro ao conectar com API GenFactory: {e}")
        except (KeyError, ValueError) as e:
            raise LLMAnalysisError(f"Erro ao processar resposta da API: {e}")

    def _extract_usage(self, response_data: Dict[str, Any]) -> Optional[TokenUsage]:
        """
        Extrai informações de uso de tokens da resposta da API

        Args:
            response_data: Dados da resposta JSON da API

        Returns:
            TokenUsage ou None se não disponível
        """
        # Formato OpenAI-compatible: {"usage": {"prompt_tokens": X, "completion_tokens": Y, "total_tokens": Z}}
        usage_data = response_data.get('usage')
        if not usage_data:
            return None

        try:
            prompt_tokens = usage_data.get('prompt_tokens', 0)
            completion_tokens = usage_data.get('completion_tokens', 0)
            total_tokens = usage_data.get('total_tokens', prompt_tokens + completion_tokens)

            return TokenUsage(
                prompt_tokens=int(prompt_tokens),
                completion_tokens=int(completion_tokens),
                total_tokens=int(total_tokens)
            )
        except (ValueError, TypeError) as e:
            logger.warning(f"Erro ao parsear usage da resposta: {e}")
            return None

    def get_last_usage(self) -> Optional[TokenUsage]:
        """
        Retorna o último usage capturado

        Returns:
            TokenUsage do último request ou None
        """
        return self.last_usage

    def __repr__(self) -> str:
        """Representação string do cliente"""
        return f"GenFactoryClient(base_url={self.base_url}, model={self.model})"
