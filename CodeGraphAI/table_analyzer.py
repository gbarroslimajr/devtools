"""
Analisador de Tabelas de Banco de Dados usando LLM
Extrai, analisa e mapeia relacionamentos entre tabelas
"""

import json
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import asdict
from collections import defaultdict
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

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

    # Batch Processing e Paralelismo
    DEFAULT_BATCH_SIZE = 5
    DEFAULT_MAX_PARALLEL_WORKERS = 2


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
        port: Optional[int] = None,
        batch_size: Optional[int] = None,
        parallel_workers: Optional[int] = None
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
            batch_size: Tamanho do batch para análise (padrão: 5, None usa config)
            parallel_workers: Número de workers paralelos (padrão: 2, None usa config, 1 desabilita)

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

        # Determina batch_size e parallel_workers
        effective_batch_size = batch_size if batch_size is not None else TableAnalysisConfig.DEFAULT_BATCH_SIZE
        effective_parallel_workers = parallel_workers if parallel_workers is not None else TableAnalysisConfig.DEFAULT_MAX_PARALLEL_WORKERS

        # Se batch_size = 1, usa processamento sequencial (comportamento original)
        if effective_batch_size <= 1:
            self._analyze_sequential(tables_db, show_progress)
        else:
            # Usa batch processing
            self._analyze_with_batch(tables_db, effective_batch_size, effective_parallel_workers, show_progress)

        # Constrói grafo de relacionamentos
        logger.info("Construindo grafo de relacionamentos...")
        self._build_relationship_graph()

        logger.info("Análise concluída!")

    def _analyze_sequential(self, tables_db: Dict[str, TableInfo], show_progress: bool) -> None:
        """
        Analisa tabelas sequencialmente (método original)

        Args:
            tables_db: Dict com tabelas a analisar
            show_progress: Mostrar barra de progresso
        """
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

    def _analyze_with_batch(
        self,
        tables_db: Dict[str, TableInfo],
        batch_size: int,
        parallel_workers: int,
        show_progress: bool
    ) -> None:
        """
        Analisa tabelas usando batch processing com processamento paralelo opcional

        Args:
            tables_db: Dict com tabelas a analisar
            batch_size: Tamanho do batch
            parallel_workers: Número de workers paralelos (1 = sequencial)
            show_progress: Mostrar barra de progresso
        """
        tables_list = list(tables_db.items())
        total_tables = len(tables_list)

        # Agrupa em batches
        batches = [
            tables_list[i:i+batch_size]
            for i in range(0, total_tables, batch_size)
        ]

        logger.info(f"Processando {total_tables} tabelas em {len(batches)} batches (tamanho: {batch_size})")

        if parallel_workers > 1:
            # Processamento paralelo
            self._process_batches_parallel(batches, parallel_workers, show_progress)
        else:
            # Processamento sequencial de batches
            batch_iterator = tqdm(batches, desc="Processando batches",
                                 total=len(batches), disable=not show_progress) if show_progress else batches
            for batch in batch_iterator:
                if show_progress and hasattr(batch_iterator, 'set_postfix'):
                    batch_iterator.set_postfix({"batch": f"{len(batch)} tabelas"})
                self._process_batch(batch)

    def _process_batches_parallel(
        self,
        batches: List[List[Tuple[str, TableInfo]]],
        max_workers: int,
        show_progress: bool
    ) -> None:
        """
        Processa batches em paralelo usando ThreadPoolExecutor

        Args:
            batches: Lista de batches para processar
            max_workers: Número máximo de workers
            show_progress: Mostrar progresso
        """
        total_batches = len(batches)
        logger.info(f"Processando {total_batches} batches em paralelo com {max_workers} workers")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submete todos os batches
            future_to_batch = {
                executor.submit(self._process_batch, batch): batch
                for batch in batches
            }

            # Progress bar para batches paralelos
            if show_progress:
                progress_bar = tqdm(total=total_batches, desc="Processando batches (paralelo)")

            # Processa resultados conforme completam
            completed = 0
            for future in as_completed(future_to_batch):
                batch = future_to_batch[future]
                try:
                    future.result()  # Aguarda conclusão e trata erros
                    completed += 1
                    if show_progress:
                        progress_bar.update(1)
                        progress_bar.set_postfix({"completos": f"{completed}/{total_batches}"})
                except Exception as e:
                    logger.error(f"Erro ao processar batch: {e}")
                    # Continua processando outros batches
                    if show_progress:
                        progress_bar.update(1)

            if show_progress:
                progress_bar.close()

    def _process_batch(self, batch: List[Tuple[str, TableInfo]]) -> None:
        """
        Processa um batch de tabelas

        Args:
            batch: Lista de tuplas (table_name, table_info)
        """
        try:
            # Prepara dados para batch processing
            tables_data = []
            table_names = []

            for table_name, table_info in batch:
                columns_list = [col.name for col in table_info.columns]
                tables_data.append((
                    f"{table_info.schema}.{table_info.name}",
                    table_info.ddl,
                    columns_list
                ))
                table_names.append(table_name)

            # Chama LLM batch
            try:
                purposes = self._analyze_business_purpose_batch(tables_data, table_names)
            except Exception as e:
                logger.warning(f"Erro no batch processing, usando fallback sequencial: {e}")
                # Fallback: processa individualmente
                purposes = {}
                for table_name, table_info in batch:
                    try:
                        columns_list = [col.name for col in table_info.columns]
                        purpose = self._analyze_business_purpose(table_info, columns_list)
                        purposes[table_name] = purpose
                    except Exception as e2:
                        logger.error(f"Erro ao analisar {table_name} (fallback): {e2}")
                        purposes[table_name] = f"Tabela {table_info.name} com {len(table_info.columns)} colunas"

            # Atualiza tabelas com resultados
            for table_name, table_info in batch:
                full_name = f"{table_info.schema}.{table_info.name}"
                if table_name in purposes:
                    table_info.business_purpose = purposes[table_name]
                elif full_name in purposes:
                    table_info.business_purpose = purposes[full_name]
                else:
                    logger.warning(f"Propósito não encontrado para {table_name}, usando fallback")
                    table_info.business_purpose = f"Tabela {table_info.name} com {len(table_info.columns)} colunas"

                # Calcula complexidade
                table_info.complexity_score = self._calculate_complexity(table_info)

                # Adiciona ao dict de tabelas
                self.tables[table_name] = table_info

        except Exception as e:
            logger.error(f"Erro ao processar batch: {e}")
            # Em caso de erro, tenta processar individualmente
            for table_name, table_info in batch:
                try:
                    columns_list = [col.name for col in table_info.columns]
                    table_info.business_purpose = self._analyze_business_purpose(table_info, columns_list)
                    table_info.complexity_score = self._calculate_complexity(table_info)
                    self.tables[table_name] = table_info
                except Exception as e2:
                    logger.error(f"Erro ao analisar {table_name} (fallback individual): {e2}")

    def _analyze_business_purpose_batch(
        self,
        tables_data: List[Tuple[str, str, List[str]]],
        table_names: List[str]
    ) -> Dict[str, str]:
        """
        Usa LLM para entender o propósito de múltiplas tabelas em batch

        Args:
            tables_data: Lista de tuplas (table_name, ddl, columns_list)
            table_names: Lista de nomes originais das tabelas (para mapeamento)

        Returns:
            Dict com table_name -> business_purpose
        """
        try:
            result = self.llm.analyze_table_purpose_batch(tables_data)
            # Mapeia resultados usando nomes originais
            mapped_result = {}
            for i, table_name in enumerate(table_names):
                full_name = tables_data[i][0]  # Nome completo usado no LLM
                if full_name in result:
                    mapped_result[table_name] = result[full_name]
                elif table_name in result:
                    mapped_result[table_name] = result[table_name]
                else:
                    # Tenta encontrar por partes do nome
                    for key, value in result.items():
                        if table_name in key or key in table_name:
                            mapped_result[table_name] = value
                            break
            return mapped_result
        except LLMAnalysisError as e:
            logger.warning(f"Erro na análise LLM batch: {e}")
            raise

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
            # Coletar estatísticas de tokens
            token_stats = None
            token_metrics_list = None
            if hasattr(self.llm, 'get_token_statistics'):
                token_stats = self.llm.get_token_statistics()
            if hasattr(self.llm, 'token_tracker'):
                token_metrics_list = [
                    {
                        'request_id': m.request_id,
                        'operation': m.operation,
                        'tokens_in': m.tokens_in,
                        'tokens_out': m.tokens_out,
                        'tokens_total': m.tokens_total,
                        'timestamp': m.timestamp.isoformat(),
                        'use_toon': m.use_toon
                    }
                    for m in self.llm.token_tracker.get_all_metrics()
                ]

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

            # Adicionar métricas de tokens se disponíveis
            if token_stats or token_metrics_list:
                results['token_metrics'] = {}
                if token_stats:
                    results['token_metrics']['statistics'] = token_stats
                if token_metrics_list:
                    results['token_metrics']['detailed'] = token_metrics_list

                # Adicionar comparação TOON se disponível
                if hasattr(self.llm, 'token_tracker'):
                    toon_comparison = self.llm.token_tracker.get_toon_comparison()
                    if toon_comparison:
                        # Converter para formato serializável
                        serializable_comparison = {}
                        for key, value in toon_comparison.items():
                            if isinstance(value, dict):
                                serializable_comparison[key] = {
                                    k: v.isoformat() if hasattr(v, 'isoformat') else v
                                    for k, v in value.items()
                                }
                            else:
                                serializable_comparison[key] = value
                        results['token_metrics']['toon_comparison'] = serializable_comparison

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

                        # Remove duplicatas mantendo ordem
                        seen = set()
                        unique_cols = []
                        for col in all_cols[:8]:
                            if col not in seen:
                                seen.add(col)
                                unique_cols.append(col)

                        f.write(f'    {self._sanitize_mermaid_name(node)} {{\n')
                        for col in unique_cols:
                            col_info = next((c for c in info.columns if c.name == col), None)
                            if col_info:
                                # Sanitiza tipo de dados: remove tamanho, substitui hífens/espaços
                                col_type = col_info.data_type.split('(')[0].strip()
                                col_type = col_type.replace('-', '_').replace(' ', '_')
                                # Limita tamanho do tipo para evitar problemas
                                if len(col_type) > 30:
                                    col_type = col_type[:30]

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
                            label = self._sanitize_mermaid_label(label)
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

    def _sanitize_mermaid_label(self, text: str) -> str:
        """Sanitiza texto para uso em labels Mermaid"""
        return text.replace('"', "'").replace('[', '(').replace(']', ')')

