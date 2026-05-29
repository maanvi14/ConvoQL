"""SQL skeleton generator: Builds SQL from structured plan with dialect awareness."""
from typing import Dict, Any, List
import re

from db.connection import db_manager

# Dialect-specific date functions for entity linking
DATE_FUNCTIONS = {
    "sqlite": {
        "this_month": "strftime('%Y-%m', {col}) = strftime('%Y-%m', 'now')",
        "last_month": "strftime('%Y-%m', {col}) = strftime('%Y-%m', 'now', '-1 month')",
        "this_year": "strftime('%Y', {col}) = strftime('%Y', 'now')",
        "last_year": "strftime('%Y', {col}) = strftime('%Y', 'now', '-1 year')",
    },
    "mysql": {
        "this_month": "DATE_FORMAT({col}, '%Y-%m') = DATE_FORMAT(NOW(), '%Y-%m')",
        "last_month": "DATE_FORMAT({col}, '%Y-%m') = DATE_FORMAT(DATE_SUB(NOW(), INTERVAL 1 MONTH), '%Y-%m')",
        "this_year": "YEAR({col}) = YEAR(NOW())",
        "last_year": "YEAR({col}) = YEAR(NOW()) - 1",
    },
    "postgresql": {
        "this_month": "TO_CHAR({col}, 'YYYY-MM') = TO_CHAR(NOW(), 'YYYY-MM')",
        "last_month": "TO_CHAR({col}, 'YYYY-MM') = TO_CHAR(NOW() - INTERVAL '1 month', 'YYYY-MM')",
        "this_year": "EXTRACT(YEAR FROM {col}) = EXTRACT(YEAR FROM NOW())",
        "last_year": "EXTRACT(YEAR FROM {col}) = EXTRACT(YEAR FROM NOW()) - 1",
    }
}

# Column name mapping for common hallucinations
COLUMN_ALIASES = {
    "id": "transaction_id",
    "trans_id": "transaction_id",
    "txn_id": "transaction_id",
    "created_at": "date",
    "timestamp": "date",
    "value": "amount",
    "price": "amount",
    "cost": "amount",
    "expense": "amount",
}

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
    return _schema_cache


def _fix_hallucinated_columns(sql: str) -> str:
    """Fix common column hallucinations in generated SQL."""
    # Fix 1: id -> transaction_id
    for bad_col, good_col in COLUMN_ALIASES.items():
        pattern = r'(?<![\w.])' + re.escape(bad_col) + r'(?![\w])'
        if re.search(pattern, sql, re.IGNORECASE):
            sql = re.sub(pattern, good_col, sql, flags=re.IGNORECASE)

    # Fix 2: tags.name, tags.value -> tags (remove JSON notation)
    sql = re.sub(r'\btags\.name\b', 'tags', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\btags\.value\b', 'tags', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\btags\[[^\]]+\]', 'tags', sql, flags=re.IGNORECASE)

    # Fix 3: WHERE tags = 'x' -> WHERE tags LIKE '%x%'
    sql = re.sub(
        r"(?i)WHERE\s+(\w+)\s*=\s*['\"]([^'\"]+)['\"]",
        lambda m: f"WHERE {m.group(1)} LIKE '%{m.group(2)}%'" if m.group(1).lower() == 'tags' else m.group(0),
        sql
    )
    # Also fix AND tags = 'x'
    sql = re.sub(
        r"(?i)AND\s+(\w+)\s*=\s*['\"]([^'\"]+)['\"]",
        lambda m: f"AND {m.group(1)} LIKE '%{m.group(2)}%'" if m.group(1).lower() == 'tags' else m.group(0),
        sql
    )

    # Fix 4: Remove double commas and fix spacing
    sql = re.sub(r',\s*,', ',', sql)
    sql = re.sub(r'SELECT\s+,', 'SELECT ', sql, flags=re.IGNORECASE)
    sql = re.sub(r',\s+FROM', ' FROM', sql, flags=re.IGNORECASE)

    return sql


