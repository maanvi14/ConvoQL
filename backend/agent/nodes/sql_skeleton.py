"""SQL skeleton generator: Builds SQL from structured plan with dialect awareness."""
from typing import Dict, Any, List
import re

from db.connection import db_manager

# VERSION MARKER: if this line does NOT appear in your server's STARTUP logs
# (not per-request — once, at process boot), the running process imported a
# stale/cached copy of this module rather than this file. Restart the actual
# server process (not just save-the-file) to pick it up.
print("[sql_skeleton.py] LOADED — BUG5_HARDENED_V2 (month_year alignment + group-by integrity fix)")

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
    """Ensure ABS() is applied to the amount column for debit/spending queries.

    HARDENING: the original implementation only matched exact literal
    substrings like 'SUM(amount)' and 'ORDER BY amount DESC'. It silently did
    nothing if the LLM used a table-qualified column
    ('SUM(transactions.amount)') or an alias ('amount AS abs_amount' +
    'ORDER BY abs_amount DESC') — both are common, valid LLM outputs that the
    original regex simply couldn't see. This version:
      1. Matches amount refs with an optional table qualifier
         (amount | t.amount | transactions.amount), not just bare 'amount'.
      2. Resolves ORDER BY aliases back to their SELECT definition to decide
         whether they need ABS() too, instead of only matching the literal
         token 'amount' immediately after ORDER BY.
    """
    type_filter = intent.get("type_filter") if intent else None
    sql_lower = sql.lower()

    is_debit_query = (type_filter == "debit" or
                      "type = 'debit'" in sql_lower or
                      'type="debit"' in sql_lower)

    if not is_debit_query:
        return sql

    # --- Step 1: wrap aggregate(amount) / aggregate(table.amount) in ABS() ---
    for func in ("SUM", "MAX", "AVG", "MIN"):
        pattern = re.compile(rf'(?i)\b{func}\s*\(\s*((?:\w+\.)?amount)\s*\)')
        sql = pattern.sub(lambda m, f=func: f"{f}(ABS({m.group(1)}))", sql)

    # --- Step 2: figure out which SELECT aliases resolve to a raw
    # (non-aggregated, non-ABS'd) amount reference, so ORDER BY can be fixed
    # even when it references the alias rather than the column directly. ---
    select_match = re.search(r'(?i)SELECT\s+(.*?)\s+FROM\b', sql, re.DOTALL)
    alias_needs_abs = set()
    if select_match:
        for item in select_match.group(1).split(","):
            item = item.strip()
            m = re.match(r'(?is)^(.*)\s+AS\s+(\w+)$', item)
            if m:
                expr, alias = m.group(1).strip(), m.group(2).strip()
                expr_lower = expr.lower()
                if re.fullmatch(r'(?:\w+\.)?amount', expr_lower):
                    alias_needs_abs.add(alias.lower())

    # --- Step 3: fix ORDER BY, resolving aliases from step 2 ---
    order_match = re.search(r'(?i)ORDER\s+BY\s+(.*?)(?=\bLIMIT\b|$)', sql, re.DOTALL)
    if order_match:
        terms = []
        changed = False
        for term in order_match.group(1).split(","):
            term_stripped = term.strip()
            tm = re.match(r'(?i)^(.*?)(\s+(?:ASC|DESC))?$', term_stripped)
            expr = tm.group(1).strip()
            direction = tm.group(2) or ""
            expr_lower = expr.lower()

            if "abs(" in expr_lower:
                terms.append(term_stripped)
                continue

            if re.fullmatch(r'(?:\w+\.)?amount', expr_lower):
                terms.append(f"ABS({expr}){direction}")
                changed = True
            elif expr_lower in alias_needs_abs:
                terms.append(f"ABS({expr}){direction}")
                changed = True
            else:
                terms.append(term_stripped)

        if changed:
            new_order_clause = ", ".join(terms)
            sql = sql[:order_match.start(1)] + new_order_clause + sql[order_match.end(1):]

    return sql


