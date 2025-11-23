"""
Testes para LLMAnalyzer
"""

import pytest
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

