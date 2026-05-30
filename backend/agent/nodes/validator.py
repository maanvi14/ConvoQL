"""Validator node: Validates SQL with schema-aware checks, EXPLAIN and dry-run execution."""
from typing import Dict, Any, List
from sqlalchemy import text
import re
from config import get_settings
from db.connection import db_manager

settings = get_settings()

FORBIDDEN_KEYWORDS = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE", "CREATE", "GRANT", "REPLACE", "MERGE"]

# Schema cache for validation
_schema_cache = None

async def _get_schema_columns() -> Dict[str, List[str]]:
    """Get actual columns from schema for validation."""
    global _schema_cache
    if _schema_cache is None:
        schema = await db_manager.get_schema()
        _schema_cache = {}
        for table in schema.get("tables", []):
            table_name = table["name"].lower()
            _schema_cache[table_name] = [col["name"].lower() for col in table.get("columns", [])]
            # Also store original case for error messages
            _schema_cache[f"{table_name}_orig"] = [col["name"] for col in table.get("columns", [])]
    return _schema_cache


def _extract_table_column_refs(sql: str) -> List[tuple]:
    """Extract table.column references from SQL."""
    refs = re.findall(r'\b(\w+)\.(\w+)\b', sql)
    return refs


def _extract_bare_column_refs(sql: str) -> List[str]:
    """Extract bare column references, EXCLUDING aliases defined in SELECT."""
    # Remove string literals first
    sql_clean = re.sub(r"'[^']*'", "''", sql)
    sql_clean = re.sub(r'"[^"]*"', '""', sql_clean)

    # === CRITICAL FIX: Extract aliases defined in SELECT so we skip them ===
    aliases = set()
    select_match = re.search(r'SELECT\s+(.*?)\s+FROM\b', sql_clean, re.IGNORECASE | re.DOTALL)
    if select_match:
        select_part = select_match.group(1)
        # Find AS aliases: "foo AS bar" or "foo bar"
        # Pattern 1: ... AS alias
        as_aliases = re.findall(r'\bAS\s+(\w+)\b', select_part, re.IGNORECASE)
        aliases.update(a.lower() for a in as_aliases)
        # Pattern 2: SUM(...) alias (no AS)
        # Match function calls followed by a bare word
        func_aliases = re.findall(r'\)\s+(\w+)\b', select_part)
        aliases.update(a.lower() for a in func_aliases if a.lower() not in {'from', 'where', 'and', 'or'})

    # Extract column names from SELECT clause (skip aliases)
    select_cols = []
    if select_match:
        select_part = select_match.group(1)
        # Simple approach: extract words that look like column names
        raw_cols = re.findall(r'(?<![\w.])\b([a-zA-Z_][a-zA-Z0-9_]*)\b', select_part)
        select_cols = [c for c in raw_cols if c.lower() not in aliases]

    # Extract from WHERE, GROUP BY, ORDER BY, HAVING
    where_match = re.search(r'WHERE\s+(.*?)(?:GROUP\s+BY|ORDER\s+BY|HAVING|LIMIT|$)', sql_clean, re.IGNORECASE | re.DOTALL)
    where_cols = []
    if where_match:
        where_part = where_match.group(1)
        where_cols = re.findall(r'(?<![\w.])\b([a-zA-Z_][a-zA-Z0-9_]*)\b', where_part)

    group_match = re.search(r'GROUP\s+BY\s+(.*?)(?:ORDER\s+BY|HAVING|LIMIT|$)', sql_clean, re.IGNORECASE | re.DOTALL)
    group_cols = []
    if group_match:
        group_cols = re.findall(r'(?<![\w.])\b([a-zA-Z_][a-zA-Z0-9_]*)\b', group_match.group(1))

    order_match = re.search(r'ORDER\s+BY\s+(.*?)(?:LIMIT|$)', sql_clean, re.IGNORECASE | re.DOTALL)
    order_cols = []
    if order_match:
        # In ORDER BY, aliases ARE valid references to SELECT expressions
        # So we should NOT flag aliases used in ORDER BY
        order_part = order_match.group(1)
        order_cols = re.findall(r'(?<![\w.])\b([a-zA-Z_][a-zA-Z0-9_]*)\b', order_part)
        # Remove aliases from validation since they're valid in ORDER BY
        order_cols = [c for c in order_cols if c.lower() not in aliases]

    all_cols = select_cols + where_cols + group_cols + order_cols

    # Filter out SQL keywords and function names
    sql_keywords = {
        'SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'NOT', 'NULL', 'IS', 'IN', 'BETWEEN',
        'LIKE', 'LIMIT', 'ORDER', 'BY', 'GROUP', 'HAVING', 'ASC', 'DESC', 'AS',
        'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER', 'ON', 'DISTINCT', 'ALL',
        'COUNT', 'SUM', 'AVG', 'MAX', 'MIN', 'ABS', 'ROUND', 'CAST', 'COALESCE',
        'strftime', 'DATE_FORMAT', 'TO_CHAR', 'NOW', 'CURRENT_DATE', 'CURRENT_TIMESTAMP',
        'WHEN', 'THEN', 'ELSE', 'END', 'CASE', 'IF', 'TRUE', 'FALSE',
        'EXISTS', 'UNION', 'INTERSECT', 'EXCEPT', 'WITH', 'TRUE', 'FALSE',
        'INTEGER', 'REAL', 'TEXT', 'DATE', 'PRIMARY', 'KEY', 'AUTOINCREMENT',
        'UNIQUE', 'CHECK', 'FOREIGN', 'REFERENCES', 'DEFAULT', 'NOTNULL',
    }

    return [c for c in all_cols if c.upper() not in sql_keywords and not c.upper().startswith('SQLITE_')]


