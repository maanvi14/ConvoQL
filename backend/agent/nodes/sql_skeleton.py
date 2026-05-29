"""SQL skeleton generator: Builds SQL from structured plan with dialect awareness."""
from typing import Dict, Any, List
import json
import re

from config import get_settings
from db.connection import db_manager

settings = get_settings()

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


def _validate_join_condition(join_condition: str, schema_cols: Dict[str, List[str]]) -> bool:
    """Validate that a JOIN condition references actual columns."""
    if not join_condition:
        return False

    # Extract column references like table.column
    col_refs = re.findall(r'\b(\w+)\.(\w+)\b', join_condition)

    for table, col in col_refs:
        table_lower = table.lower()
        col_lower = col.lower()

        if table_lower not in schema_cols:
            print(f"[SQLBuilder] Invalid JOIN: table '{table}' not in schema")
            return False
        if col_lower not in schema_cols[table_lower]:
            print(f"[SQLBuilder] Invalid JOIN: column '{table}.{col}' not in schema")
            return False

    return True


def _clean_invalid_columns(sql: str, schema_cols: Dict[str, List[str]]) -> str:
    """Remove SELECT columns that don't exist in schema."""
    # Parse SELECT clause
    select_match = re.search(r'SELECT\s+(.*?)\s+FROM', sql, re.IGNORECASE | re.DOTALL)
    if not select_match:
        return sql

    select_part = select_match.group(1)

    # Split by comma, handling aliases
    cols = []
    current = ""
    paren_depth = 0
    for char in select_part:
        if char == '(':
            paren_depth += 1
        elif char == ')':
            paren_depth -= 1
        elif char == ',' and paren_depth == 0:
            cols.append(current.strip())
            current = ""
            continue
        current += char
    if current.strip():
        cols.append(current.strip())

    valid_cols = []
    for col in cols:
        col_clean = col.strip()
        # Skip * and aggregates
        if col_clean == '*' or '(' in col_clean:
            valid_cols.append(col_clean)
            continue

        # Check for table.column format
        if '.' in col_clean:
            parts = col_clean.split('.')
            if len(parts) == 2:
                table, col_name = parts[0], parts[1]
                table_lower = table.lower().strip()
                col_lower = col_name.lower().strip()

                # Remove alias if present
                if ' AS ' in col_lower:
                    col_lower = col_lower.split(' AS ')[0].strip()

                if table_lower in schema_cols and col_lower in schema_cols[table_lower]:
                    valid_cols.append(col_clean)
                else:
                    print(f"[SQLBuilder] Removing invalid column: {col_clean}")
            else:
                valid_cols.append(col_clean)
        else:
            valid_cols.append(col_clean)

    if not valid_cols:
        valid_cols = ["*"]

    new_select = ", ".join(valid_cols)
    sql = sql.replace(select_part, new_select, 1)
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
        print("[SQLBuilder] Single transactions table — ignoring all JOINs")

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
                        print(f"[SQLBuilder] Skipping invalid join condition: {on_condition}")
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
        if len(all_filters) < len(where_filters):
            print("[SQLBuilder] Intent type_filter is null — removing all type filters")

    # Add entity-based filters from linked values
    for value_link in entity_links.get("linked_values", []):
        if isinstance(value_link, dict):
            vtype = value_link.get("type", "")
            vvalue = value_link.get("value", "")
            vcolumn = value_link.get("column", "")

            if vcolumn and vvalue:
                if vtype == "account":
                    all_filters.append(f"account = '{vvalue}'")
                elif vtype == "merchant":
                    all_filters.append(f"merchant = '{vvalue}'")
                elif vtype == "category":
                    all_filters.append(f"category = '{vvalue}'")
                elif vtype == "payment_method":
                    all_filters.append(f"payment_method = '{vvalue}'")

    # Add entity-based date filters
    for date_ref in entity_links.get("linked_dates", []):
        dtype = date_ref["type"]
        if dtype in date_funcs:
            all_filters.append(date_funcs[dtype].format(col="date"))
        elif dtype == "this_year":
            all_filters.append(date_funcs["this_year"].format(col="date"))
        elif dtype == "last_year":
            all_filters.append(date_funcs["last_year"].format(col="date"))

    # DEDUPLICATE filters before building WHERE clause
    seen_filters = set()
    unique_filters = []
    for f in all_filters:
        if isinstance(f, str):
            # Normalize: strip whitespace, lowercase for comparison
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

    # === SCHEMA-AWARE VALIDATION ===
    schema_cols = await _get_schema_columns()

    # 1. Validate and clean JOINs
    if "JOIN" in sql.upper():
        lines = sql.split("\n")
        cleaned_lines = []
        for line in lines:
            if "JOIN" in line.upper():
                # Extract ON condition
                on_match = re.search(r'ON\s+(.+)', line, re.IGNORECASE)
                if on_match:
                    on_condition = on_match.group(1)
                    if not _validate_join_condition(on_condition, schema_cols):
                        print(f"[SQLBuilder] Removing invalid JOIN: {line.strip()}")
                        continue
            cleaned_lines.append(line)
        sql = "\n".join(cleaned_lines)

    # 2. Clean invalid columns from SELECT
    sql = _clean_invalid_columns(sql, schema_cols)

    # 3. Final safety checks
    # Remove self-joins (JOINing a table to itself)
    if "JOIN transactions ON transactions" in sql.lower():
        print("[SQLBuilder] Removing self-join on transactions")
        sql = re.sub(r'\s*(?:LEFT|INNER|RIGHT)?\s*JOIN\s+transactions\s+ON\s+.*?\n', '\n', sql, flags=re.IGNORECASE)

    # Remove JOINs with made-up columns
    invalid_patterns = [
        (r'budgets\.id', 'budgets.id'),
        (r'transactions\.budget_id', 'transactions.budget_id'),
        (r'categories\.id', 'categories.id'),
        (r'categories\.color', 'categories.color'),
        (r'categories\.name', 'categories.name'),
    ]

    for pattern, desc in invalid_patterns:
        if re.search(pattern, sql, re.IGNORECASE):
            print(f"[SQLBuilder] Found invalid column reference: {desc}")
            # Remove the entire JOIN clause containing this
            lines = sql.split("\n")
            cleaned = []
            skip_next = False
            for line in lines:
                if re.search(pattern, line, re.IGNORECASE):
                    skip_next = True
                    continue
                if skip_next and line.strip().startswith("ON"):
                    skip_next = False
                    continue
                cleaned.append(line)
            sql = "\n".join(cleaned)

    # 4. If JOINs were removed and we now have a single table, clean up
    if "JOIN" not in sql.upper() and "FROM transactions" in sql.upper():
        # Remove any remaining table prefixes in SELECT
        sql = re.sub(r'transactions\.', '', sql)
        sql = re.sub(r'categories\.', '', sql)
        sql = re.sub(r'budgets\.', '', sql)
        sql = re.sub(r'accounts\.', '', sql)

    return {
        **state,
        "generated_sql": sql,
        "error": None,
    }
