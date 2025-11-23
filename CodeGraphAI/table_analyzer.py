"""
Analisador de Tabelas de Banco de Dados usando LLM
Extrai, analisa e mapeia relacionamentos entre tabelas
"""

import json
import logging
from typing import Dict, List, Optional
from dataclasses import asdict
from collections import defaultdict
from pathlib import Path

import networkx as nx
import matplotlib.pyplot as plt
from tqdm import tqdm

from analyzer import LLMAnalyzer
from app.core.models import (
    TableInfo, DatabaseConfig, DatabaseType,
    TableLoadError, LLMAnalysisError, ExportError, ValidationError
)
from app.io.table_factory import create_table_loader

# Configurar logger
logger = logging.getLogger(__name__)

# Constantes de configuração
class TableAnalysisConfig:
    """Configurações para análise de tabelas"""
    MAX_DDL_LENGTH_BUSINESS_PURPOSE = 2000
    MAX_COLUMNS_FOR_PROMPT = 20

    # Heurística de complexidade
    COMPLEXITY_COLUMNS_THRESHOLD = 5
    COMPLEXITY_COLUMNS_MAX_BONUS = 3
    COMPLEXITY_FK_WEIGHT = 1
    COMPLEXITY_INDEX_WEIGHT = 0.5
    COMPLEXITY_MAX_SCORE = 10

    # Visualização
    GRAPH_FIGSIZE = (20, 15)
    GRAPH_NODE_SIZE = 1000
    GRAPH_FONT_SIZE = 8
    GRAPH_DPI = 300


