"""
LangChain Tools for CodeGraphAI
Tools for querying code knowledge graph and performing analysis
"""

from typing import List, Optional, Any

# Global dependencies (initialized by init_tools)
_knowledge_graph = None
_crawler = None


def init_tools(knowledge_graph: Any, crawler: Optional[Any] = None) -> None:
    """
    Initialize tools with dependencies

    Args:
        knowledge_graph: CodeKnowledgeGraph instance
        crawler: CodeCrawler instance (optional)
    """
    global _knowledge_graph, _crawler
    _knowledge_graph = knowledge_graph
    _crawler = crawler

    # Update globals in all tool modules
    import app.tools.graph_tools as gt
    import app.tools.field_tools as ft
    import app.tools.crawler_tools as ct

    gt._knowledge_graph = knowledge_graph
    # graph_tools doesn't use crawler, but set it for consistency
    if hasattr(gt, '_crawler'):
        gt._crawler = crawler

    ft._knowledge_graph = knowledge_graph
    ft._crawler = crawler

    ct._knowledge_graph = knowledge_graph
    ct._crawler = crawler


def get_all_tools() -> List:
    """
    Get all available tools

    Returns:
        List of tool functions
    """
    from app.tools.graph_tools import query_procedure, query_table
    from app.tools.field_tools import analyze_field, trace_field_flow
    from app.tools.crawler_tools import crawl_procedure

    return [
        query_procedure,
        query_table,
        analyze_field,
        trace_field_flow,
        crawl_procedure
    ]


__all__ = [
    'init_tools',
    'get_all_tools'
]

