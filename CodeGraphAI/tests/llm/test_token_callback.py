"""
Testes para TokenUsageCallback e tracking de tokens
"""

import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime

from app.llm.token_callback import TokenUsageCallback
from app.llm.token_tracker import TokenTracker
from app.core.models import TokenUsage, LLMRequestMetrics


class TestTokenTracker:
    """Testes para TokenTracker"""

    def test_add_metrics(self):
        """Testa adição de métricas"""
        tracker = TokenTracker()
        metrics = LLMRequestMetrics(
            request_id="test-1",
            operation="test_op",
            tokens_in=100,
            tokens_out=50,
            tokens_total=150,
            timestamp=datetime.now(),
            use_toon=False
        )
        tracker.add_metrics(metrics)
        assert len(tracker.metrics) == 1
        assert tracker.metrics[0] == metrics

    def test_get_total_tokens(self):
        """Testa cálculo de totais"""
        tracker = TokenTracker()
        tracker.add_metrics(LLMRequestMetrics(
            request_id="test-1",
            operation="op1",
            tokens_in=100,
            tokens_out=50,
            tokens_total=150,
            timestamp=datetime.now(),
            use_toon=False
        ))
        tracker.add_metrics(LLMRequestMetrics(
            request_id="test-2",
            operation="op2",
            tokens_in=200,
            tokens_out=100,
            tokens_total=300,
            timestamp=datetime.now(),
            use_toon=False
        ))

        total = tracker.get_total_tokens()
        assert total.prompt_tokens == 300
        assert total.completion_tokens == 150
        assert total.total_tokens == 450

    def test_get_metrics_by_operation(self):
        """Testa agrupamento por operação"""
        tracker = TokenTracker()
        tracker.add_metrics(LLMRequestMetrics(
            request_id="test-1",
            operation="op1",
            tokens_in=100,
            tokens_out=50,
            tokens_total=150,
            timestamp=datetime.now(),
            use_toon=False
        ))
        tracker.add_metrics(LLMRequestMetrics(
            request_id="test-2",
            operation="op1",
            tokens_in=200,
            tokens_out=100,
            tokens_total=300,
            timestamp=datetime.now(),
            use_toon=False
        ))
        tracker.add_metrics(LLMRequestMetrics(
            request_id="test-3",
            operation="op2",
            tokens_in=50,
            tokens_out=25,
            tokens_total=75,
            timestamp=datetime.now(),
            use_toon=False
        ))

        by_op = tracker.get_metrics_by_operation()
        assert len(by_op) == 2
        assert len(by_op['op1']) == 2
        assert len(by_op['op2']) == 1

    def test_get_statistics(self):
        """Testa geração de estatísticas"""
        tracker = TokenTracker()
        tracker.add_metrics(LLMRequestMetrics(
            request_id="test-1",
            operation="op1",
            tokens_in=100,
            tokens_out=50,
            tokens_total=150,
            timestamp=datetime.now(),
            use_toon=False
        ))

        stats = tracker.get_statistics()
        assert stats['total_requests'] == 1
        assert stats['total_tokens']['total_tokens'] == 150
        assert 'by_operation' in stats
        assert 'average_tokens_per_request' in stats

    def test_get_toon_comparison_with_comparison(self):
        """Testa comparação TOON quando há requisições com e sem TOON"""
        tracker = TokenTracker()
        # Com TOON
        tracker.add_metrics(LLMRequestMetrics(
            request_id="test-1",
            operation="op1",
            tokens_in=100,
            tokens_out=50,
            tokens_total=150,
            timestamp=datetime.now(),
            use_toon=True
        ))
        # Sem TOON
        tracker.add_metrics(LLMRequestMetrics(
            request_id="test-2",
            operation="op1",
            tokens_in=200,
            tokens_out=100,
            tokens_total=300,
            timestamp=datetime.now(),
            use_toon=False
        ))

        comparison = tracker.get_toon_comparison()
        assert comparison is not None
        assert comparison['with_toon']['total_tokens'] == 150
        assert comparison['without_toon']['total_tokens'] == 300
        assert comparison['overall_savings_percent'] > 0

    def test_get_toon_comparison_only_toon(self):
        """Testa comparação TOON quando apenas TOON foi usado"""
        tracker = TokenTracker()
        tracker.add_metrics(LLMRequestMetrics(
            request_id="test-1",
            operation="op1",
            tokens_in=100,
            tokens_out=50,
            tokens_total=150,
            timestamp=datetime.now(),
            use_toon=True
        ))

        comparison = tracker.get_toon_comparison()
        assert comparison is not None
        assert comparison['without_toon'] is None
        assert 'note' in comparison

    def test_reset(self):
        """Testa reset do tracker"""
        tracker = TokenTracker()
        tracker.add_metrics(LLMRequestMetrics(
            request_id="test-1",
            operation="op1",
            tokens_in=100,
            tokens_out=50,
            tokens_total=150,
            timestamp=datetime.now(),
            use_toon=False
        ))
        tracker.reset()
        assert len(tracker.metrics) == 0


