"""SQL skeleton generator: Builds SQL from structured plan with dialect awareness."""
from typing import Dict, Any, List
import re

from db.connection import db_manager

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

_schema_cache = None

async def _get_schema_columns() -> Dict[str, List[str]]:
    global _schema_cache
    if _schema_cache is None:
        schema = await db_manager.get_schema()
        _schema_cache = {}
        for table in schema.get("tables", []):
            table_name = table["name"].lower()
            _schema_cache[table_name] = [col["name"].lower() for col in table.get("columns", [])]
    return _schema_cache


def _fix_hallucinated_columns(sql: str) -> str:
    for bad_col, good_col in COLUMN_ALIASES.items():
        pattern = r'(?<![\w.])' + re.escape(bad_col) + r'(?![\w])'
        if re.search(pattern, sql, re.IGNORECASE):
            sql = re.sub(pattern, good_col, sql, flags=re.IGNORECASE)

    sql = re.sub(r'\btags\.name\b', 'tags', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\btags\.value\b', 'tags', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\btags\[[^\]]+\]', 'tags', sql, flags=re.IGNORECASE)

    sql = re.sub(
        r"(?i)WHERE\s+(\w+)\s*=\s*['\"]([^'\"]+)['\"]",
        lambda m: f"WHERE {m.group(1)} LIKE '%{m.group(2)}%'" if m.group(1).lower() == 'tags' else m.group(0),
        sql
    )
    sql = re.sub(
        r"(?i)AND\s+(\w+)\s*=\s*['\"]([^'\"]+)['\"]",
        lambda m: f"AND {m.group(1)} LIKE '%{m.group(2)}%'" if m.group(1).lower() == 'tags' else m.group(0),
        sql
    )

    sql = re.sub(r',\s*,', ',', sql)
    sql = re.sub(r'SELECT\s+,', 'SELECT ', sql, flags=re.IGNORECASE)
    sql = re.sub(r',\s+FROM', ' FROM', sql, flags=re.IGNORECASE)

    return sql


def _enforce_abs_for_debits(sql: str, intent: Dict[str, Any]) -> str:
    """CRITICAL: Ensure ABS(amount) is used for debit/spending queries in skeleton SQL."""
    type_filter = intent.get("type_filter") if intent else None
    sql_lower = sql.lower()

    is_debit_query = (type_filter == "debit" or 
                      "type = 'debit'" in sql_lower or 
                      'type="debit"' in sql_lower)

    if is_debit_query:
        sql = re.sub(r'(?i)SUM\s*\(\s*amount\s*\)', 'SUM(ABS(amount))', sql)
        sql = re.sub(r'(?i)ORDER\s+BY\s+amount\s+DESC', 'ORDER BY ABS(amount) DESC', sql)
        sql = re.sub(r'(?i)ORDER\s+BY\s+amount\s+ASC', 'ORDER BY ABS(amount) ASC', sql)
        sql = re.sub(r'(?i)MAX\s*\(\s*amount\s*\)', 'MAX(ABS(amount))', sql)
        sql = re.sub(r'(?i)AVG\s*\(\s*amount\s*\)', 'AVG(ABS(amount))', sql)

    return sql


def _sanitize_group_by(sql: str, group_by: List[str]) -> str:
    """CRITICAL FIX: SQLite does not allow SELECT * with GROUP BY, and GROUP BY * is invalid syntax.

    Cases handled:
    1. group_by contains ["*"] -> remove GROUP BY entirely
    2. SELECT * with any GROUP BY -> remove GROUP BY (can't group by *)
    3. GROUP BY with columns not in SELECT -> SQLite may error
    """
    if not group_by:
        return sql

    # Case 1: group_by is literally ["*"] or contains "*"
    if any(g.strip() == "*" for g in group_by if isinstance(g, str)):
        sql = re.sub(r'(?i)\s+GROUP\s+BY\s+[^\n]+', '', sql)
        return sql

    # Case 2: SELECT * with GROUP BY (any columns) - SQLite requires explicit columns
    select_star_match = re.search(r'(?i)SELECT\s+\*\s+FROM', sql)
    if select_star_match:
        sql = re.sub(r'(?i)\s+GROUP\s+BY\s+[^\n]+', '', sql)
        return sql

    return sql


