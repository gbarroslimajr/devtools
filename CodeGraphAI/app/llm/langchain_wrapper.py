"""
Wrapper LangChain para GenFactoryClient
Permite usar GenFactoryClient com LLMChain do LangChain
"""

from typing import Any, List, Optional
from langchain.llms.base import BaseLLM
from langchain.callbacks.manager import CallbackManagerForLLMRun

from app.llm.genfactory_client import GenFactoryClient


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

        return response

    @property
    def _identifying_params(self) -> dict:
        """Parâmetros identificadores do modelo"""
        return {
            "base_url": self.client.base_url,
            "model": self.client.model
        }

