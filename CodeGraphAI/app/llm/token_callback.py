"""
Callback handler do LangChain para tracking de tokens
Captura métricas de uso de tokens de respostas LLM
"""

import logging
import uuid
from typing import Any, Dict, Optional
from datetime import datetime

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from app.core.models import TokenUsage, LLMRequestMetrics
from app.llm.token_tracker import TokenTracker

logger = logging.getLogger(__name__)


class TokenUsageCallback(BaseCallbackHandler):
    """Callback handler para capturar métricas de uso de tokens"""

    def __init__(self, tracker: TokenTracker):
        """
        Inicializa o callback

        Args:
            tracker: Instância do TokenTracker para armazenar métricas
        """
        super().__init__()
        self.tracker = tracker
        self.current_operation: Optional[str] = None
        self.current_use_toon: bool = False

    def set_operation(self, operation: str, use_toon: bool = False) -> None:
        """
        Define a operação atual para associar às métricas

        Args:
            operation: Nome da operação (ex: "analyze_business_logic")
            use_toon: Se TOON está sendo usado nesta operação
        """
        self.current_operation = operation
        self.current_use_toon = use_toon
        logger.debug(f"Operação definida: {operation}, TOON: {use_toon}")

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """
        Chamado quando uma requisição LLM termina

        Args:
            response: Resultado da requisição LLM
            **kwargs: Argumentos adicionais
        """
        # Se não há operação definida, usar operação genérica (para Agent)
        operation = self.current_operation or "agent_query"

        # Extrair usage da resposta
        usage = self._extract_usage(response, **kwargs)

        if usage:
            metrics = LLMRequestMetrics(
                request_id=str(uuid.uuid4()),
                operation=operation,
                tokens_in=usage.prompt_tokens,
                tokens_out=usage.completion_tokens,
                tokens_total=usage.total_tokens,
                timestamp=datetime.now(),
                use_toon=self.current_use_toon
            )
            self.tracker.add_metrics(metrics)
            if not self.current_operation:
                logger.debug(f"Métricas capturadas para operação genérica (agent_query)")
            else:
                logger.debug(
                    f"Métricas capturadas para {operation}: "
                    f"{usage.prompt_tokens} in, {usage.completion_tokens} out, "
                    f"{usage.total_tokens} total"
                )
        else:
            if not self.current_operation:
                logger.debug("Não foi possível extrair usage de tokens (operação genérica)")
            else:
                logger.warning(
                    f"Não foi possível extrair usage de tokens para {operation}"
                )

    def _extract_usage(
        self, response: LLMResult, **kwargs: Any
    ) -> Optional[TokenUsage]:
        """
        Extrai informações de uso de tokens da resposta

        Args:
            response: Resultado da requisição LLM
            **kwargs: Argumentos adicionais que podem conter usage

        Returns:
            TokenUsage ou None se não conseguir extrair
        """
        # Tentar extrair de response_metadata (formato padrão LangChain)
        if hasattr(response, 'llm_output') and response.llm_output:
            usage = response.llm_output.get('token_usage')
            if usage:
                return self._parse_usage_dict(usage)

        # Tentar extrair de kwargs (alguns providers passam aqui)
        if 'token_usage' in kwargs:
            usage = kwargs['token_usage']
            if isinstance(usage, dict):
                return self._parse_usage_dict(usage)

        # Tentar extrair de response_metadata diretamente (ChatOpenAI, ChatAnthropic)
        # Quando usado com invoke(), a resposta pode ter response_metadata
        if hasattr(response, 'response_metadata'):
            metadata = response.response_metadata
            if metadata and 'token_usage' in metadata:
                return self._parse_usage_dict(metadata['token_usage'])

        # Para GenFactory e outros, pode estar em llm_output de forma diferente
        if hasattr(response, 'llm_output') and isinstance(response.llm_output, dict):
            # Tentar diferentes formatos
            for key in ['usage', 'token_usage', 'tokenUsage']:
                if key in response.llm_output:
                    usage = response.llm_output[key]
                    if isinstance(usage, dict):
                        return self._parse_usage_dict(usage)

        # Se response tem generations, tentar extrair de lá
        if hasattr(response, 'generations') and response.generations:
            for gen_list in response.generations:
                for gen in gen_list:
                    if hasattr(gen, 'response_metadata'):
                        metadata = gen.response_metadata
                        if metadata and 'token_usage' in metadata:
                            return self._parse_usage_dict(metadata['token_usage'])

        return None

    def _parse_usage_dict(self, usage_dict: Dict[str, Any]) -> TokenUsage:
        """
        Parseia dicionário de usage para TokenUsage

        Args:
            usage_dict: Dicionário com informações de usage

        Returns:
            TokenUsage parseado
        """
        # Suporta diferentes formatos de nomes de campos
        prompt_tokens = (
            usage_dict.get('prompt_tokens') or
            usage_dict.get('promptTokens') or
            usage_dict.get('input_tokens') or
            usage_dict.get('inputTokens') or
            0
        )

        completion_tokens = (
            usage_dict.get('completion_tokens') or
            usage_dict.get('completionTokens') or
            usage_dict.get('output_tokens') or
            usage_dict.get('outputTokens') or
            0
        )

        total_tokens = (
            usage_dict.get('total_tokens') or
            usage_dict.get('totalTokens') or
            (prompt_tokens + completion_tokens)
        )

        return TokenUsage(
            prompt_tokens=int(prompt_tokens),
            completion_tokens=int(completion_tokens),
            total_tokens=int(total_tokens)
        )


