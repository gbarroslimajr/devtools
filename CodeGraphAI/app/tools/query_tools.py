"""
Query Tools for executing SQL queries against database
Tools for retrieving actual data, not just metadata
"""

import json
import logging
import re
import signal
from typing import Optional, List, Dict, Any, Tuple
from pydantic import BaseModel, Field
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# Global dependency (set by init_tools)
_db_config = None


class TimeoutError(Exception):
    """Timeout exception for query execution"""
    pass


def _timeout_handler(signum, frame):
    """Handler for query timeout"""
    raise TimeoutError("Query execution timeout")


def _get_connection():
    """
    Create database connection based on DatabaseConfig

    Returns:
        Database connection object

    Raises:
        ValueError: If db_config is not set or invalid
        ImportError: If required driver is not installed
    """
    if not _db_config:
        raise ValueError("Database configuration not available. Provide database credentials to use query tools.")

    db_type = _db_config.db_type

    if db_type.value == 'postgresql':
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
        except ImportError:
            raise ImportError("psycopg2 não está instalado. Instale com: pip install psycopg2-binary>=2.9.0")

        port = _db_config.port or 5432
        if not _db_config.database:
            raise ValueError("PostgreSQL requer o nome do banco de dados (database)")

        connection = psycopg2.connect(
            host=_db_config.host,
            port=port,
            database=_db_config.database,
            user=_db_config.user,
            password=_db_config.password
        )
        return connection, 'RealDictCursor'

    elif db_type.value == 'oracle':
        try:
            import oracledb
        except ImportError:
            raise ImportError("oracledb não está instalado. Instale com: pip install oracledb>=1.4.0")

        # Parse DSN
        dsn_parts = _db_config.host.split('/')
        if len(dsn_parts) == 2:
            host_port = dsn_parts[0]
            service = dsn_parts[1]
        else:
            host_port = _db_config.host
            service = None

        if ':' in host_port:
            host, port_str = host_port.split(':')
            try:
                port = int(port_str)
            except ValueError:
                port = 1521
        else:
            host = host_port
            port = 1521

        dsn = f"{host}:{port}/{service}" if service else f"{host}:{port}"

        connection = oracledb.connect(
            user=_db_config.user,
            password=_db_config.password,
            dsn=dsn
        )
        return connection, None

    elif db_type.value == 'mssql':
        try:
            import pyodbc
        except ImportError:
            raise ImportError("pyodbc não está instalado. Instale com: pip install pyodbc>=5.0.0")

        if not _db_config.database:
            raise ValueError("SQL Server requer o nome do banco de dados (database)")

        port = _db_config.port or 1433
        driver = _db_config.extra_params.get('driver', 'ODBC Driver 17 for SQL Server')
        connection_string = (
            f"DRIVER={{{driver}}};"
            f"SERVER={_db_config.host},{port};"
            f"DATABASE={_db_config.database};"
            f"UID={_db_config.user};"
            f"PWD={_db_config.password}"
        )

        connection = pyodbc.connect(connection_string)
        return connection, None

    elif db_type.value == 'mysql':
        try:
            import mysql.connector
            driver = 'mysql-connector'
        except ImportError:
            try:
                import pymysql
                driver = 'pymysql'
            except ImportError:
                raise ImportError(
                    "Driver MySQL não está instalado. "
                    "Instale com: pip install mysql-connector-python>=8.0.0 ou pip install pymysql>=1.0.0"
                )

        if not _db_config.database:
            raise ValueError("MySQL requer o nome do banco de dados (database)")

        port = _db_config.port or 3306

        if driver == 'mysql-connector':
            connection = mysql.connector.connect(
                host=_db_config.host,
                port=port,
                database=_db_config.database,
                user=_db_config.user,
                password=_db_config.password
            )
        else:  # pymysql
            connection = pymysql.connect(
                host=_db_config.host,
                port=port,
                database=_db_config.database,
                user=_db_config.user,
                password=_db_config.password,
                cursorclass=pymysql.cursors.DictCursor
            )
        return connection, driver

    else:
        raise ValueError(f"Tipo de banco não suportado: {db_type.value}")


