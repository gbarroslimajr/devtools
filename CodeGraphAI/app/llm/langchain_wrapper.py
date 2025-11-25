"""
Wrapper LangChain para GenFactoryClient
Permite usar GenFactoryClient com LLMChain do LangChain
"""

import logging
from typing import Any, List, Optional, Dict
from langchain_core.language_models.llms import BaseLLM
from langchain_core.callbacks.manager import CallbackManagerForLLMRun
from langchain_core.outputs import LLMResult, Generation
from pydantic import ConfigDict, Field

from app.llm.genfactory_client import GenFactoryClient
from app.core.models import TokenUsage, LLMAnalysisError

logger = logging.getLogger(__name__)


class GenFactoryLLM(BaseLLM):
    """
    Wrapper LangChain para GenFactoryClient.

    Permite usar GenFactoryClient com LLMChain e outros componentes do LangChain.
    Implementa BaseLLM com suporte a batch processing e tracking de token usage.
    """

    # Configuração Pydantic v2: permite campos extras e tipos arbitrários
    # Necessário porque 'client' não é um campo Pydantic padrão
    model_config = ConfigDict(
        extra='allow',
        arbitrary_types_allowed=True,
        protected_namespaces=()
    )

    # Declarar campos como opcionais e excluídos da validação
    # Serão definidos via object.__setattr__ após super().__init__()
    # Nota: Pydantic v2 não permite campos com underscore inicial
    client: Optional[GenFactoryClient] = Field(default=None, exclude=True)
    last_llm_output: Dict[str, Any] = Field(default_factory=dict, exclude=True)

    def __init__(self, genfactory_client: GenFactoryClient, **kwargs: Any) -> None:
        """
        Inicializa wrapper LangChain.

        Args:
            genfactory_client: Instância de GenFactoryClient configurada
            **kwargs: Argumentos adicionais para BaseLLM (callbacks, etc.)

        Raises:
            LLMAnalysisError: Se genfactory_client for None ou inválido
        """
        if genfactory_client is None:
            raise LLMAnalysisError("GenFactoryClient não pode ser None")

        super().__init__(**kwargs)

        # Usar object.__setattr__ para contornar validação do Pydantic v2
        # Isso é necessário porque 'client' não é um campo declarado no modelo
        object.__setattr__(self, 'client', genfactory_client)
        object.__setattr__(self, 'last_llm_output', {})

    @property
    def _llm_type(self) -> str:
        """Tipo do LLM"""
        return "genfactory"

    def _generate(
        self,
        prompts: List[str],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> LLMResult:
        """
        Gera respostas para uma lista de prompts (método abstrato obrigatório).

        Este método é chamado pelo LangChain para processar múltiplos prompts,
        suportando batch processing. Processa cada prompt sequencialmente
        e agrega os resultados em um LLMResult.

        Args:
            prompts: Lista de prompts para processar
            stop: Lista de strings para parar geração (não suportado ainda)
            run_manager: Callback manager para tracking de execução
            **kwargs: Parâmetros adicionais passados para a API (max_tokens, temperature, etc.)

        Returns:
            LLMResult contendo generations e llm_output com token usage

        Raises:
            LLMAnalysisError: Se houver erro ao processar algum prompt
        """
        if not hasattr(self, 'client') or not self.client:
            raise LLMAnalysisError("GenFactoryClient não está inicializado")

        logger.debug(f"Processando {len(prompts)} prompt(s) via GenFactory API")

        generations: List[List[Generation]] = []
        total_prompt_tokens = 0
        total_completion_tokens = 0
        total_tokens = 0
        llm_output: Dict[str, Any] = {}

        try:
            for i, prompt in enumerate(prompts):
                logger.debug(f"Processando prompt {i + 1}/{len(prompts)}")

                # Converter prompt para formato de mensagens
                messages = [{"role": "user", "content": prompt}]

                # Chamar API GenFactory
                response_text = self.client.chat(messages, **kwargs)

                # Extrair token usage da última requisição
                usage = self.client.get_last_usage()
                if usage:
                    total_prompt_tokens += usage.prompt_tokens
                    total_completion_tokens += usage.completion_tokens
                    total_tokens += usage.total_tokens
                    logger.debug(
                        f"Prompt {i + 1}: {usage.prompt_tokens} prompt tokens, "
                        f"{usage.completion_tokens} completion tokens"
                    )
                else:
                    logger.warning(f"Token usage não disponível para prompt {i + 1}")

                # Criar Generation object
                generation = Generation(text=response_text)
                generations.append([generation])

            # Construir llm_output com token usage agregado
            if total_tokens > 0:
                llm_output = {
                    'token_usage': {
                        'prompt_tokens': total_prompt_tokens,
                        'completion_tokens': total_completion_tokens,
                        'total_tokens': total_tokens
                    }
                }
                logger.debug(
                    f"Total tokens: {total_prompt_tokens} prompt + "
                    f"{total_completion_tokens} completion = {total_tokens} total"
                )
            else:
                logger.warning("Nenhum token usage disponível para nenhum prompt")
                llm_output = {}

            # Atualizar last_llm_output para compatibilidade com _call
            object.__setattr__(self, 'last_llm_output', llm_output)

            logger.info(f"Geração concluída: {len(generations)} prompt(s) processado(s)")

            return LLMResult(generations=generations, llm_output=llm_output)

        except LLMAnalysisError:
            # Re-raise LLMAnalysisError sem modificação
            raise
        except Exception as e:
            logger.error(f"Erro inesperado ao gerar respostas: {e}")
            raise LLMAnalysisError(f"Erro ao processar prompts: {e}") from e

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
            object.__setattr__(self, 'last_llm_output', {
                'token_usage': {
                    'prompt_tokens': usage.prompt_tokens,
                    'completion_tokens': usage.completion_tokens,
                    'total_tokens': usage.total_tokens
                }
            })
        else:
            object.__setattr__(self, 'last_llm_output', {})

        return response

    def _llm_output(self) -> Dict[str, Any]:
        """
        Retorna output do LLM incluindo metadata como usage.

        Returns:
            Dict com llm_output contendo token_usage
        """
        return getattr(self, 'last_llm_output', {})

    @property
    def _identifying_params(self) -> Dict[str, str]:
        """
        Parâmetros identificadores do modelo.

        Returns:
            Dicionário com parâmetros que identificam este modelo LLM
        """
        return {
            "base_url": self.client.base_url,
            "model": self.client.model
        }
