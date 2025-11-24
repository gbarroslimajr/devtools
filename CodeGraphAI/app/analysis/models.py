"""
Data models for code analysis
"""

from dataclasses import dataclass, field
from typing import List, Dict, Set, Any, Optional


@dataclass
class FieldUsage:
    """Information about how a field is used"""
    field_name: str
    read_by: List[str] = field(default_factory=list)
    written_by: List[str] = field(default_factory=list)
    transformations: List[str] = field(default_factory=list)
    operations: List[str] = field(default_factory=list)  # 'read', 'write', 'transform'
    contexts: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class TraceStep:
    """A single step in a field trace path"""
    procedure: str
    operation: str  # 'read', 'write', 'transform', 'pass'
    context: Dict[str, Any]
    depth: int = 0


@dataclass
class TracePath:
    """Complete trace path for a field"""
    path: List[TraceStep]
    sources: List[str]
    destinations: List[str]
    transformations: List[str]
    field_name: str


@dataclass
class CrawlResult:
    """Result of procedure crawling"""
    dependencies_tree: Dict[str, Any]
    procedures_found: List[str]
    tables_found: List[str]
    depth_reached: int
    fields_tracked: Dict[str, FieldUsage] = field(default_factory=dict)


@dataclass
class AnalysisResult:
    """Result of static code analysis"""
    procedures: Set[str]
    tables: Set[str]
    fields: Dict[str, FieldUsage]
    parameters: List[Dict[str, str]]
    variables: Set[str] = field(default_factory=set)
    control_structures: List[str] = field(default_factory=list)


@dataclass
class FieldDefinition:
    """Field definition information"""
    field_name: str
    table_name: Optional[str]
    data_type: Optional[str]
    source: str  # 'table', 'parameter', 'variable', 'derived'
    definition_location: Optional[str] = None