class TableAnalyzer:
    """Orquestra análise completa de tabelas"""

    def __init__(self, llm_analyzer: LLMAnalyzer):
        """
        Inicializa o analisador de tabelas

        Args:
            llm_analyzer: Instância do LLMAnalyzer para análise com IA
        """
        self.llm = llm_analyzer
        self.tables: Dict[str, TableInfo] = {}
        self.relationship_graph = nx.DiGraph()

    def analyze_from_database(
        self,
        user: str,
        password: str,
        dsn: str,
        schema: Optional[str] = None,
        limit: Optional[int] = None,
        show_progress: bool = True,
        db_type: Optional[str] = None,
        database: Optional[str] = None,
        port: Optional[int] = None
    ) -> None:
        """
        Analisa tabelas diretamente do banco de dados

        Args:
            user: Usuário do banco de dados
            password: Senha do banco de dados
            dsn: Data Source Name (host:port/service para Oracle, host para outros)
            schema: Schema específico (opcional)
            limit: Limite de tabelas para análise (opcional)
            show_progress: Mostrar barra de progresso (padrão: True)
            db_type: Tipo de banco (oracle, postgresql, mssql, mysql).
                    Se None, assume PostgreSQL
            database: Nome do banco de dados (obrigatório para PostgreSQL, SQL Server, MySQL)
            port: Porta do banco de dados

        Raises:
            TableLoadError: Se houver erro ao carregar do banco
        """
        # Determina tipo de banco
        if db_type is None:
            db_type = 'postgresql'  # Default

        try:
            db_type_enum = DatabaseType(db_type.lower())
        except ValueError:
            raise ValidationError(
                f"Tipo de banco inválido: {db_type}. "
                f"Tipos suportados: {[dt.value for dt in DatabaseType]}"
            )

        # Resolve host/dsn
        if ':' in dsn and '/' in dsn:
            # Oracle format: host:port/service
            connection_host = dsn
        else:
            connection_host = dsn

        # Cria DatabaseConfig
        config = DatabaseConfig(
            db_type=db_type_enum,
            user=user,
            password=password,
            host=connection_host,
            port=port,
            database=database,
            schema=schema
        )

        # Carrega tabelas do banco
        loader = create_table_loader(db_type_enum)
        tables_db = loader.load_tables(config)

        if limit and limit > 0:
            tables_db = dict(list(tables_db.items())[:limit])
            logger.info(f"Limitando análise a {limit} tabelas")

        logger.info(f"Iniciando análise de {len(tables_db)} tabelas...")

        # Usa tqdm para progress bar se solicitado
        iterator = tqdm(tables_db.items(), desc="Analisando tabelas",
                       total=len(tables_db), disable=not show_progress) if show_progress else tables_db.items()

        for table_name, table_info in iterator:
            if show_progress:
                iterator.set_postfix({"current": table_name[:30]})
            logger.debug(f"Analisando {table_name}...")

            try:
                # Analisa propósito de negócio com LLM
                columns_list = [col.name for col in table_info.columns]
                table_info.business_purpose = self._analyze_business_purpose(table_info, columns_list)

                # Calcula complexidade
                table_info.complexity_score = self._calculate_complexity(table_info)

                self.tables[table_name] = table_info
            except Exception as e:
                logger.error(f"Erro ao analisar {table_name}: {e}")
                # Continua com outras tabelas mesmo se uma falhar

        # Constrói grafo de relacionamentos
        logger.info("Construindo grafo de relacionamentos...")
        self._build_relationship_graph()

        logger.info("Análise concluída!")

    def _analyze_business_purpose(self, table_info: TableInfo, columns_list: List[str]) -> str:
        """
        Usa LLM para entender o propósito da tabela

        Args:
            table_info: Informações da tabela
            columns_list: Lista de nomes de colunas

        Returns:
            Descrição do propósito de negócio
        """
        try:
            return self.llm.analyze_table_purpose(
                table_info.ddl,
                f"{table_info.schema}.{table_info.name}",
                columns_list
            )
        except LLMAnalysisError as e:
            logger.warning(f"Erro na análise LLM de {table_info.name}: {e}")
            return f"Tabela {table_info.name} com {len(table_info.columns)} colunas"

    def _calculate_complexity(self, table_info: TableInfo) -> int:
        """
        Calcula score de complexidade (1-10)

        Args:
            table_info: Informações da tabela

        Returns:
            Score de complexidade entre 1 e 10
        """
        score = 1

        # Baseado em número de colunas
        score += min(
            len(table_info.columns) // TableAnalysisConfig.COMPLEXITY_COLUMNS_THRESHOLD,
            TableAnalysisConfig.COMPLEXITY_COLUMNS_MAX_BONUS
        )

        # Baseado em foreign keys
        score += min(len(table_info.foreign_keys) * TableAnalysisConfig.COMPLEXITY_FK_WEIGHT, 3)

        # Baseado em índices
        score += min(len(table_info.indexes) * TableAnalysisConfig.COMPLEXITY_INDEX_WEIGHT, 2)

        return min(int(score), TableAnalysisConfig.COMPLEXITY_MAX_SCORE)

    def _build_relationship_graph(self) -> None:
        """Constrói grafo de relacionamentos baseado em foreign keys"""
        if not self.tables:
            logger.warning("Nenhuma tabela para construir grafo de relacionamentos")
            return

        for table_name, table_info in self.tables.items():
            self.relationship_graph.add_node(table_name, table_info=table_info)

            for fk in table_info.foreign_keys:
                target = fk.referenced_table
                # Normaliza nome da tabela (pode estar com ou sem schema)
                target_normalized = self._normalize_table_name(target)

                if target_normalized in self.tables or target in self.tables:
                    # Usa o nome normalizado se existir, senão usa o original
                    target_node = target_normalized if target_normalized in self.tables else target

                    self.relationship_graph.add_edge(
                        table_name, target_node,
                        relationship_type='foreign_key',
                        columns=fk.columns,
                        referenced_columns=fk.referenced_columns,
                        constraint_name=fk.name
                    )

                    # Atualiza relationships no TableInfo
                    if target_node not in table_info.relationships:
                        table_info.relationships[target_node] = []
                    table_info.relationships[target_node].append('foreign_key')

    def _normalize_table_name(self, table_name: str) -> str:
        """
        Normaliza nome de tabela para matching
        Remove schema se necessário ou adiciona se faltar
        """
        # Se já existe no grafo, retorna como está
        if table_name in self.tables:
            return table_name

        # Tenta encontrar sem schema
        if '.' in table_name:
            schema, name = table_name.split('.', 1)
            # Procura por nome sem schema
            for existing_name in self.tables.keys():
                if existing_name.endswith(f".{name}") or existing_name == name:
                    return existing_name

        return table_name

    def get_table_hierarchy(self) -> Dict[int, List[str]]:
        """
        Retorna tabelas organizadas por nível hierárquico baseado em FKs

        Returns:
            Dict com nível como chave e lista de tabelas como valor
        """
        if not self.relationship_graph.nodes():
            return {}

        # Calcula níveis baseado em dependências FK (tabelas referenciadas)
        try:
            # Ordenação topológica reversa (bottom-up)
            topo_order = list(reversed(list(nx.topological_sort(self.relationship_graph))))

            levels = {}
            for node in topo_order:
                # Nível = max(níveis das tabelas referenciadas) + 1
                predecessors = list(self.relationship_graph.predecessors(node))
                if not predecessors:
                    levels[node] = 0  # Tabela base (sem dependências)
                else:
                    max_dep_level = max([levels.get(p, 0) for p in predecessors], default=-1)
                    levels[node] = max_dep_level + 1

            # Organiza por nível
            hierarchy = defaultdict(list)
            for table_name, level in levels.items():
                hierarchy[level].append(table_name)

            return dict(sorted(hierarchy.items()))
        except nx.NetworkXError:
            # Em caso de ciclos, todas ficam no nível 0
            return {0: list(self.tables.keys())}

    def export_results(self, output_file: str = "table_analysis.json") -> None:
        """
        Exporta resultados para JSON

        Args:
            output_file: Caminho do arquivo de saída

        Raises:
            ExportError: Se houver erro ao exportar
        """
        if not self.tables:
            raise ExportError("Nenhuma tabela para exportar")

        try:
            results = {
                'tables': {
                    name: {
                        **asdict(info),
                        'columns': [asdict(col) for col in info.columns],
                        'indexes': [asdict(idx) for idx in info.indexes],
                        'foreign_keys': [asdict(fk) for fk in info.foreign_keys]
                    }
                    for name, info in self.tables.items()
                },
                'hierarchy': self.get_table_hierarchy(),
                'statistics': {
                    'total_tables': len(self.tables),
                    'avg_complexity': sum(t.complexity_score for t in self.tables.values()) / len(self.tables) if self.tables else 0,
                    'total_foreign_keys': sum(len(t.foreign_keys) for t in self.tables.values()),
                    'total_indexes': sum(len(t.indexes) for t in self.tables.values())
                }
            }

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)

            logger.info(f"Resultados exportados para {output_file}")
        except Exception as e:
            logger.error(f"Erro ao exportar resultados: {e}")
            raise ExportError(f"Erro ao exportar resultados para {output_file}: {e}")

    def visualize_relationships(self, output_file: str = "relationship_graph.png") -> None:
        """
        Visualiza grafo de relacionamentos

        Args:
            output_file: Caminho do arquivo de saída

        Raises:
            ExportError: Se houver erro ao exportar
        """
        if not self.relationship_graph.nodes():
            raise ExportError("Grafo de relacionamentos vazio")

        try:
            plt.figure(figsize=TableAnalysisConfig.GRAPH_FIGSIZE)

            # Layout hierárquico
            pos = nx.spring_layout(self.relationship_graph, k=2, iterations=50)

            # Cores por complexidade
            colors = []
            for node in self.relationship_graph.nodes():
                if node in self.tables:
                    complexity = self.tables[node].complexity_score
                    colors.append(complexity)
                else:
                    colors.append(0)

            nx.draw(
                self.relationship_graph,
                pos,
                node_color=colors,
                node_size=TableAnalysisConfig.GRAPH_NODE_SIZE,
                cmap=plt.cm.viridis,
                with_labels=True,
                font_size=TableAnalysisConfig.GRAPH_FONT_SIZE,
                arrows=True,
                edge_color='gray',
                alpha=0.7
            )

            plt.title("Grafo de Relacionamentos de Tabelas (Foreign Keys)", fontsize=16)
            plt.savefig(output_file, dpi=TableAnalysisConfig.GRAPH_DPI, bbox_inches='tight')
            plt.close()

            logger.info(f"Grafo exportado para {output_file}")
        except Exception as e:
            logger.error(f"Erro ao exportar grafo: {e}")
            raise ExportError(f"Erro ao exportar grafo para {output_file}: {e}")

    def export_mermaid_diagram(self, output_file: str = "table_diagram.md", max_nodes: int = 50) -> None:
        """
        Exporta diagrama Mermaid ER (Entity Relationship)

        Args:
            output_file: Caminho do arquivo de saída
            max_nodes: Número máximo de nós no diagrama

        Raises:
            ExportError: Se houver erro ao exportar
        """
        if not self.relationship_graph.nodes():
            raise ExportError("Grafo de relacionamentos vazio")

        try:
            nodes = list(self.relationship_graph.nodes())[:max_nodes]

            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("```mermaid\nerDiagram\n")

                # Adiciona entidades (tabelas)
                for node in nodes:
                    if node in self.tables:
                        info = self.tables[node]
                        # Lista colunas principais (PK e algumas importantes)
                        pk_cols = info.primary_key_columns[:3]
                        other_cols = [col.name for col in info.columns[:5] if col.name not in pk_cols]
                        all_cols = pk_cols + other_cols

                        f.write(f'    {self._sanitize_mermaid_name(node)} {{\n')
                        for col in all_cols[:8]:  # Limita a 8 colunas por tabela
                            col_info = next((c for c in info.columns if c.name == col), None)
                            if col_info:
                                col_type = col_info.data_type.split('(')[0]  # Remove tamanho
                                pk_marker = " PK" if col_info.is_primary_key else ""
                                fk_marker = " FK" if col_info.is_foreign_key else ""
                                f.write(f'        {col_info.name} {col_type}{pk_marker}{fk_marker}\n')
                        f.write('    }\n')

                # Adiciona relacionamentos (foreign keys)
                for edge in self.relationship_graph.edges():
                    if edge[0] in nodes and edge[1] in nodes:
                        source = self._sanitize_mermaid_name(edge[0])
                        target = self._sanitize_mermaid_name(edge[1])
                        edge_data = self.relationship_graph.get_edge_data(edge[0], edge[1])
                        rel_type = edge_data.get('relationship_type', 'references')
                        f.write(f'    {source} ||--o{{ {target} : "{rel_type}"\n')

                f.write("```\n")

            logger.info(f"Diagrama Mermaid ER exportado para {output_file}")
        except Exception as e:
            logger.error(f"Erro ao exportar diagrama Mermaid: {e}")
            raise ExportError(f"Erro ao exportar diagrama Mermaid: {e}")

    def export_mermaid_hierarchy(self, output_file: str = "table_hierarchy.md") -> None:
        """
        Exporta hierarquia Mermaid organizada por níveis de dependência FK

        Args:
            output_file: Caminho do arquivo de saída

        Raises:
            ExportError: Se houver erro ao exportar
        """
        if not self.tables:
            raise ExportError("Nenhuma tabela para exportar")

        try:
            hierarchy = self.get_table_hierarchy()

            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("```mermaid\ngraph TD\n")

                # Agrupa por nível
                for level in sorted(hierarchy.keys()):
                    tables_in_level = hierarchy[level]
                    f.write(f'    subgraph Level{level}["Nível {level}"]\n')
                    for table_name in tables_in_level:
                        if table_name in self.tables:
                            info = self.tables[table_name]
                            complexity_class = "high" if info.complexity_score >= 8 else \
                                             "medium" if info.complexity_score >= 5 else "low"
                            label = f"{table_name}\\n[Complex: {info.complexity_score}, FKs: {len(info.foreign_keys)}]"
                            node_id = self._sanitize_mermaid_name(table_name)
                            f.write(f'        {node_id}["{label}"]:::{complexity_class}\n')
                    f.write('    end\n')

                # Adiciona arestas entre níveis
                for edge in self.relationship_graph.edges():
                    source = self._sanitize_mermaid_name(edge[0])
                    target = self._sanitize_mermaid_name(edge[1])
                    f.write(f"    {source} --> {target}\n")

                # Define classes de estilo
                f.write("""
    classDef high fill:#ff6b6b,stroke:#c92a2a,color:#fff
    classDef medium fill:#ffd93d,stroke:#f59f00,color:#000
    classDef low fill:#51cf66,stroke:#2b8a3e,color:#000
```\n""")

            logger.info(f"Hierarquia Mermaid exportada para {output_file}")
        except Exception as e:
            logger.error(f"Erro ao exportar hierarquia Mermaid: {e}")
            raise ExportError(f"Erro ao exportar hierarquia Mermaid: {e}")

    def _sanitize_mermaid_name(self, name: str) -> str:
        """Sanitiza nome para uso em diagramas Mermaid"""
        return name.replace(".", "_").replace("-", "_").replace(" ", "_")

