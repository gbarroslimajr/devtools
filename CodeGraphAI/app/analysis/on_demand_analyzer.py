"""
On-Demand Analyzer for procedures and tables
Automatically fetches and analyzes entities when not in cache
"""

import logging
from typing import Optional, Dict, Any
from pathlib import Path

from app.core.models import DatabaseConfig, ProcedureLoadError, TableLoadError
from app.io.procedure_loader import ProcedureLoader
from app.io.table_factory import create_table_loader

logger = logging.getLogger(__name__)


class OnDemandAnalyzer:
    """
    Analyzer that fetches and analyzes procedures/tables on-demand

    Priority for procedures:
    1. Cache (if not force_refresh)
    2. .prc file (if procedures_dir provided)
    3. Database
    4. Error "not found"

    Priority for tables:
    1. Cache (if not force_refresh)
    2. Database
    3. Error "not found"
    """

    def __init__(
        self,
        config: Any,
        knowledge_graph: Any,
        llm_analyzer: Any,
        procedures_dir: Optional[str] = None,
        db_config: Optional[DatabaseConfig] = None
    ):
        """
        Initialize OnDemandAnalyzer

        Args:
            config: Application config
            knowledge_graph: CodeKnowledgeGraph instance
            llm_analyzer: LLMAnalyzer instance for LLM-based analysis
            procedures_dir: Optional directory with .prc files
            db_config: Optional database configuration
        """
        self.config = config
        self.knowledge_graph = knowledge_graph
        self.llm_analyzer = llm_analyzer
        self.procedures_dir = procedures_dir
        self.db_config = db_config

        logger.info(f"OnDemandAnalyzer initialized (procedures_dir: {procedures_dir})")

    def get_or_analyze_procedure(
        self,
        proc_name: str,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Get procedure from cache or analyze on-demand

        Args:
            proc_name: Procedure name
            force_refresh: Force refresh even if in cache

        Returns:
            Dict with success status and data/error
        """
        try:
            # Check cache first (unless force_refresh)
            if not force_refresh:
                proc_context = self.knowledge_graph.get_procedure_context(proc_name)
                if proc_context:
                    logger.info(f"Procedure '{proc_name}' found in cache")
                    return {
                        "success": True,
                        "source": "cache",
                        "data": proc_context
                    }

            logger.info(f"Procedure '{proc_name}' not in cache, searching on-demand...")

            # Try to load from .prc file first
            source_code = None
            source = None

            if self.procedures_dir:
                source_code, source = self._load_procedure_from_file(proc_name)

            # If not found in file, try database
            if not source_code and self.db_config:
                source_code, source = self._load_procedure_from_database(proc_name)

            if not source_code:
                return {
                    "success": False,
                    "error": f"Procedure '{proc_name}' not found in files or database"
                }

            # Analyze with LLM
            logger.info(f"Analyzing procedure '{proc_name}' from {source}...")
            proc_info = self._analyze_procedure(proc_name, source_code)

            # Add to knowledge graph
            self._add_procedure_to_graph(proc_info)

            # Save cache
            self.knowledge_graph.save_to_cache()

            logger.info(f"Procedure '{proc_name}' analyzed and added to cache")

            return {
                "success": True,
                "source": source,
                "data": self.knowledge_graph.get_procedure_context(proc_name)
            }

        except Exception as e:
            logger.error(f"Error in get_or_analyze_procedure for '{proc_name}': {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    def get_or_analyze_table(
        self,
        table_name: str,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Get table from cache or analyze on-demand

        Args:
            table_name: Table name
            force_refresh: Force refresh even if in cache

        Returns:
            Dict with success status and data/error
        """
        try:
            # Check cache first (unless force_refresh)
            if not force_refresh:
                table_info = self.knowledge_graph.get_table_info(table_name)
                if table_info:
                    logger.info(f"Table '{table_name}' found in cache")
                    return {
                        "success": True,
                        "source": "cache",
                        "data": table_info
                    }

            logger.info(f"Table '{table_name}' not in cache, searching on-demand...")

            # Load from database
            if not self.db_config:
                return {
                    "success": False,
                    "error": f"Database not configured. Cannot fetch table '{table_name}'"
                }

            table_info = self._load_and_analyze_table(table_name)

            if not table_info:
                return {
                    "success": False,
                    "error": f"Table '{table_name}' not found in database"
                }

            # Add to knowledge graph
            self.knowledge_graph.add_table(table_info)

            # Save cache
            self.knowledge_graph.save_to_cache()

            logger.info(f"Table '{table_name}' analyzed and added to cache")

            return {
                "success": True,
                "source": "database",
                "data": self.knowledge_graph.get_table_info(table_name)
            }

        except Exception as e:
            logger.error(f"Error in get_or_analyze_table for '{table_name}': {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    def force_refresh(
        self,
        entity_name: str,
        entity_type: str
    ) -> Dict[str, Any]:
        """
        Force refresh of specific entity

        Args:
            entity_name: Name of entity (procedure or table)
            entity_type: Type ('procedure' or 'table')

        Returns:
            Dict with success status and data/error
        """
        logger.info(f"Force refreshing {entity_type} '{entity_name}'")

        if entity_type == "procedure":
            return self.get_or_analyze_procedure(entity_name, force_refresh=True)
        elif entity_type == "table":
            return self.get_or_analyze_table(entity_name, force_refresh=True)
        else:
            return {
                "success": False,
                "error": f"Invalid entity type: {entity_type}"
            }

    def _load_procedure_from_file(self, proc_name: str) -> tuple[Optional[str], Optional[str]]:
        """
        Try to load procedure from .prc file

        Returns:
            Tuple of (source_code, source_name) or (None, None)
        """
        try:
            proc_dir = Path(self.procedures_dir)

            # Try exact filename match
            proc_file = proc_dir / f"{proc_name}.prc"
            if proc_file.exists():
                with open(proc_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        logger.info(f"Loaded procedure '{proc_name}' from {proc_file}")
                        return content, "file"

            # Try case-insensitive search
            for file_path in proc_dir.rglob("*.prc"):
                if file_path.stem.upper() == proc_name.upper():
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        if content:
                            logger.info(f"Loaded procedure '{proc_name}' from {file_path}")
                            return content, "file"

            logger.debug(f"Procedure '{proc_name}' not found in {self.procedures_dir}")
            return None, None

        except Exception as e:
            logger.warning(f"Error loading procedure from file: {e}")
            return None, None

    def _load_procedure_from_database(self, proc_name: str) -> tuple[Optional[str], Optional[str]]:
        """
        Try to load procedure from database

        Returns:
            Tuple of (source_code, source_name) or (None, None)
        """
        try:
            # Extract schema if present
            if '.' in proc_name:
                schema, name = proc_name.split('.', 1)
            else:
                schema = self.db_config.schema
                name = proc_name

            # Load single procedure from database
            proc_db = ProcedureLoader.from_database(
                user=self.db_config.user,
                password=self.db_config.password,
                dsn=self.db_config.host,
                schema=schema,
                db_type=self.db_config.db_type.value,
                database=self.db_config.database,
                port=self.db_config.port
            )

            # Look for the procedure
            for proc_key, source_code in proc_db.items():
                if proc_key.upper() == proc_name.upper() or proc_key.upper().endswith(f".{name.upper()}"):
                    logger.info(f"Loaded procedure '{proc_name}' from database")
                    return source_code, "database"

            logger.debug(f"Procedure '{proc_name}' not found in database")
            return None, None

        except Exception as e:
            logger.warning(f"Error loading procedure from database: {e}")
            return None, None

    def _analyze_procedure(self, proc_name: str, source_code: str) -> Dict[str, Any]:
        """
        Analyze procedure with LLM

        Returns:
            ProcedureInfo dict
        """
        # Import here to avoid circular imports
        from analyzer import ProcedureAnalyzer

        # Create temporary analyzer
        temp_analyzer = ProcedureAnalyzer(self.llm_analyzer, knowledge_graph=None)

        # Analyze procedure
        proc_info = temp_analyzer._analyze_procedure_from_code(proc_name, source_code)

        return proc_info

    def _add_procedure_to_graph(self, proc_info: Any) -> None:
        """
        Add procedure to knowledge graph

        Args:
            proc_info: ProcedureInfo instance
        """
        from app.analysis.static_analyzer import StaticCodeAnalyzer

        # Static analysis for fields
        static_analyzer = StaticCodeAnalyzer()
        static_result = static_analyzer.analyze_code(proc_info.source_code, proc_info.name)

        # Prepare fields_used dict
        fields_used = {}
        for field_name, field_usage in static_result.fields.items():
            fields_used[field_name] = {
                "operations": field_usage.operations,
                "transformations": field_usage.transformations,
                "contexts": field_usage.contexts
            }

        # Add to knowledge graph
        self.knowledge_graph.add_procedure({
            "name": proc_info.name,
            "schema": proc_info.schema,
            "parameters": proc_info.parameters,
            "called_procedures": list(proc_info.called_procedures),
            "called_tables": list(proc_info.called_tables),
            "business_logic": proc_info.business_logic,
            "complexity_score": proc_info.complexity_score,
            "source_code": proc_info.source_code,
            "fields_used": fields_used
        })

    def _load_and_analyze_table(self, table_name: str) -> Optional[Dict[str, Any]]:
        """
        Load and analyze table from database

        Returns:
            TableInfo dict or None
        """
        try:
            # Import here to avoid circular imports
            from table_analyzer import TableAnalyzer

            # Create table loader
            loader = create_table_loader(self.db_config)

            # Load single table
            schema = self.db_config.schema
            if '.' in table_name:
                schema, table_name = table_name.split('.', 1)

            tables = loader.load_tables(self.db_config, limit=None)

            # Find the specific table
            table_info = None
            for tbl in tables:
                full_name = f"{tbl.schema}.{tbl.name}" if tbl.schema else tbl.name
                if full_name.upper() == f"{schema}.{table_name}".upper() if schema else table_name.upper():
                    table_info = tbl
                    break

            if not table_info:
                return None

            # Analyze with LLM
            temp_analyzer = TableAnalyzer(self.llm_analyzer, knowledge_graph=None)
            analyzed_table = temp_analyzer._analyze_single_table(table_info)

            # Convert to dict format for knowledge graph
            return {
                "name": analyzed_table.name,
                "schema": analyzed_table.schema,
                "full_name": analyzed_table.full_name,
                "columns": [
                    {
                        "name": col.name,
                        "data_type": col.data_type,
                        "nullable": col.nullable,
                        "is_primary_key": col.is_primary_key,
                        "is_foreign_key": col.is_foreign_key,
                        "foreign_key_table": col.foreign_key_table,
                        "foreign_key_column": col.foreign_key_column,
                        "default_value": col.default_value,
                        "comment": col.comment
                    }
                    for col in analyzed_table.columns
                ],
                "relationships": analyzed_table.relationships,
                "business_purpose": analyzed_table.business_purpose,
                "complexity_score": analyzed_table.complexity_score,
                "row_count": analyzed_table.row_count
            }

        except Exception as e:
            logger.error(f"Error loading and analyzing table '{table_name}': {e}", exc_info=True)
            return None

