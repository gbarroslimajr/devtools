"""
Vector Tools for Semantic Search
Tools for semantic search in the knowledge graph using vector embeddings
"""

import json
import logging
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# Global dependency (set by init_tools)
_vector_kg = None


class SemanticSearchInput(BaseModel):
    """Input schema for semantic_search_tables tool"""
    query: str = Field(
        description="Query em linguagem natural para buscar tabelas semanticamente relacionadas"
    )
    top_k: Optional[int] = Field(
        default=5,
        description="Número de resultados a retornar (padrão: 5, máximo: 20)"
    )
    similarity_threshold: Optional[float] = Field(
        default=0.0,
        description="Threshold mínimo de similaridade (0.0 a 1.0, padrão: 0.0)"
    )


class SemanticSearchProceduresInput(BaseModel):
    """Input schema for semantic_search_procedures tool"""
    query: str = Field(
        description="Query em linguagem natural para buscar procedures semanticamente relacionadas"
    )
    top_k: Optional[int] = Field(
        default=5,
        description="Número de resultados a retornar (padrão: 5, máximo: 20)"
    )
    similarity_threshold: Optional[float] = Field(
        default=0.0,
        description="Threshold mínimo de similaridade (0.0 a 1.0, padrão: 0.0)"
    )


class HybridSearchInput(BaseModel):
    """Input schema for hybrid_search tool"""
    query: str = Field(
        description="Query em linguagem natural para busca híbrida (vetorial + estrutural)"
    )
    top_k: Optional[int] = Field(
        default=5,
        description="Número de resultados a retornar (padrão: 5, máximo: 20)"
    )
    node_type: Optional[str] = Field(
        default=None,
        description="Filtrar por tipo de nó: 'table' ou 'procedure' (opcional)"
    )


@tool(args_schema=SemanticSearchInput)
def semantic_search_tables(
    query: str,
    top_k: Optional[int] = 5,
    similarity_threshold: Optional[float] = 0.0
) -> str:
    """Busca semântica de tabelas no knowledge graph.

    Use esta tool quando precisar:
    - Encontrar tabelas por significado/purpose, não apenas por nome
    - Descobrir tabelas relacionadas semanticamente
    - Buscar tabelas que lidam com um conceito específico

    Esta tool usa embeddings para encontrar tabelas que são semanticamente
    similares à query, mesmo que não contenham as palavras exatas.

    Args:
        query: Query em linguagem natural (ex: "tabelas de pagamentos")
        top_k: Número de resultados (padrão: 5, máximo: 20)
        similarity_threshold: Threshold mínimo de similaridade (0.0 a 1.0)

    Returns:
        JSON com tabelas encontradas, ordenadas por similaridade

    Examples:
        - "Quais tabelas lidam com agendamentos?"
        - "Tabelas relacionadas a pacientes"
        - "Onde são armazenados os pagamentos?"
    """
    try:
        if not _vector_kg:
            return json.dumps({
                "success": False,
                "error": "Vector knowledge graph não está disponível. "
                        "Verifique se a busca semântica está habilitada."
            })

        # Validar top_k
        if top_k and top_k > 20:
            top_k = 20
        elif not top_k:
            top_k = 5

        # Validar threshold
        if similarity_threshold is None:
            similarity_threshold = 0.0
        elif similarity_threshold < 0.0 or similarity_threshold > 1.0:
            similarity_threshold = 0.0

        # Buscar tabelas
        results = _vector_kg.semantic_search(
            query=query,
            top_k=top_k,
            node_type="table",
            similarity_threshold=similarity_threshold
        )

        # Formatar resultados
        formatted_results = []
        for result in results:
            context = result.context
            formatted_results.append({
                "table_name": context.get("name", result.node_id),
                "schema": context.get("schema", ""),
                "full_name": result.node_id,
                "similarity": round(result.similarity, 4),
                "business_purpose": context.get("business_purpose", ""),
                "columns_count": len(context.get("columns", [])),
                "complexity_score": context.get("complexity_score", 0)
            })

        return json.dumps({
            "success": True,
            "query": query,
            "results_count": len(formatted_results),
            "results": formatted_results
        }, indent=2, ensure_ascii=False)

    except Exception as e:
        logger.exception(f"Erro na busca semântica de tabelas: {e}")
        return json.dumps({
            "success": False,
            "error": f"Erro na busca semântica: {str(e)}"
        })