def build_sql_from_plan(plan: Dict[str, Any], entity_links: Dict[str, Any], 
                        intent: Dict[str, Any], dialect: str = "sqlite") -> str:
    tables = plan.get("tables", ["transactions"])
    joins = plan.get("joins", [])
    select_cols = plan.get("select_columns", ["*"])
    where_filters = plan.get("where_filters", [])
    group_by = plan.get("group_by", [])
    order_by = plan.get("order_by")
    limit = plan.get("limit", 50)

    date_funcs = DATE_FUNCTIONS.get(dialect, DATE_FUNCTIONS["sqlite"])

    if len(tables) == 1 and tables[0].lower() == "transactions":
        joins = []

    select_clause = ", ".join(select_cols)
    from_clause = tables[0]

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

    all_filters = list(where_filters)

    type_filter = intent.get("type_filter") if intent else None

    # === CRITICAL FIX: NEVER add type filter for tag/merchant/listing searches ===
    question = (intent.get("original_question") or "").lower()
    is_listing_query = any(w in question for w in ["show all", "show me all", "find all", "list all", "get all", "all transactions"])
    is_tag_search = any(w in question for w in ["tag", "tagged", "subscription", "label"])
    is_merchant_search = any(w in question for w in ["from uber", "from amazon", "merchant"])

    # For listing/tag/merchant queries: NEVER add type filter
    should_skip_type_filter = is_listing_query or is_tag_search or is_merchant_search

    if type_filter and not should_skip_type_filter:
        type_filter_sql = f"type = '{type_filter}'"
        if not any(type_filter_sql.lower() in f.lower() for f in all_filters if isinstance(f, str)):
            all_filters.append(type_filter_sql)
    elif type_filter is None or should_skip_type_filter:
        # Remove ANY type filter for tag/merchant/listing searches or when type_filter is null
        all_filters = [f for f in all_filters if not (isinstance(f, str) and "type =" in f.lower())]

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
                    all_filters.append(f"tags LIKE '%{vvalue}%'")
                elif voperator == "LIKE":
                    all_filters.append(f"{vcolumn} LIKE '%{vvalue}%'")
                else:
                    all_filters.append(f"{vcolumn} = '{vvalue}'")

    for date_ref in entity_links.get("linked_dates", []):
        dtype = date_ref["type"]
        if dtype in date_funcs:
            all_filters.append(date_funcs[dtype].format(col="date"))
        elif dtype == "this_year":
            all_filters.append(date_funcs["this_year"].format(col="date"))
        elif dtype == "last_year":
            all_filters.append(date_funcs["last_year"].format(col="date"))

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
    group_clause = ", ".join(group_by) if group_by else ""
    order_clause = order_by if order_by else ""

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
    plan = state.get("structured_plan", {})
    entity_links = state.get("entity_links", {})
    intent = state.get("intent", {})
    dialect = state.get("dialect", "sqlite")

    sql = build_sql_from_plan(plan, entity_links, intent, dialect)

    sql_upper = sql.upper()
    if "SELECT" not in sql_upper:
        sql = "SELECT * FROM transactions LIMIT 50"

    sql = _fix_hallucinated_columns(sql)
    sql = _enforce_abs_for_debits(sql, intent)

    # === CRITICAL FIX: Sanitize GROUP BY issues ===
    group_by = plan.get("group_by", [])
    sql = _sanitize_group_by(sql, group_by)

    if "LIMIT" not in sql.upper():
        sql = sql.rstrip(';') + "\nLIMIT 50"

    sql = re.sub(r'\s+', ' ', sql).strip()
    if sql.endswith(";"):
        sql = sql[:-1].strip()

    return {
        **state,
        "generated_sql": sql,
        "error": None,
    }
