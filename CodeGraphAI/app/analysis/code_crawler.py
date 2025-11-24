"""
Code Crawler for recursive dependency tracking
Crawls through procedures and tables following references
"""

import logging
from typing import Dict, List, Set, Optional, Any
from collections import deque

from app.analysis.models import TracePath, TraceStep, CrawlResult, FieldUsage

logger = logging.getLogger(__name__)


class CodeCrawler:
    """
    Code crawler for recursive dependency analysis
    Follows references through procedures and tables
    """

    def __init__(self, knowledge_graph):
        """
        Initialize crawler

        Args:
            knowledge_graph: CodeKnowledgeGraph instance
        """
        self.graph = knowledge_graph

    def crawl_procedure(
        self,
        proc_name: str,
        max_depth: int = 5,
        include_tables: bool = True
    ) -> CrawlResult:
        """
        Crawl procedure and its dependencies recursively

        Args:
            proc_name: Procedure name to start crawling
            max_depth: Maximum depth to crawl
            include_tables: Include table dependencies

        Returns:
            CrawlResult with dependency tree
        """
        visited_procedures = set()
        visited_tables = set()
        dependencies_tree = {}

        def _crawl_recursive(current_proc: str, depth: int) -> Dict[str, Any]:
            """Recursive crawling function"""
            if depth > max_depth or current_proc in visited_procedures:
                return {
                    "name": current_proc,
                    "depth": depth,
                    "truncated": depth > max_depth,
                    "dependencies": []
                }

            visited_procedures.add(current_proc)

            # Get procedure context
            proc_context = self.graph.get_procedure_context(current_proc)
            if not proc_context:
                return {
                    "name": current_proc,
                    "depth": depth,
                    "error": "Procedure not found in graph",
                    "dependencies": []
                }

            node = {
                "name": current_proc,
                "depth": depth,
                "complexity_score": proc_context.get("complexity_score", 0),
                "dependencies": []
            }

            # Crawl called procedures
            for called_proc in proc_context.get("called_procedures", []):
                child = _crawl_recursive(called_proc, depth + 1)
                node["dependencies"].append({
                    "type": "procedure",
                    **child
                })

            # Add table dependencies if requested
            if include_tables:
                for table_name in proc_context.get("called_tables", []):
                    if table_name not in visited_tables:
                        visited_tables.add(table_name)
                        table_info = self.graph.get_table_info(table_name)
                        node["dependencies"].append({
                            "type": "table",
                            "name": table_name,
                            "depth": depth + 1,
                            "columns": len(table_info.get("columns", [])) if table_info else 0
                        })

            return node

        # Start crawling
        dependencies_tree = _crawl_recursive(proc_name, 0)

        return CrawlResult(
            dependencies_tree=dependencies_tree,
            procedures_found=list(visited_procedures),
            tables_found=list(visited_tables),
            depth_reached=max_depth
        )

    def trace_field(
        self,
        field_name: str,
        start_procedure: str,
        max_depth: int = 10
    ) -> TracePath:
        """
        Trace a field through procedures to find its origin and usage

        Args:
            field_name: Field name to trace
            start_procedure: Starting procedure
            max_depth: Maximum depth to trace

        Returns:
            TracePath with complete trace information
        """
        visited = set()
        path = []
        sources = []
        destinations = []
        transformations = []

        def _trace_recursive(proc_name: str, field: str, depth: int) -> None:
            """Recursive field tracing"""
            if depth > max_depth or proc_name in visited:
                return

            visited.add(proc_name)

            # Get procedure context
            proc_context = self.graph.get_procedure_context(proc_name)
            if not proc_context:
                return

            # Check if field is used in this procedure
            fields_used = proc_context.get("fields_used", {})

            if field in fields_used:
                field_usage = fields_used[field]
                operations = field_usage.get("operations", [])

                for operation in operations:
                    step = TraceStep(
                        procedure=proc_name,
                        operation=operation,
                        context={
                            "field": field,
                            "usage": field_usage
                        },
                        depth=depth
                    )
                    path.append(step)

                    # Track transformations
                    if operation == 'transform':
                        for transform in field_usage.get("transformations", []):
                            if transform not in transformations:
                                transformations.append(transform)

                # If field is written here, this might be a source
                if 'write' in operations:
                    sources.append(proc_name)

                # If field is read here, this might be a destination
                if 'read' in operations:
                    destinations.append(proc_name)

            # Trace through called procedures
            for called_proc in proc_context.get("called_procedures", []):
                _trace_recursive(called_proc, field, depth + 1)

            # Check if field comes from tables
            for table_name in proc_context.get("called_tables", []):
                table_info = self.graph.get_table_info(table_name)
                if table_info:
                    for col in table_info.get("columns", []):
                        if col.get("name") == field:
                            sources.append(f"{table_name} (table)")
                            path.append(TraceStep(
                                procedure=proc_name,
                                operation="read_from_table",
                                context={
                                    "table": table_name,
                                    "field": field,
                                    "column_info": col
                                },
                                depth=depth
                            ))

        # Start tracing
        _trace_recursive(start_procedure, field_name, 0)

        return TracePath(
            path=path,
            sources=sources,
            destinations=destinations,
            transformations=transformations,
            field_name=field_name
        )

    def find_field_sources(
        self,
        field_name: str,
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Find all sources where a field is defined or written

        Args:
            field_name: Field name
            max_results: Maximum number of results

        Returns:
            List of source information
        """
        sources = []

        # Search in procedures
        usage_list = self.graph.query_field_usage(field_name)
        for usage in usage_list[:max_results]:
            usage_info = usage.get("usage", {})
            if "write" in usage_info.get("operations", []):
                sources.append({
                    "type": "procedure",
                    "name": usage.get("procedure"),
                    "field": field_name,
                    "operation": "write"
                })

        # Search in tables
        # This would require iterating through tables in graph
        for node, data in self.graph.graph.nodes(data=True):
            if data.get("node_type") == "table":
                for col in data.get("columns", []):
                    if col.get("name") == field_name:
                        sources.append({
                            "type": "table",
                            "name": node,
                            "field": field_name,
                            "data_type": col.get("data_type"),
                            "is_primary_key": col.get("is_primary_key", False)
                        })

        return sources[:max_results]

    def find_field_destinations(
        self,
        field_name: str,
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Find all destinations where a field is read or used

        Args:
            field_name: Field name
            max_results: Maximum number of results

        Returns:
            List of destination information
        """
        destinations = []

        # Search in procedures
        usage_list = self.graph.query_field_usage(field_name)
        for usage in usage_list[:max_results]:
            usage_info = usage.get("usage", {})
            if "read" in usage_info.get("operations", []):
                destinations.append({
                    "type": "procedure",
                    "name": usage.get("procedure"),
                    "field": field_name,
                    "operation": "read"
                })

        return destinations[:max_results]

    def analyze_field_flow(
        self,
        field_name: str,
        start_procedure: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Complete field flow analysis

        Args:
            field_name: Field to analyze
            start_procedure: Optional starting point

        Returns:
            Dict with complete flow analysis
        """
        # Find sources
        sources = self.find_field_sources(field_name)

        # Find destinations
        destinations = self.find_field_destinations(field_name)

        # Trace if starting procedure provided
        trace_path = None
        if start_procedure:
            trace_path = self.trace_field(field_name, start_procedure)

        return {
            "field_name": field_name,
            "sources": sources,
            "destinations": destinations,
            "trace": trace_path,
            "total_sources": len(sources),
            "total_destinations": len(destinations)
        }

    def get_procedure_impact(
        self,
        proc_name: str,
        max_depth: int = 3
    ) -> Dict[str, Any]:
        """
        Analyze the impact of a procedure
        Get who calls it and what it affects

        Args:
            proc_name: Procedure name
            max_depth: Maximum depth for analysis

        Returns:
            Dict with impact analysis
        """
        # Get callers (who depends on this)
        callers = self.graph.get_callers(proc_name)

        # Get what this procedure calls (dependencies)
        crawl_result = self.crawl_procedure(proc_name, max_depth=max_depth)

        # Get affected tables
        affected_tables = crawl_result.tables_found

        return {
            "procedure": proc_name,
            "callers": list(callers),
            "caller_count": len(callers),
            "dependencies": crawl_result.procedures_found,
            "dependency_count": len(crawl_result.procedures_found),
            "affected_tables": affected_tables,
            "affected_table_count": len(affected_tables),
            "total_impact_score": len(callers) + len(crawl_result.procedures_found)
        }

