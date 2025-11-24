"""
Static Code Analyzer
Performs static analysis of SQL/PL-SQL code without LLM
"""

import re
import logging
from typing import Dict, Set, List, Tuple, Optional
from collections import defaultdict

from app.analysis.models import AnalysisResult, FieldUsage

logger = logging.getLogger(__name__)


class StaticCodeAnalyzer:
    """
    Static code analyzer using regex and pattern matching
    Extracts dependencies, field usage, and code structure without LLM
    """

    # SQL keywords to filter out
    SQL_KEYWORDS = {
        'TO_DATE', 'TO_CHAR', 'TO_NUMBER', 'NVL', 'NVL2', 'COALESCE',
        'DECODE', 'CASE', 'CAST', 'CONVERT', 'COUNT', 'SUM', 'AVG',
        'MAX', 'MIN', 'SUBSTR', 'SUBSTRING', 'TRIM', 'LTRIM', 'RTRIM',
        'UPPER', 'LOWER', 'INITCAP', 'LENGTH', 'CONCAT', 'REPLACE',
        'INSTR', 'POSITION', 'LPAD', 'RPAD', 'ROUND', 'TRUNC', 'FLOOR',
        'CEIL', 'ABS', 'MOD', 'POWER', 'SQRT', 'SYSDATE', 'CURRENT_DATE',
        'CURRENT_TIMESTAMP', 'NOW', 'GETDATE', 'ADD_MONTHS', 'MONTHS_BETWEEN',
        'NEXT_DAY', 'LAST_DAY', 'EXTRACT', 'DATEPART', 'DATEDIFF',
        'ROW_NUMBER', 'RANK', 'DENSE_RANK', 'LAG', 'LEAD', 'FIRST_VALUE',
        'LAST_VALUE', 'LISTAGG', 'STRING_AGG', 'GROUP_CONCAT'
    }

    def __init__(self):
        """Initialize static analyzer"""
        pass

    def analyze_code(self, code: str, proc_name: str) -> AnalysisResult:
        """
        Perform complete static analysis of code

        Args:
            code: Source code to analyze
            proc_name: Name of the procedure/function

        Returns:
            AnalysisResult with all extracted information
        """
        # Extract different components
        procedures = self._extract_procedures(code)
        tables = self._extract_tables(code)
        fields = self._extract_field_usage(code)
        parameters = self._extract_parameters(code)
        variables = self._extract_variables(code)
        control_structures = self._extract_control_structures(code)

        return AnalysisResult(
            procedures=procedures,
            tables=tables,
            fields=fields,
            parameters=parameters,
            variables=variables,
            control_structures=control_structures
        )

    def _extract_procedures(self, code: str) -> Set[str]:
        """
        Extract procedure/function calls from code

        Args:
            code: Source code

        Returns:
            Set of procedure names
        """
        procedures = set()

        # Patterns for procedure calls
        patterns = [
            # EXEC/EXECUTE/CALL
            r'(?i)(?:EXECUTE|EXEC|CALL)\s+([a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)?)',
            # Function calls (name followed by parenthesis)
            r'(?i)([a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)?)\s*\(',
            # Package.procedure calls
            r'(?i)([a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*)\s*\(',
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, code)
            for match in matches:
                proc = match.group(1).upper()
                # Filter out SQL built-in functions
                if proc not in self.SQL_KEYWORDS and '.' not in proc:
                    procedures.add(proc)
                elif '.' in proc:
                    # Package.procedure - always add
                    procedures.add(proc)

        return procedures

    def _extract_tables(self, code: str) -> Set[str]:
        """
        Extract table references from code

        Args:
            code: Source code

        Returns:
            Set of table names
        """
        tables = set()

        patterns = [
            # FROM clause
            r'(?i)FROM\s+([a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)?)',
            # JOIN clause
            r'(?i)JOIN\s+([a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)?)',
            # INTO clause (INSERT)
            r'(?i)INTO\s+([a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)?)',
            # UPDATE clause
            r'(?i)UPDATE\s+([a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)?)',
            # DELETE FROM
            r'(?i)DELETE\s+FROM\s+([a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)?)',
            # MERGE INTO
            r'(?i)MERGE\s+INTO\s+([a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)?)',
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, code)
            for match in matches:
                table = match.group(1).upper()
                tables.add(table)

        return tables

    def _extract_field_usage(self, code: str) -> Dict[str, FieldUsage]:
        """
        Extract field usage information from code

        Args:
            code: Source code

        Returns:
            Dict mapping field names to FieldUsage objects
        """
        field_usage_map = defaultdict(lambda: FieldUsage(field_name=""))

        # Extract fields from SELECT
        select_fields = self._extract_select_fields(code)
        for field_name, context in select_fields:
            if field_name not in field_usage_map:
                field_usage_map[field_name].field_name = field_name
            field_usage_map[field_name].operations.append('read')
            field_usage_map[field_name].contexts.append({
                'type': 'select',
                'context': context
            })

        # Extract fields from INSERT
        insert_fields = self._extract_insert_fields(code)
        for field_name, context in insert_fields:
            if field_name not in field_usage_map:
                field_usage_map[field_name].field_name = field_name
            field_usage_map[field_name].operations.append('write')
            field_usage_map[field_name].contexts.append({
                'type': 'insert',
                'context': context
            })

        # Extract fields from UPDATE
        update_fields = self._extract_update_fields(code)
        for field_name, context in update_fields:
            if field_name not in field_usage_map:
                field_usage_map[field_name].field_name = field_name
            field_usage_map[field_name].operations.append('write')
            field_usage_map[field_name].contexts.append({
                'type': 'update',
                'context': context
            })

        # Extract transformations
        transformations = self._extract_transformations(code)
        for field_name, transform in transformations:
            if field_name not in field_usage_map:
                field_usage_map[field_name].field_name = field_name
            field_usage_map[field_name].transformations.append(transform)
            field_usage_map[field_name].operations.append('transform')

        return dict(field_usage_map)

    def _extract_select_fields(self, code: str) -> List[Tuple[str, str]]:
        """Extract fields from SELECT statements"""
        fields = []

        # Pattern: SELECT ... FROM
        pattern = r'(?i)SELECT\s+(.*?)\s+FROM'
        matches = re.finditer(pattern, code, re.DOTALL)

        for match in matches:
            select_clause = match.group(1)
            context = match.group(0)

            # Split by comma (but not inside parentheses)
            field_list = self._split_by_comma(select_clause)

            for field_expr in field_list:
                # Extract field name (remove aliases, functions, etc)
                field_name = self._extract_field_name(field_expr)
                if field_name and field_name != '*':
                    fields.append((field_name, context[:100]))  # Limit context size

        return fields

    def _extract_insert_fields(self, code: str) -> List[Tuple[str, str]]:
        """Extract fields from INSERT statements"""
        fields = []

        # Pattern: INSERT INTO table (field1, field2, ...)
        pattern = r'(?i)INSERT\s+INTO\s+\w+\s*\((.*?)\)'
        matches = re.finditer(pattern, code)

        for match in matches:
            field_list_str = match.group(1)
            context = match.group(0)

            # Split fields
            field_names = [f.strip().upper() for f in field_list_str.split(',')]
            for field_name in field_names:
                if field_name:
                    fields.append((field_name, context[:100]))

        return fields

    def _extract_update_fields(self, code: str) -> List[Tuple[str, str]]:
        """Extract fields from UPDATE statements"""
        fields = []

        # Pattern: UPDATE ... SET field = value
        pattern = r'(?i)UPDATE\s+.*?SET\s+(.*?)(?:WHERE|$)'
        matches = re.finditer(pattern, code, re.DOTALL)

        for match in matches:
            set_clause = match.group(1)
            context = match.group(0)

            # Extract field assignments
            assignments = set_clause.split(',')
            for assignment in assignments:
                if '=' in assignment:
                    field_name = assignment.split('=')[0].strip().upper()
                    # Remove table aliases
                    if '.' in field_name:
                        field_name = field_name.split('.')[-1]
                    if field_name:
                        fields.append((field_name, context[:100]))

        return fields

    def _extract_transformations(self, code: str) -> List[Tuple[str, str]]:
        """Extract field transformations (UPPER, LOWER, CONCAT, etc)"""
        transformations = []

        # Common transformation functions
        functions = ['UPPER', 'LOWER', 'TRIM', 'SUBSTR', 'CONCAT', 'REPLACE', 'CAST']

        for func in functions:
            pattern = rf'(?i){func}\s*\(\s*([a-z_][a-z0-9_]*)'
            matches = re.finditer(pattern, code)

            for match in matches:
                field_name = match.group(1).upper()
                transform = f"{func}({field_name})"
                transformations.append((field_name, transform))

        return transformations

    def _extract_parameters(self, code: str) -> List[Dict[str, str]]:
        """
        Extract procedure parameters from code

        Args:
            code: Source code

        Returns:
            List of dicts with parameter info
        """
        parameters = []

        # Pattern for parameter declarations
        # Example: p_param_name IN VARCHAR2, p_other OUT NUMBER
        pattern = r'(?i)(\w+)\s+(IN|OUT|INOUT|IN\s+OUT)\s+([\w\(\)]+)'
        matches = re.finditer(pattern, code)

        for match in matches:
            param_name = match.group(1)
            direction = match.group(2).upper().replace(' ', '_')
            data_type = match.group(3).upper()

            parameters.append({
                'name': param_name,
                'direction': direction,
                'type': data_type
            })

        return parameters

    def _extract_variables(self, code: str) -> Set[str]:
        """Extract local variable declarations"""
        variables = set()

        # Pattern for variable declarations
        # Example: v_variable VARCHAR2(100);
        pattern = r'(?i)(v_\w+|l_\w+)\s+[\w\(\)]+;'
        matches = re.finditer(pattern, code)

        for match in matches:
            var_name = match.group(1).upper()
            variables.add(var_name)

        return variables

    def _extract_control_structures(self, code: str) -> List[str]:
        """Extract control structures (IF, LOOP, CASE, etc)"""
        structures = []

        patterns = [
            (r'(?i)\bIF\b', 'IF'),
            (r'(?i)\bLOOP\b', 'LOOP'),
            (r'(?i)\bFOR\b', 'FOR'),
            (r'(?i)\bWHILE\b', 'WHILE'),
            (r'(?i)\bCASE\b', 'CASE'),
            (r'(?i)\bEXCEPTION\b', 'EXCEPTION'),
        ]

        for pattern, structure_type in patterns:
            matches = re.finditer(pattern, code)
            for _ in matches:
                structures.append(structure_type)

        return structures

    def _split_by_comma(self, text: str) -> List[str]:
        """Split text by comma, respecting parentheses"""
        parts = []
        current = []
        paren_depth = 0

        for char in text:
            if char == '(':
                paren_depth += 1
                current.append(char)
            elif char == ')':
                paren_depth -= 1
                current.append(char)
            elif char == ',' and paren_depth == 0:
                parts.append(''.join(current).strip())
                current = []
            else:
                current.append(char)

        if current:
            parts.append(''.join(current).strip())

        return parts

    def _extract_field_name(self, field_expr: str) -> Optional[str]:
        """Extract clean field name from expression"""
        # Remove AS alias
        if ' AS ' in field_expr.upper():
            field_expr = field_expr.split(' AS ')[0]
        elif ' ' in field_expr and not any(f in field_expr.upper() for f in self.SQL_KEYWORDS):
            # Space without AS might be alias
            field_expr = field_expr.split()[0]

        # Remove table prefix (table.field -> field)
        if '.' in field_expr:
            field_expr = field_expr.split('.')[-1]

        # Remove function calls
        if '(' in field_expr:
            # Try to extract field from function
            inner = re.search(r'\(([^)]+)\)', field_expr)
            if inner:
                field_expr = inner.group(1)
                if '.' in field_expr:
                    field_expr = field_expr.split('.')[-1]

        # Clean and return
        field_name = field_expr.strip().upper()

        # Filter out literals, keywords, etc
        if field_name and field_name not in self.SQL_KEYWORDS:
            # Check if it's a valid identifier
            if re.match(r'^[A-Z_][A-Z0-9_]*$', field_name):
                return field_name

        return None

    def extract_field_usage_for_field(
        self,
        code: str,
        field_name: str
    ) -> FieldUsage:
        """
        Extract usage information for a specific field

        Args:
            code: Source code
            field_name: Specific field to analyze

        Returns:
            FieldUsage object
        """
        all_fields = self._extract_field_usage(code)
        return all_fields.get(field_name.upper(), FieldUsage(field_name=field_name))

