"""
LangChain Tools for CodeGraphAI
Tools for querying code knowledge graph and performing analysis
"""

from typing import List, Optional, Any

# Global dependencies (initialized by init_tools)
_knowledge_graph = None
_crawler = None
_db_config = None
_on_demand_analyzer = None


def init_tools(
    knowledge_graph: Any,
    crawler: Optional[Any] = None,
    db_config: Optional[Any] = None,
    on_demand_analyzer: Optional[Any] = None,
    config: Optional[Any] = None,
    llm_analyzer: Optional[Any] = None,
    procedures_dir: Optional[str] = None
) -> None:
    """
    Initialize tools with dependencies

    Args:
        knowledge_graph: CodeKnowledgeGraph instance
        crawler: CodeCrawler instance (optional)
        db_config: DatabaseConfig instance (optional, required for query tools)
        on_demand_analyzer: OnDemandAnalyzer instance (optional, if not provided will create one)
        config: Application config (optional, required to create OnDemandAnalyzer)
        llm_analyzer: LLMAnalyzer instance (optional, required to create OnDemandAnalyzer)
        procedures_dir: Directory with .prc files (optional, for OnDemandAnalyzer)
    """
    global _knowledge_graph, _crawler, _db_config, _on_demand_analyzer
    _knowledge_graph = knowledge_graph
    _crawler = crawler
    _db_config = db_config

    # Create OnDemandAnalyzer if not provided
    if on_demand_analyzer:
        _on_demand_analyzer = on_demand_analyzer
    elif config and llm_analyzer:
        from app.analysis.on_demand_analyzer import OnDemandAnalyzer
        _on_demand_analyzer = OnDemandAnalyzer(
            config=config,
            knowledge_graph=knowledge_graph,
            llm_analyzer=llm_analyzer,
            procedures_dir=procedures_dir,
            db_config=db_config
        )
    else:
        _on_demand_analyzer = None

    # Update globals in all tool modules
    import app.tools.graph_tools as gt
    import app.tools.field_tools as ft
    import app.tools.crawler_tools as ct

    gt._knowledge_graph = knowledge_graph
    gt._on_demand_analyzer = _on_demand_analyzer
    # graph_tools doesn't use crawler by default, but set it for consistency
    if hasattr(gt, '_crawler'):
        gt._crawler = crawler

    ft._knowledge_graph = knowledge_graph
    ft._crawler = crawler
    ft._on_demand_analyzer = _on_demand_analyzer

    ct._knowledge_graph = knowledge_graph
    ct._crawler = crawler
    ct._on_demand_analyzer = _on_demand_analyzer

    # Update query_tools if available
    try:
        import app.tools.query_tools as qt
        qt._db_config = db_config
    except ImportError:
        # query_tools might not be available, ignore
        pass


def get_all_tools() -> List:
    """
    Get all available tools

    Returns:
        List of tool functions
    """
    from app.tools.graph_tools import query_procedure, query_table
    from app.tools.field_tools import analyze_field, trace_field_flow
    from app.tools.crawler_tools import crawl_procedure

    tools = [
        query_procedure,
        query_table,
        analyze_field,
        trace_field_flow,
        crawl_procedure
    ]

    # Add query tools if available
    try:
        from app.tools.query_tools import execute_query, sample_table_data, get_field_statistics
        tools.extend([
            execute_query,
            sample_table_data,
            get_field_statistics
        ])
    except ImportError:
        # query_tools might not be available, skip
        pass

    return tools


__all__ = [
    'init_tools',
    'get_all_tools'
]
