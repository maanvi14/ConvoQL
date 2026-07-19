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

    # Secondary fix: accounts.account -> accounts.account_name
    # (table-scoped so it does NOT clobber transactions.account, which is correct)
    sql = re.sub(r'\baccounts\.account\b(?!_name)', 'accounts.account_name', sql, flags=re.IGNORECASE)

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


def _normalize_col_for_compare(col: str) -> str:
    """Strip alias/table-prefix so 'transactions.date AS d' and 'date' compare equal."""
    c = col.strip().lower()
    c = c.split(" as ")[0].strip()
    if "." in c:
        c = c.split(".")[-1].strip()
    return c


_AGG_FUNCS = ("sum(", "count(", "avg(", "max(", "min(")


def _enforce_group_by_select_integrity(select_cols: List[str], group_by: List[str]) -> List[str]:
    """GENERAL FIX (Bug 5 hardening): whenever a query has GROUP BY, every
    SELECT expression must be either (a) one of the group_by columns, or
    (b) wrapped in an aggregate function (SUM/COUNT/AVG/MAX/MIN).

    This used to only be enforced for queries we heuristically detected as
    "budget joins" (`is_budget_query`). That's fragile: ANY grouped query
    with a stray raw column (date, description, amount, ...) hits the same
    SQLite quirk — non-aggregated, non-grouped columns silently return an
    arbitrary row's value per group instead of erroring, which is exactly
    what produced the per-transaction garbage rows under 'GROUP BY category'
    in the budget-comparison screenshot. This now runs for every grouped
    query, independent of whether budgets are involved.
    """
    if not group_by or not select_cols:
        return select_cols

    group_by_normalized = {
        _normalize_col_for_compare(g) for g in group_by if isinstance(g, str)
    }

    kept = []
    dropped = []
    for col in select_cols:
        if not isinstance(col, str):
            kept.append(col)
            continue
        col_stripped = col.strip()
        col_lower = col_stripped.lower()
        if col_lower == "*":
            # Handled separately by _sanitize_group_by
            kept.append(col)
            continue
        if any(agg in col_lower for agg in _AGG_FUNCS):
            kept.append(col)
            continue
        if _normalize_col_for_compare(col_stripped) in group_by_normalized:
            kept.append(col)
            continue
        dropped.append(col)

    if dropped:
        print(f"[SQLSkeleton] Dropping non-aggregated, non-grouped columns from grouped SELECT: {dropped}")

    if not kept:
        kept = list(group_by)

    # Ensure at least one aggregate remains so grouped "how much" questions
    # still get an answer even if the plan forgot to include one.
    if not any(any(agg in str(c).lower() for agg in _AGG_FUNCS) for c in kept):
        kept.append("COUNT(*) AS row_count")

    return kept


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

    is_budget_query = any("budget" in str(t).lower() for t in tables) or \
                       any("budget" in str(j.get("right_table", "")).lower() for j in joins)

    # === GENERAL FIX (Bug 5 hardening): enforce SELECT/GROUP BY integrity
    # for grouped queries that AREN'T budget joins. Budget queries get the
    # more surgical, budget-aware trim below instead — it already knows
    # `budgets.allocated` / `budgets.spent` are safe to keep (they're
    # functionally one-per-category once the join is date-aligned), whereas
    # this general check can't tell those apart from a stray raw column and
    # would strip them too.
    if group_by and not is_budget_query:
        select_cols = _enforce_group_by_select_integrity(select_cols, group_by)

    # === CRITICAL FIX (Bug 5): Trim SELECT for budgets JOIN queries ===
    if is_budget_query and group_by:
        detail_cols_to_drop = {
            "transactions.date", "transactions.description", "transactions.amount", "transactions.type",
            "t.date", "t.description", "t.amount", "t.type",
            "date", "description", "amount", "type"
        }
        new_select = []
        for col in select_cols:
            if isinstance(col, str):
                col_clean = col.strip().lower()
                # Check if it matches any of the detail columns
                if col_clean in detail_cols_to_drop:
                    continue
                # Also check if it's qualified or has alias, but matches the base column
                base_col = col_clean.split(" as ")[0].strip()
                # strip potential table qualification for check
                if "." in base_col:
                    base_col = base_col.split(".")[-1].strip()
                if base_col in detail_cols_to_drop:
                    continue
                new_select.append(col)
            else:
                new_select.append(col)
        
        # Ensure transactions.category (or equivalent) is present
        has_category = any("category" in str(c).lower() for c in new_select)
        if not has_category:
            new_select.insert(0, "transactions.category")
            
        # Ensure SUM(ABS(transactions.amount)) AS total_spent is present
        has_aggregate = any(any(agg in str(c).lower() for agg in ["sum", "total_spent"]) for c in new_select)
        if not has_aggregate:
            new_select.append("SUM(ABS(transactions.amount)) AS total_spent")
            
        select_cols = new_select

    select_clause = ", ".join(select_cols)
    from_clause = tables[0]

    join_clauses = []
    if len(tables) > 1:
        for join in joins:
            if join and join.get("right_table"):
                # BUG FIX: the planner's own JSON schema allows "type": null
                # (`"type": "LEFT JOIN" or "INNER JOIN" or null`). The old
                # check `join.get("type") and ...` silently dropped the ENTIRE
                # join whenever the LLM emitted null for type — no join, no
                # error, just a missing table in the query. Default sensibly
                # instead of dropping the join.
                join_type = join.get("type") or "INNER JOIN"
                right_table = join["right_table"]
                on_condition = join.get("on_condition", "") or ""

                # BUG FIX: this used to be an exact `right_table.lower() ==
                # "budgets"` match with no whitespace stripping. Any stray
                # space or an alias (e.g. "budgets b") from the LLM made this
                # comparison fail silently, so the month_year alignment clause
                # was never appended — which is exactly what produced the
                # unaligned `transactions.category = budgets.category` join
                # (and the resulting row-multiplication) seen in production.
                right_table_base = right_table.strip().lower().split(" as ")[0].split(" ")[0]

                # Automatically append month_year alignment for budgets join
                if right_table_base == "budgets" and "month_year" not in on_condition.lower():
                    if dialect == "mysql":
                        align_clause = "DATE_FORMAT(budgets.month_year, '%Y-%m') = DATE_FORMAT(transactions.date, '%Y-%m')"
                    elif dialect == "postgresql":
                        align_clause = "TO_CHAR(budgets.month_year, 'YYYY-MM') = TO_CHAR(transactions.date, 'YYYY-MM')"
                    else:  # sqlite
                        align_clause = "strftime('%Y-%m', budgets.month_year) = strftime('%Y-%m', transactions.date)"
                    
                    if on_condition:
                        on_condition = f"{on_condition} AND {align_clause}"
                    else:
                        on_condition = f"transactions.category = budgets.category AND {align_clause}"

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

    # ── BUG 3 FIX: Handle month_year / year_month linked_date entries ──────────
    # Check whether the entity_links contains a *specific* month_year or
    # year_month date entry (e.g. "March 2026" → sql_filter already computed).
    # If so, strip any generic "this_month" / "last_month" strftime filters that
    # may already be in all_filters from the planner, because they would produce
    # a contradictory AND (e.g. strftime(…,'now') AND strftime(…)='2026-03').
    _GENERIC_DATE_RE = re.compile(
        r"strftime\('%Y-%m',\s*(?:\w+\.)?date\)\s*=\s*strftime\('%Y-%m',\s*'now'",
        re.IGNORECASE
    )
    has_specific_date = any(
        d.get("type") in ("month_year", "year_month") and d.get("sql_filter")
        for d in entity_links.get("linked_dates", [])
    )
    if has_specific_date:
        all_filters = [
            f for f in all_filters
            if not (isinstance(f, str) and _GENERIC_DATE_RE.search(f))
        ]

    for date_ref in entity_links.get("linked_dates", []):
        dtype = date_ref["type"]
        if dtype in date_funcs:
            all_filters.append(date_funcs[dtype].format(col="date"))
        elif dtype == "this_year":
            all_filters.append(date_funcs["this_year"].format(col="date"))
        elif dtype == "last_year":
            all_filters.append(date_funcs["last_year"].format(col="date"))
        elif dtype in ("month_year", "year_month"):
            # BUG 3 FIX: Use the precomputed, authoritative sql_filter from
            # column_linker instead of silently dropping these entries.
            sql_filter = date_ref.get("sql_filter")
            if sql_filter:
                all_filters.append(sql_filter)

    # ── BUG 3 FIX: Semantic dedup — collapse table-qualified vs unqualified ──
    # Normalise each filter by stripping table-prefix from date column
    # (e.g. `transactions.date` → `date`) before comparing for duplicates.
    def _normalise_filter(f: str) -> str:
        """Normalise a filter string for dedup comparison."""
        return re.sub(r'\b\w+\.date\b', 'date', f.strip().lower(), flags=re.IGNORECASE)

    seen_filters: set = set()
    unique_filters = []
    for f in all_filters:
        if isinstance(f, str):
            normalized = _normalise_filter(f)
            if normalized not in seen_filters:
                seen_filters.add(normalized)
                unique_filters.append(f)
        else:
            unique_filters.append(f)

    where_clause = " AND ".join(unique_filters) if unique_filters else "1=1"

    # ── BUG 4 FIX: Strip trailing 'AS alias' from every GROUP BY entry ────────
    # SQLite does NOT allow 'AS alias' inside GROUP BY. The planner LLM sometimes
    # emits `group_by: ["strftime('%Y-%m', date) AS month"]`.
    sanitized_group_by = [
        re.sub(r'(?i)\s+AS\s+\w+\s*$', '', g).strip()
        for g in group_by
        if isinstance(g, str)
    ]
    group_clause = ", ".join(sanitized_group_by) if sanitized_group_by else ""
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
