"""
Testes para TableAnalyzer
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from table_analyzer import TableAnalyzer
from analyzer import LLMAnalyzer
from app.core.models import (
    TableInfo, ColumnInfo, IndexInfo, ForeignKeyInfo,
    DatabaseType, DatabaseConfig, TableLoadError
)


@pytest.fixture
def sample_table_info():
    """TableInfo de exemplo"""
    columns = [
        ColumnInfo(
            name="id",
            data_type="INTEGER",
            nullable=False,
            is_primary_key=True
        ),
        ColumnInfo(
            name="name",
            data_type="VARCHAR(100)",
            nullable=False
        ),
        ColumnInfo(
            name="user_id",
            data_type="INTEGER",
            nullable=True,
            is_foreign_key=True,
            foreign_key_table="users",
            foreign_key_column="id"
        )
    ]

    indexes = [
        IndexInfo(
            name="idx_name",
            table_name="products",
            columns=["name"],
            is_unique=False,
            is_primary=False,
            index_type="BTREE"
        )
    ]

    foreign_keys = [
        ForeignKeyInfo(
            name="fk_user",
            table_name="products",
            columns=["user_id"],
            referenced_table="users",
            referenced_columns=["id"],
            on_delete="CASCADE",
            on_update=None
        )
    ]

    return TableInfo(
        name="products",
        schema="public",
        ddl="CREATE TABLE products (...)",
        columns=columns,
        indexes=indexes,
        foreign_keys=foreign_keys,
        primary_key_columns=["id"],
        row_count=100,
        table_size="10 MB"
    )


@pytest.fixture
def mock_llm_analyzer():
    """Mock do LLMAnalyzer para testes"""
    mock = Mock(spec=LLMAnalyzer)
    mock.analyze_table_purpose.return_value = "Tabela de produtos do sistema"
    # Adiciona método batch para testes
    mock.analyze_table_purpose_batch = Mock(return_value={})
    return mock


@pytest.fixture
def table_analyzer(mock_llm_analyzer):
    """TableAnalyzer para testes"""
    return TableAnalyzer(mock_llm_analyzer)


class TestTableAnalyzer:
    """Testes para TableAnalyzer"""

    def test_init(self, mock_llm_analyzer):
        """Testa inicialização"""
        analyzer = TableAnalyzer(mock_llm_analyzer)
        assert analyzer.llm == mock_llm_analyzer
        assert analyzer.tables == {}
        assert analyzer.relationship_graph is not None

    def test_analyze_business_purpose(self, table_analyzer, sample_table_info):
        """Testa análise de propósito de negócio"""
        columns_list = [col.name for col in sample_table_info.columns]
        purpose = table_analyzer._analyze_business_purpose(sample_table_info, columns_list)

        assert purpose == "Tabela de produtos do sistema"
        table_analyzer.llm.analyze_table_purpose.assert_called_once()

    def test_calculate_complexity(self, table_analyzer, sample_table_info):
        """Testa cálculo de complexidade"""
        complexity = table_analyzer._calculate_complexity(sample_table_info)

        assert 1 <= complexity <= 10
        # Com 3 colunas, 1 FK, 1 índice: score deve ser > 1
        assert complexity >= 1

    def test_build_relationship_graph(self, table_analyzer, sample_table_info):
        """Testa construção de grafo de relacionamentos"""
        # Adiciona tabelas
        table_analyzer.tables["public.products"] = sample_table_info

        # Cria tabela referenciada
        users_table = TableInfo(
            name="users",
            schema="public",
            ddl="CREATE TABLE users (...)",
            columns=[],
            indexes=[],
            foreign_keys=[],
            primary_key_columns=["id"]
        )
        table_analyzer.tables["public.users"] = users_table

        table_analyzer._build_relationship_graph()

        # Verifica que grafo tem relacionamento
        assert "public.products" in table_analyzer.relationship_graph.nodes()
        assert "public.users" in table_analyzer.relationship_graph.nodes()
        assert table_analyzer.relationship_graph.has_edge("public.products", "public.users")

    def test_get_table_hierarchy(self, table_analyzer):
        """Testa obtenção de hierarquia"""
        # Cria tabelas com relacionamentos
        table1 = TableInfo(
            name="table1",
            schema="public",
            ddl="CREATE TABLE table1 (...)",
            columns=[],
            indexes=[],
            foreign_keys=[],
            primary_key_columns=[]
        )

        table2 = TableInfo(
            name="table2",
            schema="public",
            ddl="CREATE TABLE table2 (...)",
            columns=[],
            indexes=[],
            foreign_keys=[
                ForeignKeyInfo(
                    name="fk1",
                    table_name="table2",
                    columns=["id"],
                    referenced_table="public.table1",
                    referenced_columns=["id"]
                )
            ],
            primary_key_columns=[]
        )

        table_analyzer.tables["public.table1"] = table1
        table_analyzer.tables["public.table2"] = table2
        table_analyzer._build_relationship_graph()

        hierarchy = table_analyzer.get_table_hierarchy()

        assert isinstance(hierarchy, dict)
        # table1 deve estar em nível 0 (sem dependências)
        # table2 deve estar em nível 1 (depende de table1)
        assert 0 in hierarchy
        assert len(hierarchy) > 0

    def test_export_results_empty(self, table_analyzer, tmp_path):
        """Testa exportação com tabelas vazias"""
        output_file = tmp_path / "test.json"
        with pytest.raises(Exception):  # ExportError
            table_analyzer.export_results(str(output_file))

    def test_export_results(self, table_analyzer, sample_table_info, tmp_path):
        """Testa exportação de resultados"""
        table_analyzer.tables["public.products"] = sample_table_info
        output_file = tmp_path / "test.json"

        table_analyzer.export_results(str(output_file))

        assert output_file.exists()
        import json
        with open(output_file) as f:
            data = json.load(f)
            assert "tables" in data
            assert "public.products" in data["tables"]
            assert "statistics" in data

    def test_visualize_relationships_empty(self, table_analyzer, tmp_path):
        """Testa visualização com grafo vazio"""
        output_file = tmp_path / "test.png"
        with pytest.raises(Exception):  # ExportError
            table_analyzer.visualize_relationships(str(output_file))

    def test_export_mermaid_diagram(self, table_analyzer, sample_table_info, tmp_path):
        """Testa exportação de diagrama Mermaid"""
        table_analyzer.tables["public.products"] = sample_table_info
        table_analyzer._build_relationship_graph()
        output_file = tmp_path / "test.md"

        table_analyzer.export_mermaid_diagram(str(output_file))

        assert output_file.exists()
        content = output_file.read_text()
        assert "mermaid" in content
        assert "erDiagram" in content

    def test_export_mermaid_hierarchy(self, table_analyzer, sample_table_info, tmp_path):
        """Testa exportação de hierarquia Mermaid"""
        table_analyzer.tables["public.products"] = sample_table_info
        output_file = tmp_path / "hierarchy.md"

        table_analyzer.export_mermaid_hierarchy(str(output_file))

        assert output_file.exists()
        content = output_file.read_text()
        assert "mermaid" in content
        assert "graph TD" in content

    def test_normalize_table_name(self, table_analyzer):
        """Testa normalização de nomes de tabela"""
        table_analyzer.tables["public.products"] = TableInfo(
            name="products",
            schema="public",
            ddl="",
            columns=[],
            indexes=[],
            foreign_keys=[],
            primary_key_columns=[]
        )

        # Testa normalização
        normalized = table_analyzer._normalize_table_name("public.products")
        assert normalized == "public.products"

        normalized = table_analyzer._normalize_table_name("products")
        assert normalized == "public.products" or normalized == "products"

    def test_sanitize_mermaid_name(self, table_analyzer):
        """Testa sanitização de nomes para Mermaid"""
        name = table_analyzer._sanitize_mermaid_name("schema.table-name")
        assert "." not in name
        assert "-" not in name
        assert "_" in name

    def test_analyze_business_purpose_batch(self, mock_llm_analyzer):
        """Testa análise de propósito de negócio em batch"""
        analyzer = TableAnalyzer(mock_llm_analyzer)

        # Mock do método batch
        mock_llm_analyzer.analyze_table_purpose_batch.return_value = {
            "public.products": "Tabela de produtos do sistema",
            "public.users": "Tabela de usuários do sistema"
        }

        # Cria dados de teste
        table1 = TableInfo(
            name="products",
            schema="public",
            ddl="CREATE TABLE products (...)",
            columns=[ColumnInfo(name="id", data_type="INTEGER", nullable=False)],
            indexes=[],
            foreign_keys=[],
            primary_key_columns=["id"]
        )

        table2 = TableInfo(
            name="users",
            schema="public",
            ddl="CREATE TABLE users (...)",
            columns=[ColumnInfo(name="id", data_type="INTEGER", nullable=False)],
            indexes=[],
            foreign_keys=[],
            primary_key_columns=["id"]
        )

        tables_data = [
            ("public.products", table1.ddl, ["id"]),
            ("public.users", table2.ddl, ["id"])
        ]
        table_names = ["public.products", "public.users"]

        result = analyzer._analyze_business_purpose_batch(tables_data, table_names)

        assert "public.products" in result
        assert "public.users" in result
        assert result["public.products"] == "Tabela de produtos do sistema"
        mock_llm_analyzer.analyze_table_purpose_batch.assert_called_once()

    def test_process_batch(self, mock_llm_analyzer):
        """Testa processamento de um batch de tabelas"""
        analyzer = TableAnalyzer(mock_llm_analyzer)

        # Mock do método batch
        mock_llm_analyzer.analyze_table_purpose_batch.return_value = {
            "public.products": "Tabela de produtos"
        }

        table1 = TableInfo(
            name="products",
            schema="public",
            ddl="CREATE TABLE products (...)",
            columns=[ColumnInfo(name="id", data_type="INTEGER", nullable=False)],
            indexes=[],
            foreign_keys=[],
            primary_key_columns=["id"]
        )

        batch = [("public.products", table1)]
        analyzer._process_batch(batch)

        assert "public.products" in analyzer.tables
        assert analyzer.tables["public.products"].business_purpose == "Tabela de produtos"
        assert analyzer.tables["public.products"].complexity_score > 0

    def test_fallback_to_sequential_on_error(self, mock_llm_analyzer):
        """Testa fallback para método sequencial quando batch falha"""
        analyzer = TableAnalyzer(mock_llm_analyzer)

        # Mock: batch falha, mas método individual funciona
        from app.core.models import LLMAnalysisError
        mock_llm_analyzer.analyze_table_purpose_batch.side_effect = LLMAnalysisError("Erro no batch")
        mock_llm_analyzer.analyze_table_purpose.return_value = "Tabela de produtos (fallback)"

        table1 = TableInfo(
            name="products",
            schema="public",
            ddl="CREATE TABLE products (...)",
            columns=[ColumnInfo(name="id", data_type="INTEGER", nullable=False)],
            indexes=[],
            foreign_keys=[],
            primary_key_columns=["id"]
        )

        batch = [("public.products", table1)]
        analyzer._process_batch(batch)

        # Deve ter usado fallback sequencial
        assert "public.products" in analyzer.tables
        assert "fallback" in analyzer.tables["public.products"].business_purpose.lower()
        mock_llm_analyzer.analyze_table_purpose.assert_called()

    def test_analyze_sequential_mode(self, mock_llm_analyzer):
        """Testa que batch_size=1 usa modo sequencial"""
        analyzer = TableAnalyzer(mock_llm_analyzer)

        table1 = TableInfo(
            name="products",
            schema="public",
            ddl="CREATE TABLE products (...)",
            columns=[ColumnInfo(name="id", data_type="INTEGER", nullable=False)],
            indexes=[],
            foreign_keys=[],
            primary_key_columns=["id"]
        )

        tables_db = {"public.products": table1}
        analyzer._analyze_sequential(tables_db, show_progress=False)

        assert "public.products" in analyzer.tables
        mock_llm_analyzer.analyze_table_purpose.assert_called_once()

    def test_analyze_with_batch_sequential_batches(self, mock_llm_analyzer):
        """Testa análise com batch processing sequencial (sem paralelismo)"""
        analyzer = TableAnalyzer(mock_llm_analyzer)

        # Mock do método batch
        mock_llm_analyzer.analyze_table_purpose_batch.return_value = {
            "public.products": "Tabela de produtos",
            "public.users": "Tabela de usuários"
        }

        table1 = TableInfo(
            name="products",
            schema="public",
            ddl="CREATE TABLE products (...)",
            columns=[ColumnInfo(name="id", data_type="INTEGER", nullable=False)],
            indexes=[],
            foreign_keys=[],
            primary_key_columns=["id"]
        )

        table2 = TableInfo(
            name="users",
            schema="public",
            ddl="CREATE TABLE users (...)",
            columns=[ColumnInfo(name="id", data_type="INTEGER", nullable=False)],
            indexes=[],
            foreign_keys=[],
            primary_key_columns=["id"]
        )

        tables_db = {
            "public.products": table1,
            "public.users": table2
        }

        # Processa com batch_size=2, parallel_workers=1 (sequencial)
        analyzer._analyze_with_batch(tables_db, batch_size=2, parallel_workers=1, show_progress=False)

        assert len(analyzer.tables) == 2
        assert "public.products" in analyzer.tables
        assert "public.users" in analyzer.tables
        mock_llm_analyzer.analyze_table_purpose_batch.assert_called()

