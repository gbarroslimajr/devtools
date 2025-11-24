"""
Vector Knowledge Graph for Semantic Search
Production-ready RAG implementation with hybrid search capabilities
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Any
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

from app.graph.knowledge_graph import CodeKnowledgeGraph

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Resultado de busca semântica"""
    node_id: str
    similarity: float
    metadata: Dict[str, Any]
    context: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário"""
        return {
            "node_id": self.node_id,
            "similarity": self.similarity,
            "metadata": self.metadata,
            "context": self.context
        }


@dataclass
class NodeDocument:
    """Documento indexado no vector store"""
    node_id: str
    text: str
    node_type: str
    schema: str
    name: str


class VectorKnowledgeGraph:
    """
    Vector Knowledge Graph com busca semântica

    Implementa RAG pipeline completo:
    - Embeddings usando sentence-transformers
    - Vector store usando ChromaDB
    - Hybrid search (vetorial + estrutural)
    - Batch processing para performance
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
        Inicializa Vector Knowledge Graph

        Args:
            knowledge_graph: Instância de CodeKnowledgeGraph
            embedding_backend: Backend de embedding ("sentence-transformers")
            embedding_model: Nome do modelo (default: all-MiniLM-L6-v2)
            vector_store_path: Caminho para vector store (default: ./cache/vector_store)
            batch_size: Tamanho do batch para processamento de embeddings
            device: Dispositivo para embeddings ("cpu" ou "cuda")

        Raises:
            ImportError: Se dependências não estiverem instaladas
            ValueError: Se backend não for suportado
        """
        self.kg = knowledge_graph
        self.embedding_backend = embedding_backend
        self.batch_size = batch_size

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
            cache_dir = Path(self.kg.cache_path).parent
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

            # Obter ou criar collection
            collection_name = "knowledge_graph"
            try:
                self.collection = self.chroma_client.get_collection(collection_name)
                logger.info(f"Vector store carregado: {self.collection.count()} documentos")
            except Exception:
                # Collection não existe, criar
                self.collection = self.chroma_client.create_collection(
                    name=collection_name,
                    metadata={"description": "CodeGraphAI Knowledge Graph Vector Store"}
                )
                logger.info("Nova collection criada no vector store")

            # Verificar se precisa indexar
            if self.collection.count() == 0:
                logger.info("Vector store vazio, iniciando indexação...")
                self._index_graph()
            else:
                # Verificar se precisa re-indexar (comparar com metadata do KG)
                kg_updated = self.kg.metadata.get("updated_at")
                if kg_updated:
                    # Verificar metadata do vector store
                    collection_metadata = self.collection.metadata or {}
                    last_indexed = collection_metadata.get("last_indexed")

                    if not last_indexed or last_indexed < kg_updated:
                        logger.info("Knowledge graph atualizado, re-indexando...")
                        self._index_graph()
                    else:
                        logger.info("Vector store está atualizado")

        except Exception as e:
            logger.error(f"Erro ao inicializar vector store: {e}")
            raise

    def _create_document(self, node_id: str, node_data: Dict[str, Any]) -> NodeDocument:
        """
        Cria documento textual rico para embedding

        Args:
            node_id: ID do nó no grafo
            node_data: Dados do nó

        Returns:
            NodeDocument com texto formatado
        """
        node_type = node_data.get("node_type", "unknown")
        name = node_data.get("name", node_id)
        schema = node_data.get("schema", "")

        text_parts = [f"{node_type.capitalize()}: {name}"]

        if schema:
            text_parts.append(f"Schema: {schema}")

        # Adicionar business_purpose se disponível
        business_purpose = node_data.get("business_purpose", "")
        if business_purpose:
            text_parts.append(f"Propósito: {business_purpose}")

        # Para tabelas: adicionar colunas principais
        if node_type == "table":
            columns = node_data.get("columns", [])
            if columns:
                col_names = [col.get("name", "") for col in columns[:15]]  # Primeiras 15
                text_parts.append(f"Colunas principais: {', '.join(col_names)}")

            # Adicionar relacionamentos
            foreign_keys = node_data.get("foreign_keys", [])
            if foreign_keys:
                fk_tables = [fk.get("referenced_table", "") for fk in foreign_keys[:5]]
                text_parts.append(f"Relaciona com: {', '.join(fk_tables)}")

        # Para procedures: adicionar lógica de negócio
        elif node_type == "procedure":
            business_logic = node_data.get("business_logic", "")
            if business_logic:
                # Limitar tamanho
                logic_preview = business_logic[:300] + "..." if len(business_logic) > 300 else business_logic
                text_parts.append(f"Lógica: {logic_preview}")

            parameters = node_data.get("parameters", [])
            if parameters:
                param_names = [p.get("name", "") for p in parameters[:10]]
                text_parts.append(f"Parâmetros: {', '.join(param_names)}")

        # Adicionar complexidade
        complexity = node_data.get("complexity_score", 0)
        if complexity:
            text_parts.append(f"Complexidade: {complexity}")

        text = "\n".join(text_parts)

        return NodeDocument(
            node_id=node_id,
            text=text,
            node_type=node_type,
            schema=schema,
            name=name
        )

    def _index_graph(self) -> None:
        """Indexa todos os nós do grafo no vector store"""
        try:
            # Coletar todos os nós
            nodes_to_index = []
            for node_id, node_data in self.kg.graph.nodes(data=True):
                nodes_to_index.append((node_id, node_data))

            if not nodes_to_index:
                logger.warning("Nenhum nó encontrado no knowledge graph para indexar")
                return

            logger.info(f"Indexando {len(nodes_to_index)} nós...")

            # Processar em batches
            documents = []
            embeddings = []
            ids = []
            metadatas = []

            for i in tqdm(range(0, len(nodes_to_index), self.batch_size), desc="Indexando"):
                batch = nodes_to_index[i:i + self.batch_size]

                batch_docs = []
                batch_ids = []
                batch_metadatas = []

                for node_id, node_data in batch:
                    doc = self._create_document(node_id, node_data)
                    batch_docs.append(doc.text)
                    batch_ids.append(node_id)
                    batch_metadatas.append({
                        "type": doc.node_type,
                        "schema": doc.schema,
                        "name": doc.name
                    })

                # Gerar embeddings em batch
                batch_embeddings = self.embedder.encode(
                    batch_docs,
                    batch_size=len(batch_docs),
                    show_progress_bar=False,
                    convert_to_numpy=True
                ).tolist()

                documents.extend(batch_docs)
                embeddings.extend(batch_embeddings)
                ids.extend(batch_ids)
                metadatas.extend(batch_metadatas)

            # Adicionar ao vector store
            self.collection.add(
                embeddings=embeddings,
                documents=documents,
                ids=ids,
                metadatas=metadatas
            )

            # Atualizar metadata da collection
            kg_updated = self.kg.metadata.get("updated_at", "")
            self.collection.modify(
                metadata={"last_indexed": kg_updated}
            )

            logger.info(f"Indexação concluída: {len(ids)} nós indexados")

        except Exception as e:
            logger.error(f"Erro ao indexar grafo: {e}")
            raise

    def encode(self, text: str) -> List[float]:
        """
        Gera embedding de um texto

        Args:
            text: Texto para embedar

        Returns:
            Lista de floats representando o embedding
        """
        if self.embedding_backend == "sentence-transformers":
            embedding = self.embedder.encode(
                text,
                convert_to_numpy=True,
                show_progress_bar=False
            )
            return embedding.tolist()
        else:
            raise ValueError(f"Backend não suportado: {self.embedding_backend}")

    def semantic_search(
        self,
        query: str,
        top_k: int = 5,
        node_type: Optional[str] = None,
        similarity_threshold: float = 0.0
    ) -> List[SearchResult]:
        """
        Busca semântica no knowledge graph

        Args:
            query: Query em linguagem natural
            top_k: Número de resultados a retornar
            node_type: Filtrar por tipo ("table" ou "procedure")
            similarity_threshold: Threshold mínimo de similaridade (0.0 a 1.0)

        Returns:
            Lista de SearchResult ordenada por similaridade
        """
        try:
            # Gerar embedding da query
            query_embedding = self.encode(query)

            # Construir filtros
            where = {}
            if node_type:
                where["type"] = node_type

            # Buscar no vector store
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k * 2,  # Buscar mais para filtrar depois
                where=where if where else None
            )

            # Processar resultados
            search_results = []
            if results['ids'] and len(results['ids'][0]) > 0:
                for i in range(len(results['ids'][0])):
                    node_id = results['ids'][0][i]
                    metadata = results['metadatas'][0][i]
                    distance = results['distances'][0][i] if 'distances' in results else None

                    # Converter distância para similaridade (ChromaDB usa distância)
                    similarity = 1.0 - distance if distance is not None else 1.0

                    # Filtrar por threshold
                    if similarity < similarity_threshold:
                        continue

                    # Buscar contexto completo do grafo
                    node_data = self.kg.graph.nodes.get(node_id, {})

                    search_results.append(SearchResult(
                        node_id=node_id,
                        similarity=similarity,
                        metadata=metadata,
                        context=node_data
                    ))

                # Ordenar por similaridade (maior primeiro)
                search_results.sort(key=lambda x: x.similarity, reverse=True)

                # Limitar a top_k
                search_results = search_results[:top_k]

            return search_results

        except Exception as e:
            logger.error(f"Erro na busca semântica: {e}")
            return []

    def hybrid_search(
        self,
        query: str,
        top_k: int = 5,
        node_type: Optional[str] = None
    ) -> List[SearchResult]:
        """
        Busca híbrida: combina busca vetorial + estrutural

        Args:
            query: Query em linguagem natural
            top_k: Número de resultados a retornar
            node_type: Filtrar por tipo

        Returns:
            Lista de SearchResult com contexto expandido do grafo
        """
        # Busca semântica inicial
        semantic_results = self.semantic_search(query, top_k=top_k * 2, node_type=node_type)

        # Expandir com relacionamentos do grafo
        expanded_results = []
        seen_nodes = set()

        for result in semantic_results:
            if result.node_id in seen_nodes:
                continue

            seen_nodes.add(result.node_id)

            # Buscar relacionamentos no grafo
            node_id = result.node_id
            node_data = result.context

            # Adicionar informações de relacionamentos ao contexto
            relationships = {}

            # Outgoing edges
            for _, target, edge_data in self.kg.graph.out_edges(node_id, data=True):
                rel_type = edge_data.get("edge_type", "unknown")
                if rel_type not in relationships:
                    relationships[rel_type] = []
                relationships[rel_type].append(target)

            # Incoming edges
            for source, _, edge_data in self.kg.graph.in_edges(node_id, data=True):
                rel_type = edge_data.get("edge_type", "unknown")
                if rel_type not in relationships:
                    relationships[rel_type] = []
                relationships[rel_type].append(source)

            # Atualizar contexto com relacionamentos
            expanded_context = result.context.copy()
            expanded_context["relationships"] = relationships

            expanded_result = SearchResult(
                node_id=result.node_id,
                similarity=result.similarity,
                metadata=result.metadata,
                context=expanded_context
            )

            expanded_results.append(expanded_result)

            if len(expanded_results) >= top_k:
                break

        return expanded_results

    def get_statistics(self) -> Dict[str, Any]:
        """Retorna estatísticas do vector store"""
        try:
            count = self.collection.count()
            return {
                "vector_store_path": str(self.vector_store_path),
                "indexed_nodes": count,
                "embedding_backend": self.embedding_backend,
                "device": self.device,
                "batch_size": self.batch_size
            }
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas: {e}")
            return {}