class TestTokenUsageCallback:
    """Testes para TokenUsageCallback"""

    def test_set_operation(self):
        """Testa definição de operação"""
        tracker = TokenTracker()
        callback = TokenUsageCallback(tracker)
        callback.set_operation("test_op", use_toon=True)
        assert callback.current_operation == "test_op"
        assert callback.current_use_toon is True

    def test_on_llm_end_with_usage(self):
        """Testa captura de usage em on_llm_end"""
        tracker = TokenTracker()
        callback = TokenUsageCallback(tracker)
        callback.set_operation("test_op", use_toon=False)

        # Mock response com usage
        mock_response = Mock()
        mock_response.llm_output = {
            'token_usage': {
                'prompt_tokens': 100,
                'completion_tokens': 50,
                'total_tokens': 150
            }
        }

        callback.on_llm_end(mock_response)

        assert len(tracker.metrics) == 1
        assert tracker.metrics[0].operation == "test_op"
        assert tracker.metrics[0].tokens_in == 100
        assert tracker.metrics[0].tokens_out == 50
        assert tracker.metrics[0].tokens_total == 150

    def test_on_llm_end_without_operation(self):
        """Testa que on_llm_end não adiciona métricas sem operação definida"""
        tracker = TokenTracker()
        callback = TokenUsageCallback(tracker)

        mock_response = Mock()
        mock_response.llm_output = {
            'token_usage': {
                'prompt_tokens': 100,
                'completion_tokens': 50,
                'total_tokens': 150
            }
        }

        callback.on_llm_end(mock_response)

        assert len(tracker.metrics) == 0

    def test_parse_usage_dict_openai_format(self):
        """Testa parsing de usage no formato OpenAI"""
        tracker = TokenTracker()
        callback = TokenUsageCallback(tracker)

        usage_dict = {
            'prompt_tokens': 100,
            'completion_tokens': 50,
            'total_tokens': 150
        }

        usage = callback._parse_usage_dict(usage_dict)
        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 50
        assert usage.total_tokens == 150

    def test_parse_usage_dict_anthropic_format(self):
        """Testa parsing de usage no formato Anthropic (input_tokens/output_tokens)"""
        tracker = TokenTracker()
        callback = TokenUsageCallback(tracker)

        usage_dict = {
            'input_tokens': 100,
            'output_tokens': 50
        }

        usage = callback._parse_usage_dict(usage_dict)
        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 50
        assert usage.total_tokens == 150  # Calculado automaticamente

    def test_extract_usage_from_response_metadata(self):
        """Testa extração de usage de response_metadata"""
        tracker = TokenTracker()
        callback = TokenUsageCallback(tracker)

        mock_response = Mock()
        mock_response.response_metadata = {
            'token_usage': {
                'prompt_tokens': 100,
                'completion_tokens': 50,
                'total_tokens': 150
            }
        }

        usage = callback._extract_usage(mock_response)
        assert usage is not None
        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 50

    def test_extract_usage_from_llm_output(self):
        """Testa extração de usage de llm_output"""
        tracker = TokenTracker()
        callback = TokenUsageCallback(tracker)

        mock_response = Mock()
        mock_response.llm_output = {
            'token_usage': {
                'prompt_tokens': 100,
                'completion_tokens': 50,
                'total_tokens': 150
            }
        }

        usage = callback._extract_usage(mock_response)
        assert usage is not None
        assert usage.prompt_tokens == 100


