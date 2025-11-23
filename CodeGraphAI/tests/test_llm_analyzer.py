"""
Testes para LLMAnalyzer
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from analyzer import LLMAnalyzer
from app.core.models import LLMAnalysisError


class TestLLMAnalyzerRegex:
    """Testes para métodos regex do LLMAnalyzer (não requerem LLM)"""

    def test_extract_procedures_regex(self):
        """Testa extração de procedures via regex"""
        code = """
        BEGIN
            EXECUTE PROC1();
            PROC2(param1, param2);
            TO_DATE('2024-01-01', 'YYYY-MM-DD');
        END;
        """

        # Cria analyzer sem inicializar LLM (apenas para testar regex)
        analyzer = LLMAnalyzer.__new__(LLMAnalyzer)

        procedures = analyzer._extract_procedures_regex(code)

        assert "PROC1" in procedures
        assert "PROC2" in procedures
        assert "TO_DATE" not in procedures  # Função built-in deve ser filtrada

    def test_extract_tables_regex(self):
        """Testa extração de tabelas via regex"""
        code = """
        BEGIN
            SELECT * FROM clientes;
            INSERT INTO pedidos VALUES (...);
            UPDATE produtos SET preco = 100;
            DELETE FROM estoque WHERE id = 1;
        END;
        """

        analyzer = LLMAnalyzer.__new__(LLMAnalyzer)

        tables = analyzer._extract_tables_regex(code)

        assert "CLIENTES" in tables
        assert "PEDIDOS" in tables
        assert "PRODUTOS" in tables
        assert "ESTOQUE" in tables

    def test_calculate_complexity_heuristic(self):
        """Testa cálculo heurístico de complexidade"""
        # Código simples
        simple_code = "BEGIN NULL; END;"

        # Código complexo
        complex_code = """
        BEGIN
            IF condicao1 THEN
                FOR i IN 1..100 LOOP
                    CURSOR c1 IS SELECT * FROM tabela;
                    OPEN c1;
                    FETCH c1 INTO var;
                    CLOSE c1;
                END LOOP;
            END IF;

            EXCEPTION
                WHEN OTHERS THEN
                    NULL;
            END;
        """

        analyzer = LLMAnalyzer.__new__(LLMAnalyzer)

        simple_score = analyzer._calculate_complexity_heuristic(simple_code)
        complex_score = analyzer._calculate_complexity_heuristic(complex_code)

        assert 1 <= simple_score <= 10
        assert 1 <= complex_score <= 10
        assert complex_score > simple_score  # Código complexo deve ter score maior


class TestLLMAnalyzerInitialization:
    """Testes para inicialização do LLMAnalyzer"""

    @patch('analyzer.AutoTokenizer')
    @patch('analyzer.AutoModelForCausalLM')
    @patch('analyzer.pipeline')
    @patch('analyzer.HuggingFacePipeline')
    def test_init_local_mode(self, mock_hf_pipeline, mock_pipeline,
                             mock_model, mock_tokenizer):
        """Testa inicialização em modo local (backward compatibility)"""
        from config import reload_config
        import os

        # Mock config para modo local
        with patch.dict(os.environ, {'CODEGRAPHAI_LLM_MODE': 'local'}):
            reload_config()

            mock_tokenizer.return_value = Mock()
            mock_model.return_value = Mock()
            mock_pipeline.return_value = Mock()
            mock_hf_pipeline.return_value = Mock()

            analyzer = LLMAnalyzer(model_name="test-model", device="cpu")

            assert analyzer.llm_mode == 'local'
            assert analyzer.llm is not None
            mock_tokenizer.from_pretrained.assert_called_once_with("test-model")

    @patch('analyzer.GenFactoryClient')
    @patch('analyzer.GenFactoryLLM')
    def test_init_api_mode(self, mock_genfactory_llm, mock_genfactory_client):
        """Testa inicialização em modo API"""
        from config import reload_config
        import os

        # Mock config para modo API
        with patch.dict(os.environ, {
            'CODEGRAPHAI_LLM_MODE': 'api',
            'CODEGRAPHAI_LLM_PROVIDER': 'genfactory_llama70b',
            'CODEGRAPHAI_GENFACTORY_LLAMA70B_BASE_URL': 'https://api.test.com',
            'CODEGRAPHAI_GENFACTORY_LLAMA70B_MODEL': 'test-model',
            'CODEGRAPHAI_GENFACTORY_LLAMA70B_AUTHORIZATION_TOKEN': 'test-token',
            'CODEGRAPHAI_GENFACTORY_LLAMA70B_TIMEOUT': '20000',
            'CODEGRAPHAI_GENFACTORY_LLAMA70B_VERIFY_SSL': 'false'
        }):
            reload_config()

            mock_client_instance = Mock()
            mock_genfactory_client.return_value = mock_client_instance
            mock_llm_instance = Mock()
            mock_genfactory_llm.return_value = mock_llm_instance

            analyzer = LLMAnalyzer(llm_mode='api')

            assert analyzer.llm_mode == 'api'
            assert analyzer.llm is not None
            mock_genfactory_client.assert_called_once()
            mock_genfactory_llm.assert_called_once_with(mock_client_instance)

    def test_init_backward_compatibility(self):
        """Testa backward compatibility - chamada sem parâmetros deve usar modo local"""
        from config import reload_config
        import os

        with patch.dict(os.environ, {'CODEGRAPHAI_LLM_MODE': 'local'}):
            reload_config()

            with patch('analyzer.AutoTokenizer') as mock_tokenizer, \
                 patch('analyzer.AutoModelForCausalLM') as mock_model, \
                 patch('analyzer.pipeline') as mock_pipeline, \
                 patch('analyzer.HuggingFacePipeline') as mock_hf_pipeline:

                mock_tokenizer.from_pretrained.return_value = Mock()
                mock_model.from_pretrained.return_value = Mock()
                mock_pipeline.return_value = Mock()
                mock_hf_pipeline.return_value = Mock()

                # Chamada antiga (sem parâmetros) deve funcionar
                analyzer = LLMAnalyzer()

                assert analyzer.llm_mode == 'local'
                assert analyzer.llm is not None