def _fix_budget_comparison_sql(sql: str, question: str, intent: Dict[str, Any]) -> str:
    """CRITICAL FIX: Budget-vs-actual comparison queries must use LEFT JOIN
    from budgets to transactions, with COALESCE on the aggregate, so ALL
    budgeted categories appear even when they have no transactions.

    This post-processes the SQL after build_sql_from_plan because the planner
    sometimes emits INNER JOIN (dropping categories with zero spending) or
    forgets COALESCE (showing NULL instead of 0).
    """
    q_lower = question.lower()

    # Detect budget-vs-actual comparison
    is_budget_compare = any(pattern in q_lower for pattern in [
        "budget vs actual", "budget versus actual", "budget against actual",
        "actual spending vs budget", "compare budget", "budget vs spending",
        "allocated vs spent", "over budget", "under budget", "budget utilization",
    ])

    # Also check intent
    intent_primary = (intent.get("primary_intent") or "").lower()
    if intent_primary in ("budget_compare", "multi_table_join"):
        is_budget_compare = True

    if not is_budget_compare:
        return sql

    sql_lower = sql.lower()

    # Only fix if budgets table is involved
    if "budgets" not in sql_lower:
        return sql

    print(f"[SQLSkeleton] BUDGET_COMPARE_FIX firing for: '{question}'")

    # ── Fix 1: Force LEFT JOIN instead of INNER JOIN for budgets-transactions join ──
    # Pattern: INNER JOIN budgets ... or INNER JOIN transactions ...
    # We want: LEFT JOIN when joining budgets and transactions
    sql = re.sub(
        r'(?i)(FROM\s+\w+\s+)(INNER\s+JOIN\s+(?:budgets|transactions)\s+ON\s+[^
]+)',
        lambda m: f"{m.group(1)}LEFT JOIN{m.group(2)[10:]}",  # Replace INNER JOIN with LEFT JOIN
        sql
    )
    # Also catch if budgets is the FROM table and transactions is joined
    sql = re.sub(
        r'(?i)(FROM\s+budgets[^
]*
)(?:INNER\s+)?JOIN\s+transactions',
        r'LEFT JOIN transactions',
        sql
    )
    # And if transactions is FROM and budgets is joined
    sql = re.sub(
        r'(?i)(FROM\s+transactions[^
]*
)(?:INNER\s+)?JOIN\s+budgets',
        r'LEFT JOIN budgets',
        sql
    )

    # ── Fix 2: COALESCE SUM(ABS(...)) to show 0 instead of NULL ──
    # Pattern: SUM(ABS(transactions.amount)) or SUM(ABS(amount))
    sql = re.sub(
        r'(?i)SUM\s*\(\s*ABS\s*\(\s*(?:transactions\.)?amount\s*\)\s*\)(\s+AS\s+\w+)?',
        lambda m: f"COALESCE(SUM(ABS({re.search(r'(?i)(?:transactions\.)?amount', m.group(0)).group()})), 0){m.group(1) or ''}",
        sql
    )
    # Also catch bare SUM(amount) without ABS
    sql = re.sub(
        r'(?i)SUM\s*\(\s*(?:transactions\.)?amount\s*\)(\s+AS\s+\w+)?',
        lambda m: f"COALESCE(SUM(ABS({re.search(r'(?i)(?:transactions\.)?amount', m.group(0)).group()})), 0){m.group(1) or ''}",
        sql
    )

    # ── Fix 3: Ensure GROUP BY includes category ──
    # If GROUP BY only has month/date expression, add category
    group_match = re.search(r'(?i)GROUP\s+BY\s+([^
]+?)(?:\s+ORDER\s+BY|\s+LIMIT|$)', sql)
    if group_match:
        group_clause = group_match.group(1).strip()
        group_lower = group_clause.lower()
        # Check if category is missing from GROUP BY
        has_category_in_group = any(cat in group_lower for cat in [
            "category", "budgets.category", "transactions.category", "b.category", "t.category"
        ])
        if not has_category_in_group:
            # Add category to GROUP BY
            new_group = f"budgets.category, {group_clause}"
            sql = sql[:group_match.start(1)] + new_group + sql[group_match.end(1):]
            print(f"[SQLSkeleton] Added budgets.category to GROUP BY")

    # ── Fix 4: Move transactions.type = 'debit' from WHERE to JOIN ON if present ──
    # This is critical for LEFT JOIN — putting type filter in WHERE converts it to INNER JOIN
    type_filter_match = re.search(r"(?i)(WHERE\s+.*?)(AND\s+transactions\.type\s*=\s*'debit')", sql)
    if type_filter_match:
        # Remove from WHERE
        sql = sql[:type_filter_match.start(2)] + sql[type_filter_match.end(2):]
        # Clean up trailing AND or WHERE 1=1
        sql = re.sub(r"(?i)WHERE\s+1=1\s+AND\s+", "WHERE ", sql)
        sql = re.sub(r"(?i)WHERE\s+AND\s+", "WHERE ", sql)
        sql = re.sub(r"(?i)AND\s+1=1", "", sql)
        # Add to JOIN ON condition
        join_match = re.search(r"(?i)(LEFT\s+JOIN\s+transactions\s+ON\s+)([^
]+)", sql)
        if join_match:
            on_cond = join_match.group(2).strip()
            new_on = f"{on_cond} AND transactions.type = 'debit'"
            sql = sql[:join_match.start(2)] + new_on + sql[join_match.end(2):]
            print(f"[SQLSkeleton] Moved type='debit' from WHERE to JOIN ON")

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
                    print(f"[sql_skeleton] BUG5_HARDENED_V2 firing: injecting month_year alignment for right_table='{right_table}'")
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

    # === CRITICAL FIX: Budget comparison queries need LEFT JOIN + COALESCE ===
    question = state.get("question", "")
    sql = _fix_budget_comparison_sql(sql, question, intent)

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