def _extract_from_tables(sql: str) -> List[str]:
    """Extract table names from FROM and JOIN clauses."""
    tables = []

    from_matches = re.findall(r'FROM\s+(\w+)(?:\s+AS\s+\w+)?', sql, re.IGNORECASE)
    tables.extend(from_matches)

    join_matches = re.findall(r'JOIN\s+(\w+)(?:\s+AS\s+\w+)?', sql, re.IGNORECASE)
    tables.extend(join_matches)

    return [t.lower() for t in tables]


async def validator_node(state: Dict[str, Any]) -> Dict[str, Any]:
    sql = state["generated_sql"].strip()

    # 1. Security: Check for forbidden keywords
    upper_sql = sql.upper()
    for word in FORBIDDEN_KEYWORDS:
        if word in upper_sql:
            state["error"] = f"Security violation: {word} statements are not allowed. Only SELECT queries are permitted."
            state["valid"] = False
            return state

    # 2. Schema Validation: Check all referenced columns exist
    schema_cols = await _get_schema_columns()

    # Extract table references
    from_tables = _extract_from_tables(sql)

    # Validate FROM tables exist
    for table in from_tables:
        if table not in schema_cols:
            state["error"] = f"Schema error: Table '{table}' does not exist in database."
            state["valid"] = False
            return state

    # Extract table.column references
    col_refs = _extract_table_column_refs(sql)

    for table, col in col_refs:
        table_lower = table.lower()
        col_lower = col.lower()

        if table_lower not in schema_cols:
            continue

        if col_lower not in schema_cols[table_lower]:
            state["error"] = f"Schema error: Column '{table}.{col}' does not exist."
            state["valid"] = False
            return state

    # Validate BARE column references (skip aliases)
    bare_cols = _extract_bare_column_refs(sql)

    # Collect all valid columns from referenced tables
    valid_columns = set()
    for table in from_tables:
        if table in schema_cols:
            valid_columns.update(schema_cols[table])

    for col in bare_cols:
        col_lower = col.lower()
        if col_lower in {'count', 'sum', 'avg', 'max', 'min', 'abs', 'round', 'cast', 'coalesce', 'strftime', 'date_format', 'to_char', 'now', 'length', 'upper', 'lower', 'trim', 'replace', 'substr', 'instr'}:
            continue

        if col_lower not in valid_columns:
            if col_lower == 'id':
                state["error"] = f"Schema error: Column 'id' does not exist. Did you mean 'transaction_id'?"
            elif col_lower in ['name', 'color', 'budget_limit'] and 'categories' not in from_tables:
                state["error"] = f"Schema error: Column '{col}' only exists in table 'categories'."
            else:
                state["error"] = f"Schema error: Column '{col}' does not exist in table(s) {from_tables}."
            state["valid"] = False
            return state

    # Catch tags.name, tags.value, tags->> etc. (JSON hallucinations)
    json_hallucination_patterns = [
        r'\btags\.name\b',
        r'\btags\.value\b', 
        r'\btags\[[^\]]+\]',
        r'\btags\s*->>',
        r'\btags\s*#>',
    ]
    for pattern in json_hallucination_patterns:
        if re.search(pattern, sql, re.IGNORECASE):
            state["error"] = "Schema error: 'tags' is a comma-separated TEXT column, not JSON. Use tags LIKE '%value%'."
            state["valid"] = False
            return state

    # 3. Syntax: EXPLAIN query plan
    try:
        async with db_manager.engine.connect() as conn:
            await conn.execute(text(f"EXPLAIN QUERY PLAN {sql}"))
    except Exception as e:
        state["error"] = f"SQL syntax error: {str(e)}."
        state["valid"] = False
        return state

    # 4. Dry-run: Try to execute with LIMIT 1
    try: 
        test_sql = f"SELECT * FROM ({sql}) AS validation_query LIMIT 1"
        async with db_manager.engine.connect() as conn:
            await conn.execute(text(test_sql))
    except Exception as e:
        try:
            if "LIMIT" not in sql.upper():
                limited_sql = f"{sql.rstrip(';')} LIMIT 1"
                async with db_manager.engine.connect() as conn:
                    await conn.execute(text(limited_sql))
            else:
                async with db_manager.engine.connect() as conn:
                    await conn.execute(text(sql))
        except Exception as e2:
            state["error"] = f"Query execution error: {str(e2)}."
            state["valid"] = False
            return state

    state["valid"] = True
    state["error"] = None
    return state


