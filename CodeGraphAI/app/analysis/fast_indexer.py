"""
Fast Indexer for Procedures
Indexes procedures quickly without LLM using static analysis and embeddings
"""

import re
import logging
import time
from typing import Dict, List, Set, Optional, Any, Tuple
from pathlib import Path
from datetime import datetime
from collections import defaultdict

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

from tqdm import tqdm

from app.analysis.static_analyzer import StaticCodeAnalyzer
from app.io.file_loader import FileLoader
from app.graph.knowledge_graph import CodeKnowledgeGraph
from analyzer import AnalysisConfig

logger = logging.getLogger(__name__)


class FastIndexer:
    """
    Indexação rápida de procedures sem LLM

    Pipeline:
    - Carrega arquivos via FileLoader
    - Extrai estrutura via StaticCodeAnalyzer
    - Calcula complexidade heurística
    - Cria embeddings do código-fonte
    - Indexa no ChromaDB
    - Popula knowledge graph
    """

    def __init__(
        self,
        knowledge_graph: CodeKnowledgeGraph,
        embedding_backend: str = "sentence-transformers",
        embedding_model: Optional[str] = None,
        vector_store_path: Optional[Path] = None,
        batch_size: int = 32,
        device: Optional[str] = None
    ):
        """
        Inicializa FastIndexer

        Args:
            knowledge_graph: Instância de CodeKnowledgeGraph
            embedding_backend: Backend de embedding (padrão: sentence-transformers)
            embedding_model: Nome do modelo (padrão: all-MiniLM-L6-v2)
            vector_store_path: Caminho para vector store (padrão: ./cache/vector_store)
            batch_size: Tamanho do batch para processamento de embeddings
            device: Dispositivo para embeddings ("cpu" ou "cuda")

        Raises:
            ImportError: Se dependências não estiverem instaladas
            ValueError: Se backend não for suportado
        """
        self.knowledge_graph = knowledge_graph
        self.embedding_backend = embedding_backend
        self.batch_size = batch_size
        self.static_analyzer = StaticCodeAnalyzer()

        # Determinar device
        if device is None:
            try:
                import torch
                self.device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                self.device = "cpu"
        else:
            self.device = device

        # Configurar caminho do vector store
        if vector_store_path is None:
            cache_dir = Path(self.knowledge_graph.cache_path).parent
            self.vector_store_path = cache_dir / "vector_store"
        else:
            self.vector_store_path = Path(vector_store_path)

        self.vector_store_path.mkdir(parents=True, exist_ok=True)

        # Inicializar embedding model
        if embedding_backend == "sentence-transformers":
            if not SENTENCE_TRANSFORMERS_AVAILABLE:
                raise ImportError(
                    "sentence-transformers não está instalado. "
                    "Instale com: pip install sentence-transformers>=2.2.0"
                )

            if embedding_model is None:
                embedding_model = "sentence-transformers/all-MiniLM-L6-v2"

            logger.info(f"Carregando modelo de embedding: {embedding_model} (device: {self.device})")
            self.embedder = SentenceTransformer(embedding_model, device=self.device)
            logger.info("Modelo de embedding carregado com sucesso")
        else:
            raise ValueError(f"Backend não suportado: {embedding_backend}")

        # Inicializar vector store
        if not CHROMADB_AVAILABLE:
            raise ImportError(
                "chromadb não está instalado. "
                "Instale com: pip install chromadb>=0.4.0"
            )

        self._initialize_vector_store()

    def _initialize_vector_store(self) -> None:
        """Inicializa ou carrega vector store do ChromaDB"""
        try:
            # Criar cliente ChromaDB com persistência
            self.chroma_client = chromadb.PersistentClient(
                path=str(self.vector_store_path),
                settings=Settings(anonymized_telemetry=False)
            )

            # Obter ou criar collection para código-fonte
            collection_name = "procedure_code_index"
            try:
                self.collection = self.chroma_client.get_collection(collection_name)
                logger.info(f"Vector store carregado: {self.collection.count()} documentos")
            except Exception:
                # Collection não existe, criar
                self.collection = self.chroma_client.create_collection(
                    name=collection_name,
                    metadata={"description": "CodeGraphAI Procedure Code Index"}
                )
                logger.info("Nova collection criada no vector store")

        except Exception as e:
            logger.error(f"Erro ao inicializar vector store: {e}")
            raise

    def _calculate_complexity_heuristic(self, code: str) -> int:
        """
        Cálculo heurístico de complexidade (reutiliza lógica de LLMAnalyzer)

        Args:
            code: Código-fonte da procedure

        Returns:
            Score de complexidade entre 1 e 10
        """
        score = 1

        lines = len(code.split('\n'))
        score += min(lines // AnalysisConfig.COMPLEXITY_LINES_THRESHOLD,
                    AnalysisConfig.COMPLEXITY_LINES_MAX_BONUS)

        score += len(re.findall(r'(?i)\bIF\b', code)) * AnalysisConfig.COMPLEXITY_IF_WEIGHT
        score += len(re.findall(r'(?i)\bLOOP\b', code)) * AnalysisConfig.COMPLEXITY_LOOP_WEIGHT
        score += len(re.findall(r'(?i)\bCURSOR\b', code)) * AnalysisConfig.COMPLEXITY_CURSOR_WEIGHT
        score += len(re.findall(r'(?i)\bEXCEPTION\b', code)) * AnalysisConfig.COMPLEXITY_EXCEPTION_WEIGHT

        return min(int(score), AnalysisConfig.COMPLEXITY_MAX_SCORE)

    def _create_code_document(
        self,
        proc_name: str,
        code: str,
        analysis_result: Any,
        complexity: int,
        schema: str = "UNKNOWN"
    ) -> str:
        """
        Cria documento textual rico para embedding

        Args:
            proc_name: Nome da procedure
            code: Código-fonte
            analysis_result: Resultado da análise estática
            complexity: Score de complexidade heurística
            schema: Schema da procedure

        Returns:
            Texto formatado para embedding
        """
        text_parts = [f"Procedure: {proc_name}"]

        if schema and schema != "UNKNOWN":
            text_parts.append(f"Schema: {schema}")

        # Parâmetros
        if analysis_result.parameters:
            param_names = [p.get('name', '') for p in analysis_result.parameters[:10]]
            if param_names:
                text_parts.append(f"Parameters: {', '.join(param_names)}")

        # Dependências
        if analysis_result.procedures:
            proc_list = list(analysis_result.procedures)[:15]
            text_parts.append(f"Dependencies: {', '.join(proc_list)}")

        if analysis_result.tables:
            table_list = list(analysis_result.tables)[:15]
            text_parts.append(f"Tables: {', '.join(table_list)}")

        # Complexidade
        text_parts.append(f"Complexity: {complexity}/10")

        # Código-fonte (truncado se necessário)
        max_code_length = 2000
        if len(code) > max_code_length:
            code_preview = code[:max_code_length] + "..."
        else:
            code_preview = code

        text_parts.append(f"\nCode:\n{code_preview}")

        return "\n".join(text_parts)

    def _index_in_chromadb(
        self,
        documents: List[str],
        ids: List[str],
        metadatas: List[Dict[str, Any]],
        embeddings: List[List[float]]
    ) -> None:
        """
        Indexa documentos no ChromaDB

        Args:
            documents: Lista de textos dos documentos
            ids: Lista de IDs (nomes das procedures)
            metadatas: Lista de metadados
            embeddings: Lista de embeddings
        """
        try:
            # Limpar documentos existentes com os mesmos IDs (para re-indexação)
            existing_ids = self.collection.get(ids=ids)['ids']
            if existing_ids:
                self.collection.delete(ids=existing_ids)

            # Adicionar novos documentos
            self.collection.add(
                embeddings=embeddings,
                documents=documents,
                ids=ids,
                metadatas=metadatas
            )

            logger.debug(f"Indexados {len(ids)} documentos no ChromaDB")

        except Exception as e:
            logger.error(f"Erro ao indexar no ChromaDB: {e}")
            raise

    def _populate_knowledge_graph(
        self,
        proc_name: str,
        schema: str,
        source_code: str,
        analysis_result: Any,
        complexity: int
    ) -> None:
        """
        Popula knowledge graph com dados estruturais

        Args:
            proc_name: Nome da procedure
            schema: Schema da procedure
            source_code: Código-fonte
            analysis_result: Resultado da análise estática
            complexity: Score de complexidade
        """
        try:
            proc_info = {
                "name": proc_name,
                "schema": schema,
                "source_code": source_code,
                "parameters": analysis_result.parameters,
                "called_procedures": list(analysis_result.procedures),
                "called_tables": list(analysis_result.tables),
                "business_logic": "",  # Vazio, será preenchido depois com LLM
                "complexity_score": complexity
            }

            self.knowledge_graph.add_procedure(proc_info)
            logger.debug(f"Procedure {proc_name} adicionada ao knowledge graph")

        except Exception as e:
            logger.error(f"Erro ao popular knowledge graph para {proc_name}: {e}")
            # Continua mesmo se falhar

    def index_from_files(
        self,
        directory_path: str,
        extension: str = "prc",
        show_progress: bool = True
    ) -> Dict[str, Any]:
        """
        Indexa procedures de arquivos sem usar LLM

        Args:
            directory_path: Caminho do diretório com arquivos
            extension: Extensão dos arquivos (padrão: "prc")
            show_progress: Mostrar barra de progresso

        Returns:
            Dict com estatísticas da indexação:
            {
                "indexed_count": int,
                "total_time": float,
                "pending_llm": List[str],
                "vector_store_path": str,
                "statistics": {
                    "procedures_extracted": int,
                    "tables_extracted": int,
                    "avg_complexity": float
                }
            }
        """
        start_time = time.time()

        # 1. Carregar arquivos
        logger.info(f"Carregando arquivos .{extension} de {directory_path}...")
        loader = FileLoader(directory_path, extension)
        procedures = loader.load_procedures()

        if not procedures:
            logger.warning(f"Nenhum arquivo .{extension} encontrado em {directory_path}")
            return {
                "indexed_count": 0,
                "total_time": time.time() - start_time,
                "pending_llm": [],
                "vector_store_path": str(self.vector_store_path),
                "statistics": {
                    "procedures_extracted": 0,
                    "tables_extracted": 0,
                    "avg_complexity": 0.0
                }
            }

        logger.info(f"Encontrados {len(procedures)} procedures para indexar")

        # 2. Análise estática e preparação de documentos
        documents = []
        ids = []
        metadatas = []
        all_procedures = set()
        all_tables = set()
        complexities = []

        iterator = tqdm(procedures.items(), desc="Analisando procedures",
                       total=len(procedures), disable=not show_progress) if show_progress else procedures.items()

        for proc_name, source_code in iterator:
            if show_progress:
                iterator.set_postfix({"current": proc_name[:30]})

            try:
                # Extrair schema do nome
                if '.' in proc_name:
                    schema, name = proc_name.split('.', 1)
                else:
                    schema = "UNKNOWN"
                    name = proc_name

                # Análise estática
                analysis_result = self.static_analyzer.analyze_code(source_code, name)

                # Calcular complexidade heurística
                complexity = self._calculate_complexity_heuristic(source_code)

                # Criar documento para embedding
                doc_text = self._create_code_document(
                    proc_name=name,
                    code=source_code,
                    analysis_result=analysis_result,
                    complexity=complexity,
                    schema=schema
                )

                documents.append(doc_text)
                ids.append(proc_name)
                metadatas.append({
                    "type": "procedure",
                    "name": name,
                    "schema": schema,
                    "complexity_heuristic": complexity,
                    "dependencies_count": len(analysis_result.procedures),
                    "tables_count": len(analysis_result.tables),
                    "code_length": len(source_code),
                    "indexed_at": datetime.now().isoformat(),
                    "llm_enriched": False
                })

                # Coletar estatísticas
                all_procedures.update(analysis_result.procedures)
                all_tables.update(analysis_result.tables)
                complexities.append(complexity)

                # Popular knowledge graph
                self._populate_knowledge_graph(
                    proc_name=name,
                    schema=schema,
                    source_code=source_code,
                    analysis_result=analysis_result,
                    complexity=complexity
                )

            except Exception as e:
                logger.error(f"Erro ao processar {proc_name}: {e}")
                # Continua com outras procedures

        # 3. Gerar embeddings em batch
        logger.info(f"Gerando embeddings para {len(documents)} procedures...")
        embeddings = []
        for i in tqdm(range(0, len(documents), self.batch_size), desc="Gerando embeddings",
                     disable=not show_progress):
            batch = documents[i:i + self.batch_size]
            batch_embeddings = self.embedder.encode(
                batch,
                batch_size=len(batch),
                show_progress_bar=False,
                convert_to_numpy=True
            ).tolist()
            embeddings.extend(batch_embeddings)

        # 4. Indexar no ChromaDB
        logger.info(f"Indexando {len(ids)} procedures no vector store...")
        self._index_in_chromadb(documents, ids, metadatas, embeddings)

        # 5. Salvar knowledge graph
        self.knowledge_graph.save_to_cache()

        # Calcular estatísticas
        total_time = time.time() - start_time
        avg_complexity = sum(complexities) / len(complexities) if complexities else 0.0

        result = {
            "indexed_count": len(ids),
            "total_time": total_time,
            "pending_llm": list(procedures.keys()),  # Todas precisam de enriquecimento LLM
            "vector_store_path": str(self.vector_store_path),
            "statistics": {
                "procedures_extracted": len(all_procedures),
                "tables_extracted": len(all_tables),
                "avg_complexity": round(avg_complexity, 2)
            }
        }

        logger.info(f"Indexação concluída: {len(ids)} procedures em {total_time:.2f}s")
        return result