def build_sql_from_plan(plan: Dict[str, Any], entity_links: Dict[str, Any], 
                        intent: Dict[str, Any], dialect: str = "sqlite") -> str:
    """Build SQL query from structured plan. Deterministic, not LLM-based."""

    tables = plan.get("tables", ["transactions"])
    joins = plan.get("joins", [])
    select_cols = plan.get("select_columns", ["*"])
    where_filters = plan.get("where_filters", [])
    group_by = plan.get("group_by", [])
    order_by = plan.get("order_by")
    limit = plan.get("limit", 50)

    date_funcs = DATE_FUNCTIONS.get(dialect, DATE_FUNCTIONS["sqlite"])

    # FORCE SINGLE TABLE: If only transactions table, ignore all joins
    if len(tables) == 1 and tables[0].lower() == "transactions":
        joins = []

    # Build SELECT
    select_clause = ", ".join(select_cols)

    # Build FROM
    from_clause = tables[0]

    # Build JOINs (only if multiple tables)
    join_clauses = []
    if len(tables) > 1:
        for join in joins:
            if join and join.get("type") and join.get("right_table"):
                join_type = join["type"]
                right_table = join["right_table"]
                on_condition = join.get("on_condition", "")

                if on_condition:
                    if "categories.category" in on_condition.lower() or "category = category" in on_condition.lower():
                        continue
                    join_clauses.append(f"{join_type} {right_table} ON {on_condition}")
                else:
                    join_clauses.append(f"{join_type} {right_table}")

    # Build WHERE
    all_filters = list(where_filters)

    # Add type filter from intent if present and not already in filters
    type_filter = intent.get("type_filter") if intent else None
    if type_filter:
        type_filter_sql = f"type = '{type_filter}'"
        if not any(type_filter_sql.lower() in f.lower() for f in all_filters if isinstance(f, str)):
            all_filters.append(type_filter_sql)
    elif type_filter is None:
        # Explicitly remove any type filters if intent says null
        all_filters = [f for f in all_filters if not (isinstance(f, str) and "type =" in f.lower())]

    # Add entity-based filters from linked values
    for value_link in entity_links.get("linked_values", []):
        if isinstance(value_link, dict):
            vtype = value_link.get("type", "")
            vvalue = value_link.get("value", "")
            vcolumn = value_link.get("column", "")
            voperator = value_link.get("operator", "=")

            if vcolumn and vvalue:
                if vtype == "account":
                    all_filters.append(f"account = '{vvalue}'")
                elif vtype == "merchant":
                    all_filters.append(f"merchant = '{vvalue}'")
                elif vtype == "category":
                    all_filters.append(f"category = '{vvalue}'")
                elif vtype == "payment_method":
                    all_filters.append(f"payment_method = '{vvalue}'")
                elif vtype == "tag":
                    # CRITICAL: tags is comma-separated, use LIKE
                    all_filters.append(f"tags LIKE '%{vvalue}%'")
                elif voperator == "LIKE":
                    all_filters.append(f"{vcolumn} LIKE '%{vvalue}%'")
                else:
                    all_filters.append(f"{vcolumn} = '{vvalue}'")

    # Add entity-based date filters
    for date_ref in entity_links.get("linked_dates", []):
        dtype = date_ref["type"]
        if dtype in date_funcs:
            all_filters.append(date_funcs[dtype].format(col="date"))
        elif dtype == "this_year":
            all_filters.append(date_funcs["this_year"].format(col="date"))
        elif dtype == "last_year":
            all_filters.append(date_funcs["last_year"].format(col="date"))

    # DEDUPLICATE filters
    seen_filters = set()
    unique_filters = []
    for f in all_filters:
        if isinstance(f, str):
            normalized = f.strip().lower()
            if normalized not in seen_filters:
                seen_filters.add(normalized)
                unique_filters.append(f)
        else:
            unique_filters.append(f)

    where_clause = " AND ".join(unique_filters) if unique_filters else "1=1"

    # Build GROUP BY
    group_clause = ", ".join(group_by) if group_by else ""

    # Build ORDER BY
    order_clause = order_by if order_by else ""

    # Assemble SQL
    sql = f"SELECT {select_clause}\nFROM {from_clause}"

    for join_clause in join_clauses:
        sql += f"\n{join_clause}"

    sql += f"\nWHERE {where_clause}"

    if group_clause:
        sql += f"\nGROUP BY {group_clause}"

    if order_clause:
        sql += f"\nORDER BY {order_clause}"

    if limit:
        sql += f"\nLIMIT {limit}"

    return sql


async def sql_skeleton_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Generate SQL using structured plan + entity links + intent + dialect."""
    plan = state.get("structured_plan", {})
    entity_links = state.get("entity_links", {})
    intent = state.get("intent", {})
    dialect = state.get("dialect", "sqlite")

    # Build SQL deterministically
    sql = build_sql_from_plan(plan, entity_links, intent, dialect)

    # Validate basic structure
    sql_upper = sql.upper()
    if "SELECT" not in sql_upper:
        sql = "SELECT * FROM transactions LIMIT 50"

    # Apply hallucination fixes
    sql = _fix_hallucinated_columns(sql)

    # Ensure LIMIT exists
    if "LIMIT" not in sql.upper():
        sql = sql.rstrip(';') + "\nLIMIT 50"

    # Clean up whitespace
    sql = re.sub(r'\s+', ' ', sql).strip()
    if sql.endswith(";"):
        sql = sql[:-1].strip()

    return {
        **state,
        "generated_sql": sql,
        "error": None,
    }
