"""
Coletor de métricas de tokens para LLM
Gerencia e agrega métricas de uso de tokens em operações LLM
"""

import logging
from typing import List, Dict, Any, Optional
from collections import defaultdict
from datetime import datetime

from app.core.models import TokenUsage, LLMRequestMetrics

logger = logging.getLogger(__name__)


class TokenTracker:
    """Gerencia e agrega métricas de uso de tokens"""

    def __init__(self):
        """Inicializa o tracker de tokens"""
        self.metrics: List[LLMRequestMetrics] = []
        self._lock = None  # Para thread-safety futuro

    def add_metrics(self, metrics: LLMRequestMetrics) -> None:
        """
        Adiciona métricas ao tracker

        Args:
            metrics: Métricas de uma requisição LLM
        """
        self.metrics.append(metrics)
        logger.debug(
            f"Métricas adicionadas: {metrics.operation} - "
            f"{metrics.tokens_in} in, {metrics.tokens_out} out, "
            f"{metrics.tokens_total} total"
        )

    def get_total_tokens(self) -> TokenUsage:
        """
        Retorna total de tokens usados em todas as operações

        Returns:
            TokenUsage com totais agregados
        """
        if not self.metrics:
            return TokenUsage()

        total_prompt = sum(m.tokens_in for m in self.metrics)
        total_completion = sum(m.tokens_out for m in self.metrics)
        total_all = sum(m.tokens_total for m in self.metrics)

        return TokenUsage(
            prompt_tokens=total_prompt,
            completion_tokens=total_completion,
            total_tokens=total_all
        )

    def get_metrics_by_operation(self) -> Dict[str, List[LLMRequestMetrics]]:
        """
        Agrupa métricas por tipo de operação

        Returns:
            Dict com operação como chave e lista de métricas como valor
        """
        grouped = defaultdict(list)
        for metric in self.metrics:
            grouped[metric.operation].append(metric)
        return dict(grouped)

    def get_statistics(self) -> Dict[str, Any]:
        """
        Retorna estatísticas agregadas de uso de tokens

        Returns:
            Dict com estatísticas detalhadas
        """
        if not self.metrics:
            return {
                'total_requests': 0,
                'total_tokens': TokenUsage(),
                'by_operation': {},
                'average_tokens_per_request': TokenUsage()
            }

        total = self.get_total_tokens()
        by_operation = self.get_metrics_by_operation()

        # Calcular totais por operação
        operation_totals = {}
        for op, metrics_list in by_operation.items():
            op_total = sum(m.tokens_total for m in metrics_list)
            op_in = sum(m.tokens_in for m in metrics_list)
            op_out = sum(m.tokens_out for m in metrics_list)
            operation_totals[op] = {
                'count': len(metrics_list),
                'tokens_in': op_in,
                'tokens_out': op_out,
                'tokens_total': op_total,
                'average_per_request': {
                    'tokens_in': op_in / len(metrics_list) if metrics_list else 0,
                    'tokens_out': op_out / len(metrics_list) if metrics_list else 0,
                    'tokens_total': op_total / len(metrics_list) if metrics_list else 0
                }
            }

        # Calcular médias gerais
        num_requests = len(self.metrics)
        avg_tokens = TokenUsage(
            prompt_tokens=total.prompt_tokens / num_requests if num_requests > 0 else 0,
            completion_tokens=total.completion_tokens / num_requests if num_requests > 0 else 0,
            total_tokens=total.total_tokens / num_requests if num_requests > 0 else 0
        )

        return {
            'total_requests': num_requests,
            'total_tokens': {
                'prompt_tokens': total.prompt_tokens,
                'completion_tokens': total.completion_tokens,
                'total_tokens': total.total_tokens
            },
            'by_operation': operation_totals,
            'average_tokens_per_request': {
                'prompt_tokens': avg_tokens.prompt_tokens,
                'completion_tokens': avg_tokens.completion_tokens,
                'total_tokens': avg_tokens.total_tokens
            }
        }

    def get_toon_comparison(self) -> Optional[Dict[str, Any]]:
        """
        Compara uso de tokens com e sem TOON (se aplicável)

        Returns:
            Dict com comparação ou None se TOON não foi usado
        """
        # Separar métricas com e sem TOON
        with_toon = [m for m in self.metrics if m.use_toon]
        without_toon = [m for m in self.metrics if not m.use_toon]

        if not with_toon:
            return None  # TOON não foi usado

        # Calcular totais
        total_with_toon = sum(m.tokens_total for m in with_toon)
        total_without_toon = sum(m.tokens_total for m in without_toon) if without_toon else 0

        # Calcular economia (se houver comparação)
        if without_toon:
            # Comparar operações similares
            # Agrupar por operação para comparação mais precisa
            with_toon_by_op = defaultdict(list)
            without_toon_by_op = defaultdict(list)

            for m in with_toon:
                with_toon_by_op[m.operation].append(m)
            for m in without_toon:
                without_toon_by_op[m.operation].append(m)

            # Comparar operações que existem em ambos
            comparison_by_op = {}
            for op in set(with_toon_by_op.keys()) & set(without_toon_by_op.keys()):
                toon_total = sum(m.tokens_total for m in with_toon_by_op[op])
                no_toon_total = sum(m.tokens_total for m in without_toon_by_op[op])
                if no_toon_total > 0:
                    savings = ((no_toon_total - toon_total) / no_toon_total) * 100
                    comparison_by_op[op] = {
                        'with_toon': toon_total,
                        'without_toon': no_toon_total,
                        'savings_percent': savings,
                        'savings_tokens': no_toon_total - toon_total
                    }

            overall_savings = ((total_without_toon - total_with_toon) / total_without_toon * 100) if total_without_toon > 0 else 0

            return {
                'with_toon': {
                    'total_tokens': total_with_toon,
                    'request_count': len(with_toon)
                },
                'without_toon': {
                    'total_tokens': total_without_toon,
                    'request_count': len(without_toon)
                },
                'overall_savings_percent': overall_savings,
                'overall_savings_tokens': total_without_toon - total_with_toon,
                'by_operation': comparison_by_op
            }
        else:
            # Apenas TOON foi usado, sem comparação
            return {
                'with_toon': {
                    'total_tokens': total_with_toon,
                    'request_count': len(with_toon)
                },
                'without_toon': None,
                'note': 'TOON foi usado em todas as requisições. Não há comparação disponível.'
            }

    def reset(self) -> None:
        """Limpa todas as métricas armazenadas"""
        self.metrics.clear()
        logger.debug("Métricas de tokens resetadas")

    def get_all_metrics(self) -> List[LLMRequestMetrics]:
        """
        Retorna todas as métricas armazenadas

        Returns:
            Lista de todas as métricas
        """
        return self.metrics.copy()