def _validate_select_query(query: str) -> Tuple[bool, Optional[str]]:
    """
    Validate that query is a safe SELECT statement

    Args:
        query: SQL query to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Remove comments and normalize whitespace
    query_clean = re.sub(r'--.*?$', '', query, flags=re.MULTILINE)
    query_clean = re.sub(r'/\*.*?\*/', '', query_clean, flags=re.DOTALL)
    query_clean = ' '.join(query_clean.split())

    # Check if starts with SELECT (case-insensitive)
    if not re.match(r'^\s*SELECT\s+', query_clean, re.IGNORECASE):
        return False, "Apenas queries SELECT são permitidas"

    # Block dangerous commands
    dangerous_keywords = [
        'DROP', 'DELETE', 'UPDATE', 'INSERT', 'TRUNCATE',
        'ALTER', 'CREATE', 'EXEC', 'EXECUTE', 'CALL',
        'GRANT', 'REVOKE', 'COMMIT', 'ROLLBACK'
    ]

    query_upper = query_clean.upper()
    for keyword in dangerous_keywords:
        # Check for keyword as separate word (not part of another word)
        pattern = r'\b' + keyword + r'\b'
        if re.search(pattern, query_upper):
            return False, f"Comando '{keyword}' não é permitido por segurança"

    # Check for multiple statements (semicolon followed by non-comment)
    parts = query_clean.split(';')
    if len(parts) > 1:
        for part in parts[1:]:
            part_clean = part.strip()
            if part_clean and not part_clean.startswith('--'):
                return False, "Múltiplos comandos não são permitidos"

    return True, None


def _add_limit_if_needed(query: str, max_limit: int = 1000) -> str:
    """
    Add LIMIT clause if not present

    Args:
        query: SQL query
        max_limit: Maximum limit value

    Returns:
        Query with LIMIT clause
    """
    query_upper = query.upper()

    # Check if LIMIT already exists
    if re.search(r'\bLIMIT\s+\d+', query_upper):
        # Extract existing limit and ensure it's within max
        limit_match = re.search(r'\bLIMIT\s+(\d+)', query_upper)
        if limit_match:
            existing_limit = int(limit_match.group(1))
            if existing_limit > max_limit:
                # Replace with max_limit
                query = re.sub(r'\bLIMIT\s+\d+', f'LIMIT {max_limit}', query, flags=re.IGNORECASE)
        return query

    # Check if TOP exists (SQL Server)
    if re.search(r'\bTOP\s+\d+', query_upper):
        return query

    # Add LIMIT at the end
    # Remove trailing semicolon if present
    query = query.rstrip().rstrip(';')
    query += f' LIMIT {max_limit}'

    return query


def _execute_safe_query(query: str, timeout: int = 30) -> Dict[str, Any]:
    """
    Execute a safe SELECT query with timeout

    Args:
        query: SQL SELECT query
        timeout: Timeout in seconds (default: 30)

    Returns:
        Dict with columns and rows

    Raises:
        ValueError: If query is invalid
        TimeoutError: If query times out
        Exception: For other database errors
    """
    # Validate query
    is_valid, error_msg = _validate_select_query(query)
    if not is_valid:
        raise ValueError(error_msg)

    # Add limit if needed
    query = _add_limit_if_needed(query, max_limit=1000)

    # Get connection
    conn_result = _get_connection()
    connection = conn_result[0]
    cursor_type = conn_result[1] if len(conn_result) > 1 else None
    driver = conn_result[1] if len(conn_result) > 1 and isinstance(conn_result[1], str) else None

    try:
        # Set timeout (if supported)
        if hasattr(connection, 'set_session'):
            # PostgreSQL
            with connection.cursor() as temp_cursor:
                temp_cursor.execute(f"SET statement_timeout = {timeout * 1000}")  # milliseconds

        # Create cursor
        if cursor_type == 'RealDictCursor':
            from psycopg2.extras import RealDictCursor
            cursor = connection.cursor(cursor_factory=RealDictCursor)
        elif driver == 'mysql-connector':
            cursor = connection.cursor(dictionary=True)
        else:
            cursor = connection.cursor()

        # Execute query with timeout using signal (Unix only)
        try:
            # Set signal alarm for timeout (Unix)
            signal.signal(signal.SIGALRM, _timeout_handler)
            signal.alarm(timeout)

            cursor.execute(query)
            rows = cursor.fetchall()

            # Cancel alarm
            signal.alarm(0)
        except (AttributeError, OSError):
            # Windows doesn't support SIGALRM, just execute without signal timeout
            cursor.execute(query)
            rows = cursor.fetchall()

        # Get column names
        if cursor_type == 'RealDictCursor' or driver == 'mysql-connector' or driver == 'pymysql':
            # Dictionary cursor
            if rows:
                columns = list(rows[0].keys())
            else:
                # No rows, get columns from cursor description
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
        else:
            # Regular cursor - get from description
            if cursor.description:
                columns = [desc[0] for desc in cursor.description]
            else:
                columns = []

        # Convert rows to list of dicts
        result_rows = []
        for row in rows:
            if isinstance(row, dict):
                result_rows.append({k: str(v) if v is not None else None for k, v in row.items()})
            else:
                # Convert tuple to dict
                row_dict = {}
                for i, col in enumerate(columns):
                    value = row[i] if i < len(row) else None
                    row_dict[col] = str(value) if value is not None else None
                result_rows.append(row_dict)

        return {
            "columns": columns,
            "rows": result_rows,
            "row_count": len(result_rows)
        }

    finally:
        cursor.close()
        connection.close()


class ExecuteQueryInput(BaseModel):
    """Input schema for execute_query tool"""
    query: str = Field(
        description="Query SQL SELECT a ser executada. Apenas SELECT é permitido por segurança."
    )
    limit: Optional[int] = Field(
        default=100,
        description="Limite máximo de linhas (padrão: 100, máximo: 1000). Será aplicado automaticamente se não especificado na query."
    )


@tool(args_schema=ExecuteQueryInput)
def execute_query(query: str, limit: Optional[int] = 100) -> str:
    """Executa uma query SELECT segura no banco de dados.

    Use esta tool quando precisar:
    - Consultar dados reais do banco de dados
    - Obter resultados de queries SELECT
    - Analisar dados de tabelas

    **IMPORTANTE - Segurança:**
    - Apenas queries SELECT são permitidas
    - LIMIT é aplicado automaticamente (máximo 1000 linhas)
    - Timeout de 30 segundos
    - Comandos perigosos (DROP, DELETE, UPDATE, etc.) são bloqueados

    Args:
        query: Query SQL SELECT
        limit: Limite de linhas (padrão: 100, máximo: 1000)

    Returns:
        JSON com colunas e dados retornados

    Examples:
        - "Execute: SELECT * FROM appointments LIMIT 10"
        - "Quantos registros tem a tabela users?"
        - "SELECT name, email FROM users WHERE active = true LIMIT 5"
    """
    try:
        if not _db_config:
            return json.dumps({
                "success": False,
                "error": "Configuração de banco de dados não disponível. "
                        "Forneça credenciais de banco para usar esta tool."
            })

        # Validate and adjust limit
        if limit and limit > 1000:
            limit = 1000
        elif not limit:
            limit = 100

        # Add limit to query if not present
        query_with_limit = _add_limit_if_needed(query, max_limit=limit)

        # Execute query
        result = _execute_safe_query(query_with_limit, timeout=30)

        return json.dumps({
            "success": True,
            "data": result
        }, indent=2)

    except ValueError as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        })
    except TimeoutError:
        return json.dumps({
            "success": False,
            "error": "Query excedeu o timeout de 30 segundos"
        })
    except ImportError as e:
        return json.dumps({
            "success": False,
            "error": f"Driver de banco não instalado: {str(e)}"
        })
    except Exception as e:
        logger.exception(f"Erro ao executar query: {e}")
        return json.dumps({
            "success": False,
            "error": f"Erro ao executar query: {str(e)}"
        })


class SampleTableDataInput(BaseModel):
    """Input schema for sample_table_data tool"""
    table_name: str = Field(
        description="Nome da tabela (com ou sem schema, ex: 'users' ou 'public.users')"
    )
    limit: Optional[int] = Field(
        default=10,
        description="Número de linhas a retornar (padrão: 10, máximo: 100)"
    )
    columns: Optional[List[str]] = Field(
        default=None,
        description="Lista de colunas específicas a retornar (opcional). Se não especificado, retorna todas."
    )


@tool(args_schema=SampleTableDataInput)
def sample_table_data(
    table_name: str,
    limit: Optional[int] = 10,
    columns: Optional[List[str]] = None
) -> str:
    """Retorna uma amostra de dados de uma tabela.

    Use esta tool quando precisar:
    - Ver exemplos de dados de uma tabela
    - Entender estrutura de dados
    - Verificar valores reais em campos

    Args:
        table_name: Nome da tabela (com ou sem schema)
        limit: Número de linhas (padrão: 10, máximo: 100)
        columns: Colunas específicas (opcional)

    Returns:
        JSON com amostra de dados

    Examples:
        - "Mostre 5 registros da tabela appointments"
        - "Amostra da tabela users com colunas name e email"
        - "10 registros da tabela public.orders"
    """
    try:
        if not _db_config:
            return json.dumps({
                "success": False,
                "error": "Configuração de banco de dados não disponível. "
                        "Forneça credenciais de banco para usar esta tool."
            })

        # Validate and adjust limit
        if limit and limit > 100:
            limit = 100
        elif not limit:
            limit = 10

        # Build query
        if columns:
            cols_str = ', '.join(columns)
            query = f"SELECT {cols_str} FROM {table_name} LIMIT {limit}"
        else:
            query = f"SELECT * FROM {table_name} LIMIT {limit}"

        # Execute query
        result = _execute_safe_query(query, timeout=30)

        return json.dumps({
            "success": True,
            "data": result,
            "table_name": table_name
        }, indent=2)

    except ValueError as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        })
    except TimeoutError:
        return json.dumps({
            "success": False,
            "error": "Query excedeu o timeout de 30 segundos"
        })
    except ImportError as e:
        return json.dumps({
            "success": False,
            "error": f"Driver de banco não instalado: {str(e)}"
        })
    except Exception as e:
        logger.exception(f"Erro ao obter amostra de dados: {e}")
        return json.dumps({
            "success": False,
            "error": f"Erro ao obter amostra de dados: {str(e)}"
        })


class GetFieldStatisticsInput(BaseModel):
    """Input schema for get_field_statistics tool"""
    table_name: str = Field(
        description="Nome da tabela (com ou sem schema)"
    )
    field_name: str = Field(
        description="Nome do campo/coluna para análise estatística"
    )


@tool(args_schema=GetFieldStatisticsInput)
def get_field_statistics(table_name: str, field_name: str) -> str:
    """Retorna estatísticas de um campo específico em uma tabela.

    Use esta tool quando precisar:
    - Análise estatística de campos
    - Valores mínimo, máximo, médio
    - Contagem de valores distintos
    - Contagem de nulos

    Args:
        table_name: Nome da tabela
        field_name: Nome do campo

    Returns:
        JSON com estatísticas do campo

    Examples:
        - "Estatísticas do campo price na tabela products"
        - "Qual o valor máximo do campo created_at na tabela users?"
        - "Quantos valores distintos tem o campo status na tabela orders?"
    """
    try:
        if not _db_config:
            return json.dumps({
                "success": False,
                "error": "Configuração de banco de dados não disponível. "
                        "Forneça credenciais de banco para usar esta tool."
            })

        db_type = _db_config.db_type.value

        # Build statistics query based on database type
        if db_type == 'postgresql':
            query = f"""
                SELECT
                    COUNT(*) as total_count,
                    COUNT({field_name}) as non_null_count,
                    COUNT(*) - COUNT({field_name}) as null_count,
                    COUNT(DISTINCT {field_name}) as distinct_count
                FROM {table_name}
            """
        elif db_type == 'oracle':
            query = f"""
                SELECT
                    COUNT(*) as total_count,
                    COUNT({field_name}) as non_null_count,
                    COUNT(*) - COUNT({field_name}) as null_count,
                    COUNT(DISTINCT {field_name}) as distinct_count
                FROM {table_name}
            """
        elif db_type == 'mssql':
            query = f"""
                SELECT
                    COUNT(*) as total_count,
                    COUNT({field_name}) as non_null_count,
                    COUNT(*) - COUNT({field_name}) as null_count,
                    COUNT(DISTINCT {field_name}) as distinct_count
                FROM {table_name}
            """
        elif db_type == 'mysql':
            query = f"""
                SELECT
                    COUNT(*) as total_count,
                    COUNT({field_name}) as non_null_count,
                    COUNT(*) - COUNT({field_name}) as null_count,
                    COUNT(DISTINCT {field_name}) as distinct_count
                FROM {table_name}
            """
        else:
            return json.dumps({
                "success": False,
                "error": f"Tipo de banco não suportado: {db_type}"
            })

        # Execute basic statistics
        basic_stats = _execute_safe_query(query, timeout=30)

        if not basic_stats.get("rows"):
            return json.dumps({
                "success": False,
                "error": "Não foi possível obter estatísticas básicas"
            })

        stats_row = basic_stats["rows"][0]
        result = {
            "table_name": table_name,
            "field_name": field_name,
            "total_count": int(stats_row.get("total_count", 0)),
            "non_null_count": int(stats_row.get("non_null_count", 0)),
            "null_count": int(stats_row.get("null_count", 0)),
            "distinct_count": int(stats_row.get("distinct_count", 0))
        }

        # Try to get min, max, avg for numeric fields
        try:
            numeric_query = f"""
                SELECT
                    MIN({field_name}) as min_value,
                    MAX({field_name}) as max_value,
                    AVG(CAST({field_name} AS DECIMAL)) as avg_value
                FROM {table_name}
                WHERE {field_name} IS NOT NULL
            """

            numeric_stats = _execute_safe_query(numeric_query, timeout=30)
            if numeric_stats.get("rows"):
                numeric_row = numeric_stats["rows"][0]
                result["min_value"] = numeric_row.get("min_value")
                result["max_value"] = numeric_row.get("max_value")
                result["avg_value"] = numeric_row.get("avg_value")
        except Exception:
            # Field might not be numeric, ignore
            pass

        return json.dumps({
            "success": True,
            "data": result
        }, indent=2)

    except ValueError as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        })
    except TimeoutError:
        return json.dumps({
            "success": False,
            "error": "Query excedeu o timeout de 30 segundos"
        })
    except ImportError as e:
        return json.dumps({
            "success": False,
            "error": f"Driver de banco não instalado: {str(e)}"
        })
    except Exception as e:
        logger.exception(f"Erro ao obter estatísticas: {e}")
        return json.dumps({
            "success": False,
            "error": f"Erro ao obter estatísticas: {str(e)}"
        })

