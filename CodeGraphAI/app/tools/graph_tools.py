"""
Graph Tools for querying Knowledge Graph
"""

import json
import logging
from typing import Optional
from pydantic import BaseModel, Field
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# Global dependency (set by init_tools)
_knowledge_graph = None


class QueryProcedureInput(BaseModel):
    """Input schema for query_procedure tool"""
    procedure_name: str = Field(
        description="Nome da procedure a ser consultada (ex: 'SCHEMA.PROC_NAME' ou apenas 'PROC_NAME')"
    )
    include_dependencies: bool = Field(
        default=True,
        description="Incluir dependências (procedures e tabelas chamadas)"
    )
    include_callers: bool = Field(
        default=False,
        description="Incluir quem chama esta procedure"
    )


@tool(args_schema=QueryProcedureInput)
def query_procedure(
    procedure_name: str,
    include_dependencies: bool = True,
    include_callers: bool = False
) -> str:
    """Consulta informações de uma stored procedure no knowledge graph.

    Use esta tool quando precisar:
    - Saber o que uma procedure faz (lógica de negócio)
    - Ver suas dependências (procedures e tabelas que ela chama)
    - Ver quem a chama (procedures que dependem dela)
    - Entender seus parâmetros e complexidade

    Args:
        procedure_name: Nome da procedure (com ou sem schema)
        include_dependencies: Incluir procedures e tabelas chamadas
        include_callers: Incluir quem chama esta procedure

    Returns:
        JSON com informações completas da procedure

    Examples:
        - "Consulte a procedure PROCESSAR_PEDIDO"
        - "O que faz a procedure VALIDAR_USUARIO?"
        - "Quem chama a procedure CALCULAR_SALDO?"
    """
    if not _knowledge_graph:
        return json.dumps({
            "success": False,
            "error": "Knowledge graph não inicializado. Execute a análise primeiro."
        })

    try:
        proc_context = _knowledge_graph.get_procedure_context(procedure_name)

        if not proc_context:
            return json.dumps({
                "success": False,
                "error": f"Procedure '{procedure_name}' não encontrada no knowledge graph. "
                        f"Verifique se o nome está correto ou se a análise foi executada."
            })

        result = {
            "success": True,
            "data": {
                "procedure_name": proc_context.get("name"),
                "schema": proc_context.get("schema"),
                "full_name": proc_context.get("full_name"),
                "parameters": proc_context.get("parameters", []),
                "business_logic": proc_context.get("business_logic", ""),
                "complexity_score": proc_context.get("complexity_score", 0)
            }
        }

        if include_dependencies:
            result["data"]["dependencies"] = {
                "procedures": proc_context.get("called_procedures", []),
                "tables": proc_context.get("called_tables", [])
            }
            result["data"]["total_dependencies"] = (
                len(proc_context.get("called_procedures", [])) +
                len(proc_context.get("called_tables", []))
            )

        if include_callers:
            callers = _knowledge_graph.get_callers(proc_context.get("full_name", procedure_name))
            result["data"]["callers"] = list(callers)
            result["data"]["caller_count"] = len(callers)

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.exception(f"Erro ao consultar procedure {procedure_name}")
        return json.dumps({
            "success": False,
            "error": f"Erro ao consultar procedure: {str(e)}"
        })


class QueryTableInput(BaseModel):
    """Input schema for query_table tool"""
    table_name: str = Field(
        description="Nome da tabela (ex: 'SCHEMA.TABLE_NAME' ou apenas 'TABLE_NAME')"
    )
    include_columns: bool = Field(
        default=True,
        description="Incluir informações das colunas"
    )
    include_relationships: bool = Field(
        default=True,
        description="Incluir relacionamentos (foreign keys)"
    )


@tool(args_schema=QueryTableInput)
def query_table(
    table_name: str,
    include_columns: bool = True,
    include_relationships: bool = True
) -> str:
    """Consulta informações de uma tabela no knowledge graph.

    Use esta tool quando precisar:
    - Ver estrutura de uma tabela
    - Ver colunas, tipos e constraints
    - Ver relacionamentos (foreign keys)
    - Entender o propósito da tabela

    Args:
        table_name: Nome da tabela (com ou sem schema)
        include_columns: Incluir detalhes das colunas
        include_relationships: Incluir foreign keys e relacionamentos

    Returns:
        JSON com informações completas da tabela

    Examples:
        - "Mostre a estrutura da tabela PEDIDOS"
        - "Quais colunas tem a tabela USUARIOS?"
        - "Com quais tabelas a tabela PRODUTOS se relaciona?"
    """
    if not _knowledge_graph:
        return json.dumps({
            "success": False,
            "error": "Knowledge graph não inicializado. Execute a análise primeiro."
        })

    try:
        table_info = _knowledge_graph.get_table_info(table_name)

        if not table_info:
            return json.dumps({
                "success": False,
                "error": f"Tabela '{table_name}' não encontrada no knowledge graph. "
                        f"Verifique se o nome está correto ou se a análise foi executada."
            })

        result = {
            "success": True,
            "data": {
                "table_name": table_info.get("name"),
                "schema": table_info.get("schema"),
                "full_name": table_info.get("full_name"),
                "business_purpose": table_info.get("business_purpose", ""),
                "complexity_score": table_info.get("complexity_score", 0),
                "row_count": table_info.get("row_count")
            }
        }

        if include_columns:
            columns = table_info.get("columns", [])
            result["data"]["columns"] = [
                {
                    "name": col.get("name"),
                    "data_type": col.get("data_type"),
                    "nullable": col.get("nullable", True),
                    "is_primary_key": col.get("is_primary_key", False),
                    "is_foreign_key": col.get("is_foreign_key", False),
                    "default_value": col.get("default_value")
                }
                for col in columns
            ]
            result["data"]["column_count"] = len(columns)

        if include_relationships:
            result["data"]["relationships"] = table_info.get("relationships", {})

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.exception(f"Erro ao consultar tabela {table_name}")
        return json.dumps({
            "success": False,
            "error": f"Erro ao consultar tabela: {str(e)}"
        })

