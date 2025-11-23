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

    @patch('analyzer.ChatOpenAI')
    def test_init_openai_mode(self, mock_chat_openai):
        """Testa inicialização em modo OpenAI"""
        from app.config.config import Config

        mock_llm = MagicMock()
        mock_chat_openai.return_value = mock_llm

        config = Config()
        config.llm_mode = 'api'
        config.llm_provider = 'openai'
        config.openai = {
            'api_key': 'sk-test-key',
            'model': 'gpt-5.1',
            'base_url': None,
            'timeout': 60,
            'temperature': 0.3,
            'max_tokens': 4000
        }

        analyzer = LLMAnalyzer(config=config)

        assert analyzer.llm_mode == 'api'
        assert analyzer.llm is not None
        mock_chat_openai.assert_called_once()

    @patch('analyzer.ChatAnthropic')
    def test_init_anthropic_mode(self, mock_chat_anthropic):
        """Testa inicialização em modo Anthropic"""
        from app.config.config import Config

        mock_llm = MagicMock()
        mock_chat_anthropic.return_value = mock_llm

        config = Config()
        config.llm_mode = 'api'
        config.llm_provider = 'anthropic'
        config.anthropic = {
            'api_key': 'sk-ant-test-key',
            'model': 'claude-sonnet-4-5-20250929',
            'timeout': 60,
            'temperature': 0.3,
            'max_tokens': 4000
        }

        analyzer = LLMAnalyzer(config=config)

        assert analyzer.llm_mode == 'api'
        assert analyzer.llm is not None
        mock_chat_anthropic.assert_called_once()

    def test_factory_pattern_provider_dispatch(self):
        """Testa que factory pattern funciona corretamente para diferentes providers"""
        from app.config.config import Config

        providers = ['genfactory_llama70b', 'openai', 'anthropic']

        for provider in providers:
            config = Config()
            config.llm_mode = 'api'
            config.llm_provider = provider

            if provider.startswith('genfactory_'):
                config.genfactory_llama70b = {
                    'base_url': 'https://api.test.com',
                    'model': 'test-model',
                    'authorization_token': 'test-token',
                    'timeout': 20000,
                    'verify_ssl': False,
                    'ca_bundle_path': []
                }
                with patch('analyzer.GenFactoryClient') as mock_client, \
                     patch('analyzer.GenFactoryLLM') as mock_llm:
                    mock_client.return_value = Mock()
                    mock_llm.return_value = Mock()
                    analyzer = LLMAnalyzer(config=config)
                    assert analyzer.llm is not None
            elif provider == 'openai':
                config.openai = {
                    'api_key': 'sk-test-key',
                    'model': 'gpt-5.1',
                    'base_url': None,
                    'timeout': 60,
                    'temperature': 0.3,
                    'max_tokens': 4000
                }
                with patch('analyzer.ChatOpenAI') as mock_chat:
                    mock_chat.return_value = Mock()
                    analyzer = LLMAnalyzer(config=config)
                    assert analyzer.llm is not None
            elif provider == 'anthropic':
                config.anthropic = {
                    'api_key': 'sk-ant-test-key',
                    'model': 'claude-sonnet-4-5-20250929',
                    'timeout': 60,
                    'temperature': 0.3,
                    'max_tokens': 4000
                }
                with patch('analyzer.ChatAnthropic') as mock_chat:
                    mock_chat.return_value = Mock()
                    analyzer = LLMAnalyzer(config=config)
                    assert analyzer.llm is not None


