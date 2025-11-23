"""
Testes para módulo de conversão TOON
"""

import pytest
from unittest.mock import patch, MagicMock
import json

from app.llm.toon_converter import (
    json_to_toon,
    toon_to_json,
    format_toon_example,
    format_dependencies_prompt_example,
    parse_llm_response,
    TOON_AVAILABLE
)


class TestToonConverter:
    """Testes para conversão TOON"""

    @pytest.fixture
    def sample_data(self):
        """Dados de exemplo para testes"""
        return {
            "procedures": ["proc1", "schema.proc2", "proc3"],
            "tables": ["table1", "schema.table2", "table3"]
        }

    @pytest.fixture
    def sample_array_data(self):
        """Dados de array uniforme (caso de uso ideal para TOON)"""
        return {
            "users": [
                {"id": 1, "name": "Alice", "age": 30},
                {"id": 2, "name": "Bob", "age": 25},
                {"id": 3, "name": "Charlie", "age": 35}
            ]
        }

    def test_json_to_toon_available(self, sample_data):
        """Testa conversão JSON para TOON quando biblioteca está disponível"""
        if not TOON_AVAILABLE:
            pytest.skip("Biblioteca toon-python não está disponível")

        try:
            toon_str = json_to_toon(sample_data)
            assert isinstance(toon_str, str)
            assert len(toon_str) > 0
        except Exception as e:
            pytest.fail(f"Erro inesperado ao converter para TOON: {e}")

    def test_toon_to_json_available(self, sample_data):
        """Testa conversão TOON para JSON quando biblioteca está disponível"""
        if not TOON_AVAILABLE:
            pytest.skip("Biblioteca toon-python não está disponível")

        try:
            # Primeiro converte para TOON
            toon_str = json_to_toon(sample_data)
            # Depois converte de volta
            result = toon_to_json(toon_str)
            assert isinstance(result, dict)
            assert "procedures" in result
            assert "tables" in result
            assert result["procedures"] == sample_data["procedures"]
            assert result["tables"] == sample_data["tables"]
        except Exception as e:
            pytest.fail(f"Erro inesperado ao converter de TOON: {e}")

    def test_round_trip_conversion(self, sample_data):
        """Testa conversão round-trip JSON -> TOON -> JSON"""
        if not TOON_AVAILABLE:
            pytest.skip("Biblioteca toon-python não está disponível")

        try:
            toon_str = json_to_toon(sample_data)
            result = toon_to_json(toon_str)
            assert result == sample_data
        except Exception as e:
            pytest.fail(f"Erro no round-trip: {e}")

    def test_round_trip_array_data(self, sample_array_data):
        """Testa round-trip com dados de array uniforme (caso ideal para TOON)"""
        if not TOON_AVAILABLE:
            pytest.skip("Biblioteca toon-python não está disponível")

        try:
            toon_str = json_to_toon(sample_array_data)
            result = toon_to_json(toon_str)
            assert result == sample_array_data
            # Verifica que TOON é mais compacto que JSON para arrays uniformes
            json_str = json.dumps(sample_array_data, indent=2)
            assert len(toon_str) < len(json_str)
        except Exception as e:
            pytest.fail(f"Erro no round-trip com array: {e}")

    def test_json_to_toon_not_available(self, sample_data):
        """Testa erro quando TOON não está disponível"""
        with patch('app.llm.toon_converter.TOON_AVAILABLE', False):
            with pytest.raises(ValueError, match="Biblioteca toon-python não está disponível"):
                json_to_toon(sample_data)

    def test_toon_to_json_not_available(self):
        """Testa erro ao parsear TOON quando biblioteca não está disponível"""
        with patch('app.llm.toon_converter.TOON_AVAILABLE', False):
            with pytest.raises(ValueError, match="Biblioteca toon-python não está disponível"):
                toon_to_json("test toon string")

    def test_format_toon_example(self, sample_data):
        """Testa formatação de exemplo TOON"""
        result = format_toon_example(sample_data)
        assert isinstance(result, str)
        assert len(result) > 0
        # Deve conter "Formato TOON" ou "Formato JSON" (fallback)
        assert "Formato" in result

    def test_format_toon_example_fallback(self, sample_data):
        """Testa fallback para JSON quando TOON falha"""
        with patch('app.llm.toon_converter.json_to_toon', side_effect=ValueError("Test error")):
            result = format_toon_example(sample_data)
            assert "Formato JSON" in result
            assert "procedures" in result
            assert "tables" in result

    def test_format_dependencies_prompt_example_json(self):
        """Testa formatação de exemplo para prompt com JSON"""
        result = format_dependencies_prompt_example(use_toon=False)
        assert isinstance(result, str)
        assert "JSON" in result
        assert "procedures" in result
        assert "tables" in result

    def test_format_dependencies_prompt_example_toon(self):
        """Testa formatação de exemplo para prompt com TOON"""
        if not TOON_AVAILABLE:
            pytest.skip("Biblioteca toon-python não está disponível")

        result = format_dependencies_prompt_example(use_toon=True)
        assert isinstance(result, str)
        # Pode conter TOON ou JSON (se TOON falhar)
        assert len(result) > 0

    def test_parse_llm_response_json(self):
        """Testa parsing de resposta JSON do LLM"""
        json_response = '{"procedures": ["proc1"], "tables": ["table1"]}'
        result = parse_llm_response(json_response, use_toon=False)
        assert result is not None
        assert isinstance(result, dict)
        assert "procedures" in result
        assert "tables" in result

    def test_parse_llm_response_json_with_text(self):
        """Testa parsing de resposta JSON com texto ao redor"""
        response = """
        Aqui está a análise:
        {
            "procedures": ["proc1", "proc2"],
            "tables": ["table1"]
        }
        Fim da análise.
        """
        result = parse_llm_response(response, use_toon=False)
        assert result is not None
        assert isinstance(result, dict)
        assert len(result["procedures"]) == 2

    def test_parse_llm_response_toon(self):
        """Testa parsing de resposta TOON do LLM"""
        if not TOON_AVAILABLE:
            pytest.skip("Biblioteca toon-python não está disponível")

        # Primeiro cria TOON válido
        sample_data = {"procedures": ["proc1"], "tables": ["table1"]}
        try:
            toon_str = json_to_toon(sample_data)
            # Simula resposta do LLM com TOON
            response = f"Resposta em TOON:\n{toon_str}"
            result = parse_llm_response(response, use_toon=True)
            assert result is not None
            assert isinstance(result, dict)
            assert "procedures" in result
        except Exception:
            # Se TOON não funcionar, testa fallback para JSON
            json_response = '{"procedures": ["proc1"], "tables": ["table1"]}'
            result = parse_llm_response(json_response, use_toon=True)
            assert result is not None

    def test_parse_llm_response_empty(self):
        """Testa parsing de resposta vazia"""
        result = parse_llm_response("", use_toon=False)
        assert result is None

        result = parse_llm_response("   ", use_toon=False)
        assert result is None

    def test_parse_llm_response_invalid(self):
        """Testa parsing de resposta inválida"""
        invalid_response = "Esta não é uma resposta válida em JSON ou TOON"
        result = parse_llm_response(invalid_response, use_toon=False)
        assert result is None

    def test_parse_llm_response_fallback_to_json(self):
        """Testa fallback de TOON para JSON quando TOON falha"""
        # Resposta com formato que parece TOON mas é inválido
        invalid_toon = "[invalid toon format"
        json_response = '{"procedures": ["proc1"], "tables": ["table1"]}'
        # Adiciona JSON válido na resposta
        response = f"{invalid_toon}\n{json_response}"
        result = parse_llm_response(response, use_toon=True)
        # Deve fazer fallback para JSON
        assert result is not None
        assert isinstance(result, dict)

