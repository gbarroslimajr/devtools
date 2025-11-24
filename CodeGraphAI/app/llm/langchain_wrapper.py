"""
Wrapper LangChain para GenFactoryClient
Permite usar GenFactoryClient com LLMChain do LangChain
"""

from typing import Any, List, Optional, Dict
from langchain_core.language_models.llms import BaseLLM
from langchain_core.callbacks.manager import CallbackManagerForLLMRun

from app.llm.genfactory_client import GenFactoryClient
from app.core.models import TokenUsage


class GenFactoryLLM(BaseLLM):
    """Wrapper LangChain para GenFactoryClient"""

    def __init__(self, genfactory_client: GenFactoryClient, **kwargs: Any):
        """
        Inicializa wrapper LangChain

        Args:
            genfactory_client: Instância de GenFactoryClient
            **kwargs: Argumentos adicionais para BaseLLM
        """
        super().__init__(**kwargs)
        self.client = genfactory_client

    @property
    def _llm_type(self) -> str:
        """Tipo do LLM"""
        return "genfactory"

    def _call(
            self,
            prompt: str,
            stop: Optional[List[str]] = None,
            run_manager: Optional[CallbackManagerForLLMRun] = None,
            **kwargs: Any,
    ) -> str:
        """
        Chama o modelo via API GenFactory

        Args:
            prompt: Texto do prompt
            stop: Lista de strings para parar geração (não suportado ainda)
            run_manager: Callback manager (não usado)
            **kwargs: Parâmetros adicionais

        Returns:
            Resposta do modelo
        """
        # Converter prompt para formato de mensagens
        messages = [{"role": "user", "content": prompt}]

        # Chamar API
        response = self.client.chat(messages, **kwargs)

        # Armazenar usage para acesso via llm_output
        # Isso será usado pelos callbacks para extrair métricas
        usage = self.client.get_last_usage()
        if usage:
            # Armazenar em atributo temporário para acesso via _llm_output
            self._last_llm_output = {
                'token_usage': {
                    'prompt_tokens': usage.prompt_tokens,
                    'completion_tokens': usage.completion_tokens,
                    'total_tokens': usage.total_tokens
                }
            }
        else:
            self._last_llm_output = {}

        return response

    def _llm_output(self) -> Dict[str, Any]:
        """
        Retorna output do LLM incluindo metadata como usage

        Returns:
            Dict com llm_output contendo token_usage
        """
        return getattr(self, '_last_llm_output', {})

    @property
    def _identifying_params(self) -> dict:
        """Parâmetros identificadores do modelo"""
        return {
            "base_url": self.client.base_url,
            "model": self.client.model
        }
