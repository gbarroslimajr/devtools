"""
Knowledge Graph for Code Analysis
Persistent graph structure for storing and querying code relationships
"""

import json
import logging
from typing import Dict, List, Set, Optional, Any
from pathlib import Path
from collections import defaultdict
from datetime import datetime

import networkx as nx

logger = logging.getLogger(__name__)


class CodeKnowledgeGraph:
    """
    Knowledge graph for storing and querying code relationships

    Uses NetworkX MultiDiGraph to store:
    - Procedures, tables, fields as nodes
    - Calls, accesses, reads, writes as edges
    """

    def __init__(self, cache_path: str = "./cache/knowledge_graph.json"):
        """
        Initialize knowledge graph

        Args:
            cache_path: Path to cache file
        """
        self.graph = nx.MultiDiGraph()
        self.cache_path = Path(cache_path)
        self.metadata = {
            "created_at": None,
            "updated_at": None,
            "version": "1.0.0"
        }
        self._load_from_cache()

    def add_procedure(self, proc_info: Dict[str, Any]) -> None:
        """
        Add procedure to knowledge graph

        Args:
            proc_info: Dict with procedure information
                Required keys: name, schema
                Optional: parameters, called_procedures, called_tables,
                         business_logic, complexity_score, source_code
        """
        name = proc_info["name"]
        schema = proc_info.get("schema", "unknown")
        full_name = f"{schema}.{name}"

        # Add node
        self.graph.add_node(
            full_name,
            node_type="procedure",
            name=name,
            schema=schema,
            parameters=proc_info.get("parameters", []),
            business_logic=proc_info.get("business_logic", ""),
            complexity_score=proc_info.get("complexity_score", 0),
            source_code=proc_info.get("source_code", ""),
            fields_used=proc_info.get("fields_used", {}),
            updated_at=datetime.now().isoformat()
        )

        # Add edges for procedure calls
        for called_proc in proc_info.get("called_procedures", []):
            self.graph.add_edge(
                full_name,
                called_proc,
                edge_type="calls",
                relationship="procedure_call"
            )

        # Add edges for table access
        for table in proc_info.get("called_tables", []):
            self.graph.add_edge(
                full_name,
                table,
                edge_type="accesses",
                relationship="table_access"
            )

        self.metadata["updated_at"] = datetime.now().isoformat()
        logger.debug(f"Added procedure to graph: {full_name}")

    def add_table(self, table_info: Dict[str, Any]) -> None:
        """
        Add table to knowledge graph

        Args:
            table_info: Dict with table information
                Required keys: name, schema
                Optional: columns, foreign_keys, indexes, business_purpose
        """
        name = table_info["name"]
        schema = table_info.get("schema", "unknown")
        full_name = f"{schema}.{name}"

        # Add node
        self.graph.add_node(
            full_name,
            node_type="table",
            name=name,
            schema=schema,
            columns=table_info.get("columns", []),
            foreign_keys=table_info.get("foreign_keys", []),
            indexes=table_info.get("indexes", []),
            business_purpose=table_info.get("business_purpose", ""),
            complexity_score=table_info.get("complexity_score", 0),
            row_count=table_info.get("row_count"),
            updated_at=datetime.now().isoformat()
        )

        # Add edges for foreign keys
        for fk in table_info.get("foreign_keys", []):
            referenced_table = fk.get("referenced_table")
            if referenced_table:
                self.graph.add_edge(
                    full_name,
                    referenced_table,
                    edge_type="references",
                    relationship="foreign_key",
                    columns=fk.get("columns", []),
                    referenced_columns=fk.get("referenced_columns", [])
                )

        self.metadata["updated_at"] = datetime.now().isoformat()
        logger.debug(f"Added table to graph: {full_name}")

    def add_field(self, field_info: Dict[str, Any]) -> None:
        """
        Add field/column information to graph

        Args:
            field_info: Dict with field information
                Required: field_name, table_name
                Optional: data_type, usage_info
        """
        field_name = field_info["field_name"]
        table_name = field_info.get("table_name", "unknown")
        full_name = f"{table_name}.{field_name}"

        # Add node
        self.graph.add_node(
            full_name,
            node_type="field",
            field_name=field_name,
            table_name=table_name,
            data_type=field_info.get("data_type", "unknown"),
            is_primary_key=field_info.get("is_primary_key", False),
            is_foreign_key=field_info.get("is_foreign_key", False),
            usage_info=field_info.get("usage_info", {}),
            updated_at=datetime.now().isoformat()
        )

        # Add edge to table
        if table_name and table_name != "unknown":
            self.graph.add_edge(
                full_name,
                table_name,
                edge_type="belongs_to",
                relationship="field_of_table"
            )

    def get_procedure_context(self, proc_name: str) -> Optional[Dict[str, Any]]:
        """
        Get complete context of a procedure

        Args:
            proc_name: Procedure name (with or without schema)

        Returns:
            Dict with procedure context or None if not found
        """
        # Find node (try with and without schema)
        node = self._find_node(proc_name, "procedure")
        if not node:
            return None

        node_data = self.graph.nodes[node]

        # Get dependencies
        called_procedures = []
        called_tables = []

        for _, target, data in self.graph.out_edges(node, data=True):
            if data.get("edge_type") == "calls":
                called_procedures.append(target)
            elif data.get("edge_type") == "accesses":
                called_tables.append(target)

        return {
            "name": node_data.get("name"),
            "schema": node_data.get("schema"),
            "full_name": node,
            "parameters": node_data.get("parameters", []),
            "business_logic": node_data.get("business_logic", ""),
            "complexity_score": node_data.get("complexity_score", 0),
            "called_procedures": called_procedures,
            "called_tables": called_tables,
            "fields_used": node_data.get("fields_used", {}),
            "source_code": node_data.get("source_code", "")
        }

    def get_table_info(self, table_name: str) -> Optional[Dict[str, Any]]:
        """
        Get table information

        Args:
            table_name: Table name (with or without schema)

        Returns:
            Dict with table info or None if not found
        """
        node = self._find_node(table_name, "table")
        if not node:
            return None

        node_data = self.graph.nodes[node]

        # Get relationships
        relationships = {}
        for _, target, data in self.graph.out_edges(node, data=True):
            rel_type = data.get("relationship", "unknown")
            if rel_type not in relationships:
                relationships[rel_type] = []
            relationships[rel_type].append(target)

        return {
            "name": node_data.get("name"),
            "schema": node_data.get("schema"),
            "full_name": node,
            "columns": node_data.get("columns", []),
            "foreign_keys": node_data.get("foreign_keys", []),
            "indexes": node_data.get("indexes", []),
            "business_purpose": node_data.get("business_purpose", ""),
            "complexity_score": node_data.get("complexity_score", 0),
            "row_count": node_data.get("row_count"),
            "relationships": relationships
        }

    def query_field_usage(
        self,
        field_name: str,
        procedure_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Query field usage across procedures

        Args:
            field_name: Field name to search
            procedure_name: Optional procedure to scope search

        Returns:
            List of dicts with field usage information
        """
        results = []

        # Search in procedure fields_used
        for node, data in self.graph.nodes(data=True):
            if data.get("node_type") != "procedure":
                continue

            if procedure_name and not node.endswith(procedure_name):
                continue

            fields_used = data.get("fields_used", {})
            if field_name in fields_used:
                results.append({
                    "procedure": node,
                    "field": field_name,
                    "usage": fields_used[field_name]
                })

        return results

    def get_field_relationships(self, field_name: str) -> Dict[str, List[str]]:
        """
        Get relationships for a field

        Args:
            field_name: Field name

        Returns:
            Dict with relationship types and targets
        """
        relationships = defaultdict(list)

        # Find field nodes
        for node, data in self.graph.nodes(data=True):
            if data.get("node_type") == "field" and data.get("field_name") == field_name:
                # Get edges
                for _, target, edge_data in self.graph.out_edges(node, data=True):
                    rel_type = edge_data.get("relationship", "unknown")
                    relationships[rel_type].append(target)

        return dict(relationships)

    def get_callers(self, proc_name: str) -> Set[str]:
        """
        Get procedures that call the given procedure

        Args:
            proc_name: Procedure name

        Returns:
            Set of procedure names that call this one
        """
        node = self._find_node(proc_name, "procedure")
        if not node:
            return set()

        callers = set()
        for source, _, data in self.graph.in_edges(node, data=True):
            if data.get("edge_type") == "calls":
                callers.add(source)

        return callers

    def get_field_usage(self, field_name: str) -> Dict[str, List[str]]:
        """
        Get where a field is read/written

        Args:
            field_name: Field name

        Returns:
            Dict with read_by, written_by lists
        """
        usage = {
            "read_by": [],
            "written_by": [],
            "procedures": []
        }

        # Search in procedures
        for node, data in self.graph.nodes(data=True):
            if data.get("node_type") != "procedure":
                continue

            fields_used = data.get("fields_used", {})
            if field_name in fields_used:
                usage["procedures"].append(node)
                field_usage = fields_used[field_name]

                if "read" in field_usage.get("operations", []):
                    usage["read_by"].append(node)
                if "write" in field_usage.get("operations", []):
                    usage["written_by"].append(node)

        return usage

    def _find_node(self, name: str, node_type: str) -> Optional[str]:
        """
        Find node by name (with or without schema)

        Args:
            name: Node name
            node_type: Type of node (procedure, table, field)

        Returns:
            Full node name or None
        """
        # Try exact match
        if name in self.graph and self.graph.nodes[name].get("node_type") == node_type:
            return name

        # Try partial match (name without schema)
        for node, data in self.graph.nodes(data=True):
            if data.get("node_type") == node_type:
                if node.endswith(f".{name}") or data.get("name") == name:
                    return node

        return None

    def save_to_cache(self) -> None:
        """Save knowledge graph to cache file"""
        try:
            # Ensure cache directory exists
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)

            # Convert graph to JSON-serializable format
            data = {
                "metadata": self.metadata,
                "nodes": [
                    {
                        "id": node,
                        **node_data
                    }
                    for node, node_data in self.graph.nodes(data=True)
                ],
                "edges": [
                    {
                        "source": source,
                        "target": target,
                        "key": key,
                        **edge_data
                    }
                    for source, target, key, edge_data in self.graph.edges(data=True, keys=True)
                ]
            }

            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.info(f"Knowledge graph saved to {self.cache_path}")
        except Exception as e:
            logger.error(f"Error saving knowledge graph: {e}")

    def _load_from_cache(self) -> None:
        """Load knowledge graph from cache file"""
        if not self.cache_path.exists():
            logger.debug("No cache file found, starting with empty graph")
            self.metadata["created_at"] = datetime.now().isoformat()
            return

        try:
            with open(self.cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.metadata = data.get("metadata", {})

            # Rebuild graph
            for node_data in data.get("nodes", []):
                node_id = node_data.pop("id")
                self.graph.add_node(node_id, **node_data)

            for edge_data in data.get("edges", []):
                source = edge_data.pop("source")
                target = edge_data.pop("target")
                key = edge_data.pop("key", None)
                self.graph.add_edge(source, target, key=key, **edge_data)

            logger.info(f"Knowledge graph loaded from {self.cache_path}")
            logger.info(f"Loaded {len(self.graph.nodes)} nodes and {len(self.graph.edges)} edges")
        except Exception as e:
            logger.error(f"Error loading knowledge graph: {e}")
            logger.info("Starting with empty graph")
            self.metadata["created_at"] = datetime.now().isoformat()

    def clear(self) -> None:
        """Clear all data from graph"""
        self.graph.clear()
        self.metadata["updated_at"] = datetime.now().isoformat()
        logger.info("Knowledge graph cleared")

    def get_statistics(self) -> Dict[str, Any]:
        """Get graph statistics"""
        node_types = defaultdict(int)
        edge_types = defaultdict(int)

        for _, data in self.graph.nodes(data=True):
            node_types[data.get("node_type", "unknown")] += 1

        for _, _, data in self.graph.edges(data=True):
            edge_types[data.get("edge_type", "unknown")] += 1

        return {
            "total_nodes": len(self.graph.nodes),
            "total_edges": len(self.graph.edges),
            "node_types": dict(node_types),
            "edge_types": dict(edge_types),
            "metadata": self.metadata
        }

