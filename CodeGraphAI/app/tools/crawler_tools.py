"""
Crawler Tools for procedure dependency analysis
"""

import json
import logging
from pydantic import BaseModel, Field
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# Global dependencies (set by init_tools)
_knowledge_graph = None
_crawler = None
_on_demand_analyzer = None


class CrawlProcedureInput(BaseModel):
    """Input schema for crawl_procedure tool"""
    procedure_name: str = Field(
        description="Nome da procedure a ser analisada"
    )
    max_depth: int = Field(
        default=5,
        description="Profundidade máxima do crawling (padrão: 5)"
    )
    include_tables: bool = Field(
        default=True,
        description="Incluir tabelas acessadas no crawling"
    )


@tool(args_schema=CrawlProcedureInput)
def crawl_procedure(
    procedure_name: str,
    max_depth: int = 5,
    include_tables: bool = True
) -> str:
    """Faz crawling de uma procedure e todas suas dependências.

    Analisa recursivamente procedures chamadas e tabelas acessadas.
    Retorna árvore completa de dependências.

    Use esta tool quando precisar:
    - Ver árvore completa de dependências de uma procedure
    - Entender impacto de mudanças (análise de impacto)
    - Mapear fluxo completo de execução
    - Ver todas procedures e tabelas envolvidas

    Args:
        procedure_name: Nome da procedure
        max_depth: Profundidade máxima do crawling
        include_tables: Incluir tabelas no crawling

    Returns:
        JSON com árvore completa de dependências

    Examples:
        - "Faça crawling da procedure PROCESSAR_PEDIDO"
        - "Mostre todas dependências de CALCULAR_SALDO"
        - "Qual o impacto de modificar VALIDAR_USUARIO?"
    """
    if not _crawler:
        return json.dumps({
            "success": False,
            "error": "Crawler não inicializado. Esta funcionalidade requer o crawler."
        })

    try:
        # If procedure not in cache, try on-demand analysis
        if _on_demand_analyzer:
            proc_context = _knowledge_graph.get_procedure_context(procedure_name)
            if not proc_context:
                logger.info(f"Procedure '{procedure_name}' not in cache for crawling, attempting on-demand...")
                on_demand_result = _on_demand_analyzer.get_or_analyze_procedure(procedure_name)
                if not on_demand_result.get("success"):
                    return json.dumps({
                        "success": False,
                        "error": f"Procedure '{procedure_name}' não encontrada. {on_demand_result.get('error', '')}"
                    })

        crawl_result = _crawler.crawl_procedure(
            proc_name=procedure_name,
            max_depth=max_depth,
            include_tables=include_tables
        )

        result = {
            "success": True,
            "data": {
                "procedure_name": procedure_name,
                "dependencies_tree": crawl_result.dependencies_tree,
                "procedures_found": crawl_result.procedures_found,
                "tables_found": crawl_result.tables_found if include_tables else [],
                "depth_reached": crawl_result.depth_reached
            },
            "statistics": {
                "total_procedures": len(crawl_result.procedures_found),
                "total_tables": len(crawl_result.tables_found) if include_tables else 0,
                "max_depth": max_depth,
                "depth_reached": crawl_result.depth_reached
            },
            "summary": {
                "procedure": procedure_name,
                "calls": len(crawl_result.procedures_found) - 1,  # Exclude self
                "accesses": len(crawl_result.tables_found) if include_tables else 0,
                "complexity": "alta" if len(crawl_result.procedures_found) > 10 else "média" if len(crawl_result.procedures_found) > 5 else "baixa"
            }
        }

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.exception(f"Erro ao fazer crawling de {procedure_name}")
        return json.dumps({
            "success": False,
            "error": f"Erro ao fazer crawling: {str(e)}"
        })