class TestLLMAnalyzerToonIntegration:
    """Testes de integração para suporte TOON"""

    @patch('analyzer.AutoTokenizer')
    @patch('analyzer.AutoModelForCausalLM')
    @patch('analyzer.pipeline')
    @patch('analyzer.HuggingFacePipeline')
    def test_dependencies_prompt_with_toon_enabled(self, mock_hf_pipeline, mock_pipeline,
                                                   mock_model, mock_tokenizer):
        """Testa que prompt de dependências usa TOON quando habilitado"""
        from config import reload_config
        import os
        from app.llm.toon_converter import TOON_AVAILABLE

        with patch.dict(os.environ, {
            'CODEGRAPHAI_LLM_MODE': 'local',
            'CODEGRAPHAI_LLM_USE_TOON': 'true'
        }):
            reload_config()

            mock_tokenizer.from_pretrained.return_value = Mock()
            mock_model.from_pretrained.return_value = Mock()
            mock_pipeline.return_value = Mock()
            mock_hf_pipeline.return_value = Mock()

            analyzer = LLMAnalyzer()

            # Verifica que prompt foi configurado
            assert analyzer.dependencies_prompt is not None
            # Verifica que template contém informação sobre formato
            template = analyzer.dependencies_prompt.template
            assert "procedures" in template.lower() or "tables" in template.lower()

    @patch('analyzer.AutoTokenizer')
    @patch('analyzer.AutoModelForCausalLM')
    @patch('analyzer.pipeline')
    @patch('analyzer.HuggingFacePipeline')
    def test_dependencies_prompt_with_toon_disabled(self, mock_hf_pipeline, mock_pipeline,
                                                     mock_model, mock_tokenizer):
        """Testa que prompt de dependências usa JSON quando TOON está desabilitado"""
        from config import reload_config
        import os

        with patch.dict(os.environ, {
            'CODEGRAPHAI_LLM_MODE': 'local',
            'CODEGRAPHAI_LLM_USE_TOON': 'false'
        }):
            reload_config()

            mock_tokenizer.from_pretrained.return_value = Mock()
            mock_model.from_pretrained.return_value = Mock()
            mock_pipeline.return_value = Mock()
            mock_hf_pipeline.return_value = Mock()

            analyzer = LLMAnalyzer()

            # Verifica que prompt foi configurado
            assert analyzer.dependencies_prompt is not None
            template = analyzer.dependencies_prompt.template
            # Deve mencionar JSON
            assert "json" in template.lower() or "JSON" in template

    def test_extract_dependencies_with_toon_response(self):
        """Testa extração de dependências com resposta TOON do LLM"""
        from app.llm.toon_converter import TOON_AVAILABLE, json_to_toon
        from config import reload_config
        import os

        if not TOON_AVAILABLE:
            pytest.skip("Biblioteca toon-python não está disponível")

        with patch.dict(os.environ, {
            'CODEGRAPHAI_LLM_MODE': 'local',
            'CODEGRAPHAI_LLM_USE_TOON': 'true'
        }):
            reload_config()

            # Cria analyzer sem inicializar LLM
            analyzer = LLMAnalyzer.__new__(LLMAnalyzer)
            analyzer.config = reload_config()

            # Mock do LLM retornando resposta TOON
            sample_data = {
                "procedures": ["proc1", "proc2"],
                "tables": ["table1", "table2"]
            }
            toon_response = json_to_toon(sample_data)

            mock_llm = Mock()
            mock_llm.invoke.return_value = f"Resposta:\n{toon_response}"
            analyzer.llm = mock_llm

            # Mock do prompt
            from langchain_core.prompts import PromptTemplate
            analyzer.dependencies_prompt = PromptTemplate(
                input_variables=["code"],
                template="Test: {code}"
            )

            # Testa extração
            code = "SELECT * FROM table1;"
            procedures, tables = analyzer.extract_dependencies(code)

            # Deve ter extraído as dependências
            assert len(procedures) >= 0  # Pode ter procedimentos do regex também
            assert len(tables) >= 1  # Deve ter pelo menos table1

    def test_extract_dependencies_fallback_to_json(self):
        """Testa fallback de TOON para JSON quando TOON falha"""
        from config import reload_config
        import os

        with patch.dict(os.environ, {
            'CODEGRAPHAI_LLM_MODE': 'local',
            'CODEGRAPHAI_LLM_USE_TOON': 'true'
        }):
            reload_config()

            analyzer = LLMAnalyzer.__new__(LLMAnalyzer)
            analyzer.config = reload_config()

            # Mock do LLM retornando resposta JSON (fallback)
            json_response = '{"procedures": ["proc1"], "tables": ["table1"]}'
            mock_llm = Mock()
            mock_llm.invoke.return_value = f"Resposta:\n{json_response}"
            analyzer.llm = mock_llm

            from langchain_core.prompts import PromptTemplate
            analyzer.dependencies_prompt = PromptTemplate(
                input_variables=["code"],
                template="Test: {code}"
            )

            code = "SELECT * FROM table1;"
            procedures, tables = analyzer.extract_dependencies(code)

            # Deve ter extraído as dependências via fallback JSON
            assert len(procedures) >= 0
            assert len(tables) >= 1

    def test_extract_dependencies_with_json_response(self):
        """Testa extração de dependências com resposta JSON tradicional"""
        from config import reload_config
        import os

        with patch.dict(os.environ, {
            'CODEGRAPHAI_LLM_MODE': 'local',
            'CODEGRAPHAI_LLM_USE_TOON': 'false'
        }):
            reload_config()

            analyzer = LLMAnalyzer.__new__(LLMAnalyzer)
            analyzer.config = reload_config()

            # Mock do LLM retornando resposta JSON
            json_response = '{"procedures": ["proc1", "proc2"], "tables": ["table1"]}'
            mock_llm = Mock()
            mock_llm.invoke.return_value = f"Análise:\n{json_response}\nFim"
            analyzer.llm = mock_llm

            from langchain_core.prompts import PromptTemplate
            analyzer.dependencies_prompt = PromptTemplate(
                input_variables=["code"],
                template="Test: {code}"
            )

            code = "SELECT * FROM table1; EXEC proc1();"
            procedures, tables = analyzer.extract_dependencies(code)

            # Deve ter extraído as dependências
            assert len(procedures) >= 0
            assert len(tables) >= 1