@tool(args_schema=SemanticSearchProceduresInput)
def semantic_search_procedures(
    query: str,
    top_k: Optional[int] = 5,
    similarity_threshold: Optional[float] = 0.0
) -> str:
    """Busca semântica de procedures no knowledge graph.

    Use esta tool quando precisar:
    - Encontrar procedures por funcionalidade, não apenas por nome
    - Descobrir procedures que fazem algo similar
    - Buscar procedures relacionadas a um conceito específico

    Esta tool usa embeddings para encontrar procedures que são semanticamente
    similares à query, mesmo que não contenham as palavras exatas.

    Args:
        query: Query em linguagem natural (ex: "procedures que processam pagamentos")
        top_k: Número de resultados (padrão: 5, máximo: 20)
        similarity_threshold: Threshold mínimo de similaridade (0.0 a 1.0)

    Returns:
        JSON com procedures encontradas, ordenadas por similaridade

    Examples:
        - "Procedures que validam dados"
        - "Como processar pedidos?"
        - "Procedures relacionadas a cálculos financeiros"
    """
    try:
        if not _vector_kg:
            return json.dumps({
                "success": False,
                "error": "Vector knowledge graph não está disponível. "
                        "Verifique se a busca semântica está habilitada."
            })

        # Validar top_k
        if top_k and top_k > 20:
            top_k = 20
        elif not top_k:
            top_k = 5

        # Validar threshold
        if similarity_threshold is None:
            similarity_threshold = 0.0
        elif similarity_threshold < 0.0 or similarity_threshold > 1.0:
            similarity_threshold = 0.0

        # Buscar procedures
        results = _vector_kg.semantic_search(
            query=query,
            top_k=top_k,
            node_type="procedure",
            similarity_threshold=similarity_threshold
        )

        # Formatar resultados
        formatted_results = []
        for result in results:
            context = result.context
            formatted_results.append({
                "procedure_name": context.get("name", result.node_id),
                "schema": context.get("schema", ""),
                "full_name": result.node_id,
                "similarity": round(result.similarity, 4),
                "business_logic": context.get("business_logic", "")[:200] + "..." if len(context.get("business_logic", "")) > 200 else context.get("business_logic", ""),
                "parameters_count": len(context.get("parameters", [])),
                "complexity_score": context.get("complexity_score", 0)
            })

        return json.dumps({
            "success": True,
            "query": query,
            "results_count": len(formatted_results),
            "results": formatted_results
        }, indent=2, ensure_ascii=False)

    except Exception as e:
        logger.exception(f"Erro na busca semântica de procedures: {e}")
        return json.dumps({
            "success": False,
            "error": f"Erro na busca semântica: {str(e)}"
        })


@tool(args_schema=HybridSearchInput)
def hybrid_search(
    query: str,
    top_k: Optional[int] = 5,
    node_type: Optional[str] = None
) -> str:
    """Busca híbrida: combina busca semântica (vetorial) + relacionamentos estruturais do grafo.

    Use esta tool quando precisar:
    - Busca semântica com contexto expandido de relacionamentos
    - Encontrar nós relacionados e seus relacionamentos no grafo
    - Análise de impacto mais completa

    Esta tool combina:
    1. Busca semântica usando embeddings
    2. Expansão com relacionamentos do grafo estrutural

    Args:
        query: Query em linguagem natural
        top_k: Número de resultados (padrão: 5, máximo: 20)
        node_type: Filtrar por tipo: "table" ou "procedure" (opcional)

    Returns:
        JSON com resultados incluindo relacionamentos do grafo

    Examples:
        - "Sistema de agendamentos e suas dependências"
        - "Tabelas de pagamento e relacionamentos"
        - "Procedures de validação e quem as chama"
    """
    try:
        if not _vector_kg:
            return json.dumps({
                "success": False,
                "error": "Vector knowledge graph não está disponível. "
                        "Verifique se a busca semântica está habilitada."
            })

        # Validar top_k
        if top_k and top_k > 20:
            top_k = 20
        elif not top_k:
            top_k = 5

        # Validar node_type
        if node_type and node_type not in ["table", "procedure"]:
            node_type = None

        # Busca híbrida
        results = _vector_kg.hybrid_search(
            query=query,
            top_k=top_k,
            node_type=node_type
        )

        # Formatar resultados
        formatted_results = []
        for result in results:
            context = result.context
            relationships = context.get("relationships", {})

            formatted_result = {
                "node_id": result.node_id,
                "name": context.get("name", result.node_id),
                "schema": context.get("schema", ""),
                "node_type": context.get("node_type", "unknown"),
                "similarity": round(result.similarity, 4),
                "relationships": {}
            }

            # Adicionar informações específicas do tipo
            if context.get("node_type") == "table":
                formatted_result["business_purpose"] = context.get("business_purpose", "")
                formatted_result["columns_count"] = len(context.get("columns", []))
            elif context.get("node_type") == "procedure":
                formatted_result["business_logic"] = context.get("business_logic", "")[:200] + "..." if len(context.get("business_logic", "")) > 200 else context.get("business_logic", "")
                formatted_result["parameters_count"] = len(context.get("parameters", []))

            # Adicionar relacionamentos
            for rel_type, targets in relationships.items():
                formatted_result["relationships"][rel_type] = targets[:10]  # Limitar a 10 por tipo

            formatted_results.append(formatted_result)

        return json.dumps({
            "success": True,
            "query": query,
            "results_count": len(formatted_results),
            "results": formatted_results
        }, indent=2, ensure_ascii=False)

    except Exception as e:
        logger.exception(f"Erro na busca híbrida: {e}")
        return json.dumps({
            "success": False,
            "error": f"Erro na busca híbrida: {str(e)}"
        })

