"""Database dialect adapter for SQLite, MySQL, and PostgreSQL compatibility.

This module provides dialect-specific SQL generation helpers so the same
agent code works across different database backends.
"""
from typing import Dict, Any

# Date function mappings
DATE_FUNCTIONS = {
    "sqlite": {
        "this_month": "strftime('%Y-%m', {col}) = strftime('%Y-%m', 'now')",
        "last_month": "strftime('%Y-%m', {col}) = strftime('%Y-%m', 'now', '-1 month')",
        "this_year": "strftime('%Y', {col}) = strftime('%Y', 'now')",
        "last_year": "strftime('%Y', {col}) = strftime('%Y', 'now', '-1 year')",
        "format": "strftime('%Y-%m', {col})",
        "month": "strftime('%Y-%m', {col})",
        "year": "strftime('%Y', {col})",
    },
    "mysql": {
        "this_month": "DATE_FORMAT({col}, '%Y-%m') = DATE_FORMAT(NOW(), '%Y-%m')",
        "last_month": "DATE_FORMAT({col}, '%Y-%m') = DATE_FORMAT(DATE_SUB(NOW(), INTERVAL 1 MONTH), '%Y-%m')",
        "this_year": "YEAR({col}) = YEAR(NOW())",
        "last_year": "YEAR({col}) = YEAR(NOW()) - 1",
        "format": "DATE_FORMAT({col}, '%Y-%m')",
        "month": "DATE_FORMAT({col}, '%Y-%m')",
        "year": "YEAR({col})",
    },
    "postgresql": {
        "this_month": "TO_CHAR({col}, 'YYYY-MM') = TO_CHAR(NOW(), 'YYYY-MM')",
        "last_month": "TO_CHAR({col}, 'YYYY-MM') = TO_CHAR(NOW() - INTERVAL '1 month', 'YYYY-MM')",
        "this_year": "EXTRACT(YEAR FROM {col}) = EXTRACT(YEAR FROM NOW())",
        "last_year": "EXTRACT(YEAR FROM {col}) = EXTRACT(YEAR FROM NOW()) - 1",
        "format": "TO_CHAR({col}, 'YYYY-MM')",
        "month": "TO_CHAR({col}, 'YYYY-MM')",
        "year": "EXTRACT(YEAR FROM {col})",
    }
}

# Limit syntax (same across all three, but kept for future extensions)
LIMIT_SYNTAX = {
    "sqlite": "LIMIT {n}",
    "mysql": "LIMIT {n}",
    "postgresql": "LIMIT {n}",
}

# String concatenation
STRING_CONCAT = {
    "sqlite": "||",
    "mysql": "CONCAT",
    "postgresql": "||",
}


def get_date_function(dialect: str, function: str, column: str = "date") -> str:
    """Get dialect-specific date function.

    Args:
        dialect: "sqlite", "mysql", or "postgresql"
        function: "this_month", "last_month", "this_year", "last_year", "format", "month", "year"
        column: Column name to apply function to

    Returns:
        SQL expression string
    """
    dialect_funcs = DATE_FUNCTIONS.get(dialect, DATE_FUNCTIONS["sqlite"])
    template = dialect_funcs.get(function, "{col}")
    return template.format(col=column)


def get_limit_clause(dialect: str, n: int) -> str:
    """Get dialect-specific LIMIT clause."""
    syntax = LIMIT_SYNTAX.get(dialect, LIMIT_SYNTAX["sqlite"])
    return syntax.format(n=n)


def detect_dialect(connection_string: str) -> str:
    """Detect database dialect from connection string.

    Args:
        connection_string: SQLAlchemy connection string

    Returns:
        "sqlite", "mysql", or "postgresql"
    """
    conn_lower = connection_string.lower()
    if "sqlite" in conn_lower:
        return "sqlite"
    elif "mysql" in conn_lower or "mariadb" in conn_lower or "pymysql" in conn_lower:
        return "mysql"
    elif "postgres" in conn_lower or "psycopg" in conn_lower:
        return "postgresql"
    else:
        # Default fallback
        return "sqlite"


def adapt_schema_for_dialect(schema: Dict[str, Any], dialect: str) -> Dict[str, Any]:
    """Adapt schema metadata for specific dialect.

    Currently a no-op since schema introspection is dialect-agnostic,
    but can be extended for dialect-specific type mappings.
    """
    return schema

