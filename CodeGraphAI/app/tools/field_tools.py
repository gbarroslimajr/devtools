"""
Field Analysis Tools
Tools for analyzing specific fields/columns
"""

import json
import logging
from typing import Optional
from pydantic import BaseModel, Field
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# Global dependencies (set by init_tools)
_knowledge_graph = None
_crawler = None


class AnalyzeFieldInput(BaseModel):
    """Input schema for analyze_field tool"""
    field_name: str = Field(
        description="Nome do campo/coluna a ser analisado"
    )
    procedure_name: Optional[str] = Field(
        default=None,
        description="Nome da procedure onde o campo é usado (opcional, ajuda a filtrar resultados)"
    )
    table_name: Optional[str] = Field(
        default=None,
        description="Nome da tabela onde o campo está definido (opcional)"
    )


@tool(args_schema=AnalyzeFieldInput)
def analyze_field(
    field_name: str,
    procedure_name: Optional[str] = None,
    table_name: Optional[str] = None
) -> str:
    """Analisa um campo/coluna específico em detalhes.

    Use esta tool quando precisar:
    - Saber o que um campo faz e seu propósito
    - Ver onde ele é usado (procedures que o leem/escrevem)
    - Ver de onde ele vem (tabela de origem)
    - Ver relacionamentos com outros campos
    - Entender transformações aplicadas

    Args:
        field_name: Nome do campo
        procedure_name: Procedure onde buscar o campo (opcional, ajuda a filtrar)
        table_name: Tabela onde buscar o campo (opcional)

    Returns:
        JSON com análise completa do campo

    Examples:
        - "Analise o campo 'status'"
        - "O que faz o campo 'email' da procedure VALIDAR_USUARIO?"
        - "De onde vem o campo 'total_valor'?"
    """
    if not _knowledge_graph:
        return json.dumps({
            "success": False,
            "error": "Knowledge graph não inicializado. Execute a análise primeiro."
        })

    try:
        # Query field usage
        field_usage_list = _knowledge_graph.query_field_usage(
            field_name=field_name,
            procedure_name=procedure_name
        )

        if not field_usage_list:
            return json.dumps({
                "success": False,
                "error": f"Campo '{field_name}' não encontrado no knowledge graph. "
                        f"Verifique se o nome está correto ou se a análise foi executada."
            })

        # Get usage info
        usage_info = _knowledge_graph.get_field_usage(field_name)

        # Get relationships
        relationships = _knowledge_graph.get_field_relationships(field_name)

        # Find field in tables if table_name provided
        definition = None
        if table_name:
            table_info = _knowledge_graph.get_table_info(table_name)
            if table_info:
                for col in table_info.get("columns", []):
                    if col.get("name") == field_name:
                        definition = {
                            "table": table_name,
                            "data_type": col.get("data_type"),
                            "nullable": col.get("nullable"),
                            "is_primary_key": col.get("is_primary_key"),
                            "is_foreign_key": col.get("is_foreign_key")
                        }
                        break

        result = {
            "success": True,
            "data": {
                "field_name": field_name,
                "definition": definition,
                "usage": {
                    "read_by": usage_info.get("read_by", []),
                    "written_by": usage_info.get("written_by", []),
                    "used_in_procedures": usage_info.get("procedures", [])
                },
                "usage_count": len(field_usage_list),
                "relationships": relationships,
                "detailed_usage": [
                    {
                        "procedure": usage.get("procedure"),
                        "operations": usage.get("usage", {}).get("operations", []),
                        "transformations": usage.get("usage", {}).get("transformations", [])
                    }
                    for usage in field_usage_list
                ]
            }
        }

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.exception(f"Erro ao analisar campo {field_name}")
        return json.dumps({
            "success": False,
            "error": f"Erro ao analisar campo: {str(e)}"
        })


class TraceFieldFlowInput(BaseModel):
    """Input schema for trace_field_flow tool"""
    field_name: str = Field(
        description="Nome do campo a ser rastreado"
    )
    start_procedure: str = Field(
        description="Procedure inicial para começar o rastreamento"
    )
    max_depth: int = Field(
        default=10,
        description="Profundidade máxima do rastreamento (padrão: 10)"
    )


@tool(args_schema=TraceFieldFlowInput)
def trace_field_flow(
    field_name: str,
    start_procedure: str,
    max_depth: int = 10
) -> str:
    """Rastreia o fluxo completo de um campo através de procedures.

    Faz crawling seguindo o campo desde sua origem até seu destino final.
    Mostra todas as transformações e operações aplicadas ao campo.

    Use esta tool quando precisar:
    - Saber de onde um campo vem (origem dos dados)
    - Ver transformações aplicadas ao campo
    - Rastrear o caminho completo do dado
    - Entender quem alimenta o campo

    Args:
        field_name: Nome do campo
        start_procedure: Procedure onde começar o rastreamento
        max_depth: Profundidade máxima do rastreamento

    Returns:
        JSON com caminho completo e transformações

    Examples:
        - "Rastreie o campo 'status' desde PROCESSAR_PEDIDO"
        - "De onde vem o campo 'saldo' usado em CALCULAR_JUROS?"
        - "Trace o fluxo do campo 'email' começando em CRIAR_USUARIO"
    """
    if not _crawler:
        return json.dumps({
            "success": False,
            "error": "Crawler não inicializado. Esta funcionalidade requer o crawler."
        })

    try:
        trace_result = _crawler.trace_field(
            field_name=field_name,
            start_procedure=start_procedure,
            max_depth=max_depth
        )

        result = {
            "success": True,
            "data": {
                "field_name": trace_result.field_name,
                "start_procedure": start_procedure,
                "path": [
                    {
                        "procedure": step.procedure,
                        "operation": step.operation,
                        "depth": step.depth,
                        "context": step.context
                    }
                    for step in trace_result.path
                ],
                "sources": trace_result.sources,
                "destinations": trace_result.destinations,
                "transformations": trace_result.transformations,
                "path_length": len(trace_result.path),
                "source_count": len(trace_result.sources),
                "destination_count": len(trace_result.destinations)
            },
            "summary": {
                "field": field_name,
                "starts_at": start_procedure,
                "comes_from": trace_result.sources,
                "goes_to": trace_result.destinations,
                "has_transformations": len(trace_result.transformations) > 0
            }
        }

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.exception(f"Erro ao rastrear fluxo de {field_name}")
        return json.dumps({
            "success": False,
            "error": f"Erro ao rastrear fluxo: {str(e)}"
        })

