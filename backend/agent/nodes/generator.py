"""Generator node: Creates SQL from natural language with dialect awareness.

NOTE: This module is NOT currently wired into the LangGraph pipeline in
graph.py. The live path goes through structured_planner → sql_skeleton
instead. This file is preserved as an alternative, LLM-direct SQL generation
approach that could be wired in as a documented fallback strategy, e.g.:

    workflow.add_conditional_edges(
        "typed_error_classifier",
        route_after_error_classification,
        {
            "sql_skeleton": "sql_skeleton",
            "generator": "generator",          # <-- optional fallback
            "result_set_validator": "result_set_validator",
        }
    )

Do NOT import generator_node into graph.py unless you intend to wire it in.
Leaving it imported-but-unused would cause an unnecessary ChatGroq
instantiation on every module load.

Also note: _fix_group_by() in this file only handles the case of a bare
`date` column missing from GROUP BY. It is only called from generator_node
(which is currently unreachable), so it has no effect on the live pipeline.
"""
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from typing import Dict, Any, List
import re

from config import get_settings
from db.connection import db_manager

settings = get_settings()

# Dialect-specific date function examples - WITH ROLLING WINDOWS
DIALECT_EXAMPLES = {
    "sqlite": {
        "this_month": "strftime('%Y-%m', date) = strftime('%Y-%m', 'now')",
        "last_month": "strftime('%Y-%m', date) = strftime('%Y-%m', 'now', '-1 month')",
        "last_3_months": "date >= date('now', '-3 months')",
        "last_6_months": "date >= date('now', '-6 months')",
        "last_year": "date >= date('now', '-1 year')",
        "date_format": "strftime('%Y-%m', date)",
        "year_month": "strftime('%Y-%m', date)",
        "date_parse": "date",
    },
    "mysql": {
        "this_month": "DATE_FORMAT(date, '%Y-%m') = DATE_FORMAT(NOW(), '%Y-%m')",
        "last_month": "DATE_FORMAT(date, '%Y-%m') = DATE_FORMAT(DATE_SUB(NOW(), INTERVAL 1 MONTH), '%Y-%m')",
        "last_3_months": "date >= DATE_SUB(NOW(), INTERVAL 3 MONTH)",
        "last_6_months": "date >= DATE_SUB(NOW(), INTERVAL 6 MONTH)",
        "last_year": "date >= DATE_SUB(NOW(), INTERVAL 1 YEAR)",
        "date_format": "DATE_FORMAT(date, '%Y-%m')",
        "year_month": "DATE_FORMAT(date, '%Y-%m')",
        "date_parse": "date",
    },
    "postgresql": {
        "this_month": "TO_CHAR(date, 'YYYY-MM') = TO_CHAR(NOW(), 'YYYY-MM')",
        "last_month": "TO_CHAR(date, 'YYYY-MM') = TO_CHAR(NOW() - INTERVAL '1 month', 'YYYY-MM')",
        "last_3_months": "date >= NOW() - INTERVAL '3 months'",
        "last_6_months": "date >= NOW() - INTERVAL '6 months'",
        "last_year": "date >= NOW() - INTERVAL '1 year'",
        "date_format": "TO_CHAR(date, 'YYYY-MM')",
        "year_month": "TO_CHAR(date, 'YYYY-MM')",
        "date_parse": "date::date",
    }
}

COLUMN_ALIASES = {
    "id": "transaction_id",
    "trans_id": "transaction_id",
    "txn_id": "transaction_id",
    "user_id": None,
    "customer_id": None,
    "created_at": "date",
    "timestamp": "date",
    "value": "amount",
    "price": "amount",
    "cost": "amount",
    "expense": "amount",
    "total": None,
    "sum": None,
}

TABLE_COLUMNS: Dict[str, List[str]] = {}


async def _load_schema_from_db() -> str:
    """Fetch actual schema from database for LLM grounding."""
    schema = await db_manager.get_schema()
    schema_lines = []

    for table in schema.get("tables", []):
        table_name = table["name"]
        cols = table.get("columns", [])
        TABLE_COLUMNS[table_name] = [c["name"] for c in cols]

        col_defs = []
        for col in cols:
            col_name = col["name"]
            col_type = col.get("type", "TEXT")
            if col_name == "amount":
                col_defs.append(f"    {col_name} {col_type}  -- NEGATIVE for debits (expenses), POSITIVE for credits (income)")
            elif col_name == "type":
                col_defs.append(f"    {col_name} {col_type}  -- 'debit' or 'credit'")
            else:
                col_defs.append(f"    {col_name} {col_type}")

        schema_lines.append(f"CREATE TABLE {table_name} (\n" + ",\n".join(col_defs) + "\n);")

    return "\n\n".join(schema_lines)


TAGS_COLUMN_RULES = """
=== SPECIAL COLUMN: tags ===
The `tags` column is a COMMA-SEPARATED TEXT string, NOT a JSON object or sub-table.
Examples of tags values:
  'subscription'
  'subscription,health'
  'electronics,anomaly,big'
  'salary,monthly,raise'

To filter by tag, ALWAYS use: tags LIKE '%tag_name%'
NEVER use: tags.name = 'tag_name'
NEVER use: tags = 'tag_name'
"""

SIGN_CONVENTION_RULES = """
=== CRITICAL: AMOUNT SIGN CONVENTION ===
The `amount` column uses SIGNED values:
  - Debits (expenses, purchases, payments): NEGATIVE values (e.g., -28000.00, -4500.00)
  - Credits (income, salary, deposits): POSITIVE values (e.g., 80000.00, 5000.00)

THEREFORE:
1. For spending/expense analysis: ALWAYS use ABS(amount) in aggregations and ORDER BY
   CORRECT: SUM(ABS(amount)), ORDER BY ABS(amount) DESC
   WRONG: SUM(amount), MAX(amount), ORDER BY amount DESC (sorts debits at bottom!)

2. For income analysis: Use amount directly (no ABS needed)
   CORRECT: SUM(amount) for total income

3. For "highest expense": ORDER BY ABS(amount) DESC LIMIT 1
   For "highest income": ORDER BY amount DESC LIMIT 1

4. NEVER filter with amount > 0 or amount < 0 to determine debit/credit.
   ALWAYS use: type = 'debit' or type = 'credit'
   WRONG: WHERE amount > 0 (this filters OUT all debits!)
   WRONG: WHERE amount < 0 (this filters OUT all credits!)
"""

# ROLLING WINDOW DATE RULES - CLEAR INSTRUCTIONS
DATE_FILTER_RULES = """
=== DATE FILTER RULES ===
For time-based queries, use the CORRECT date range:
- "this month" or "current month": {date_this_month}
- "last month" or "previous month": {date_last_month}
- "last 3 months" or "past 3 months": {date_last_3_months}
- "last 6 months" or "past 6 months" or "last six months": {date_last_6_months}
- "last year" or "past year": {date_last_year}
- For specific months like "March 2026": strftime('%Y-%m', date) = '2026-03'
- NEVER combine rolling window (last 6 months) with specific month filter — use ONLY one
- The date column stores dates as TEXT in 'YYYY-MM-DD' format
- CRITICAL: For rolling windows (last N months), use >= comparison, NOT = comparison
  CORRECT: date >= date('now', '-6 months')
  WRONG: strftime('%Y-%m', date) = strftime('%Y-%m', 'now', '-6 months')
"""

GENERATOR_PROMPT = """You are an expert {dialect} SQL generator. You write ONLY correct, executable {dialect} queries.

=== EXACT DATABASE SCHEMA (use these exact column names, NEVER hallucinate) ===
{exact_schema}

{sample_data}

{tags_rules}

{sign_rules}

{date_rules}

USER QUESTION: {question}

PREVIOUS ERROR (if any): {error}
RETRY INSTRUCTION (if any): {retry_hint}

DETECTED INTENT:
- Primary: {primary_intent}
- Type Filter: {type_filter}
- Time Dimension: {time_dimension}
- Aggregation: {aggregation_type}
- Dialect: {dialect}

=== CRITICAL RULES ===
1. ONLY SELECT statements. NEVER INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE, GRANT.
2. Use ONLY column names from the schema above. NEVER make up columns.
3. For "highest expense", "biggest purchase", "most expensive": ALWAYS use: ORDER BY ABS(amount) DESC LIMIT 1
   NEVER use MAX(amount) because debit amounts are negative.
4. For expenses/spending: ALWAYS filter with type = 'debit' AND use ABS(amount) in SELECT
5. For income: ALWAYS filter with type = 'credit' AND use amount directly (no ABS)
6. SINGLE TABLE PREFERENCE: The transactions table has ALL needed columns. DO NOT JOIN unless question explicitly asks for data from other tables.
7. Date filtering: use {dialect} date functions
8. This month: {date_this_month}
9. Last month: {date_last_month}
10. Last 3 months: {date_last_3_months}
11. Last 6 months: {date_last_6_months}
12. Last year: {date_last_year}
13. LIMIT: Use LIMIT 50 unless user asks for specific number.
14. NEVER compare dates from different tables directly. Normalize both with date function.
15. TYPE FILTER RULE: Only add type = 'debit' or type = 'credit' when the question EXPLICITLY asks for expenses or income. NEVER add type filter for tag, category, or merchant searches.
16. COLUMN NAMES: Use exact names from schema. If a table has transaction_id, NEVER use id.
17. TAG FILTERING: The tags column is comma-separated TEXT. Use tags LIKE '%value%' — NEVER tags.name or JSON syntax.
18. DATE FILTERING:
    - For specific months like "March 2026": use strftime('%Y-%m', date) = '2026-03'
    - NEVER use strftime('%Y-%m', date) = strftime('%Y-%m', '2026-03') — this is WRONG
    - NEVER combine this_month/last_month with a specific month — use ONLY one date filter
    - For "May 2026": strftime('%Y-%m', date) = '2026-05' (direct string comparison)
    - The date column stores dates as TEXT in 'YYYY-MM-DD' format
    - CRITICAL: For "last N months" use >= date('now', '-N months'), NOT strftime equality
19. AMOUNT SIGN CONVENTION (CRITICAL):
    - Debits are NEGATIVE, Credits are POSITIVE
    - For spending queries: SELECT SUM(ABS(amount)) — NOT SUM(amount)
    - For spending queries: ORDER BY ABS(amount) DESC — NOT ORDER BY amount DESC
    - NEVER use amount > 0 or amount < 0 as a filter
20. GROUP BY RULE:
    - When using SUM/AVG/COUNT with GROUP BY, only select aggregated columns and grouping columns
    - WRONG: SELECT date, category, SUM(amount) GROUP BY category (date not in GROUP BY)
    - CORRECT: SELECT strftime('%Y-%m', date) AS month, category, SUM(amount) GROUP BY month, category

=== CORRECT EXAMPLES ===

Example A — Simple highest expense (single table, NO JOIN):
Question: "What was my highest expense ever?"
```sql
SELECT transaction_id, description, ABS(amount) AS expense_amount, date, category, account
FROM transactions
WHERE type = 'debit'
ORDER BY ABS(amount) DESC
LIMIT 1
```

Example B — Spending by category last month (single table, NO JOIN):
Question: "How much did I spend by category last month?"
```sql
SELECT category, SUM(ABS(amount)) AS total_spent, COUNT(*) AS num_transactions
FROM transactions
WHERE type = 'debit'
  AND {date_last_month}
GROUP BY category
ORDER BY total_spent DESC
```

Example C — Spending last 6 months (ROLLING WINDOW - use >= not =):
Question: "Analyze my spending patterns for the last 6 months"
```sql
SELECT strftime('%Y-%m', date) AS month, category, SUM(ABS(amount)) AS total_spent
FROM transactions
WHERE type = 'debit'
  AND {date_last_6_months}
GROUP BY month, category
ORDER BY month, total_spent DESC
```

Example D — Total income (single table, NO JOIN):
Question: "What is my total income?"
```sql
SELECT SUM(amount) AS total_income
FROM transactions
WHERE type = 'credit'
```

Example E — Tag search (NO type filter, tags is comma-separated TEXT):
Question: "Show all transactions tagged with 'subscription'"
```sql
SELECT transaction_id, date, description, amount, type, category, account, merchant, payment_method, tags
FROM transactions
WHERE tags LIKE '%subscription%'
ORDER BY date DESC
LIMIT 50
```

Example F — Specific month query:
Question: "How much did I spend on Food in May 2026?"
```sql
SELECT category, SUM(ABS(amount)) AS total
FROM transactions
WHERE type = 'debit'
  AND category = 'Food'
  AND strftime('%Y-%m', date) = '2026-05'
GROUP BY category
```

Example G — Monthly spending trend (use ABS for debits):
Question: "Show my monthly spending trend"
```sql
SELECT strftime('%Y-%m', date) AS month, SUM(ABS(amount)) AS total_spent, COUNT(*) AS num_transactions
FROM transactions
WHERE type = 'debit'
GROUP BY month
ORDER BY month
```

Generate ONLY the SQL query inside the code block:

```sql
"""


def _validate_and_fix_columns(sql: str) -> str:
    """Validate column names against schema and fix common hallucinations."""
    if not sql or not TABLE_COLUMNS:
        return sql

    for bad_col, good_col in COLUMN_ALIASES.items():
        pattern = r'(?<![\w.])' + re.escape(bad_col) + r'(?![\w])'
        if re.search(pattern, sql, re.IGNORECASE):
            if good_col is None:
                sql = re.sub(
                    r'(?i)SELECT\s+([^\n]*?)\b' + re.escape(bad_col) + r'\b\s*,?\s*',
                    lambda m: 'SELECT ' + m.group(1).replace(m.group(0).split()[-1], '').rstrip(',').rstrip(),
                    sql
                )
                sql = re.sub(r',\s*FROM', ' FROM', sql, flags=re.IGNORECASE)
                print(f"[Generator] Removed hallucinated column '{bad_col}'")
            else:
                sql = re.sub(pattern, good_col, sql, flags=re.IGNORECASE)
                print(f"[Generator] Fixed column name: '{bad_col}' -> '{good_col}'")

    json_hallucinations = [
        (r'\btags\.name\b', "tags LIKE '%subscription%'"),
        (r'\btags\.value\b', "tags LIKE '%value%'"),
        (r'\btags\[[^\]]+\]', "tags LIKE '%value%'"),
        (r'\btags\s*->>', "tags"),
        (r'\btags\s*#>', "tags"),
    ]

    for pattern, replacement in json_hallucinations:
        if re.search(pattern, sql, re.IGNORECASE):
            print(f"[Generator] FIXED JSON hallucination: removed tags.dot notation")
            sql = re.sub(pattern, "tags", sql, flags=re.IGNORECASE)

    sql = re.sub(
        r"(?i)WHERE\s+(\w+)\s*=\s*['\"]([^'\"]+)['\"]",
        lambda m: f"WHERE {m.group(1)} LIKE '%{m.group(2)}%'" if m.group(1).lower() == 'tags' else m.group(0),
        sql
    )

    sql = re.sub(r',\s*,', ',', sql)
    sql = re.sub(r'SELECT\s+,', 'SELECT ', sql, flags=re.IGNORECASE)
    sql = re.sub(r',\s+FROM', ' FROM', sql, flags=re.IGNORECASE)

    return sql


def _enforce_abs_for_debits(sql: str, intent_data: Dict[str, Any]) -> str:
    """CRITICAL: Ensure ABS(amount) is used for debit/spending queries."""
    type_filter = intent_data.get("type_filter") if intent_data else None
    sql_lower = sql.lower()

    is_debit_query = (type_filter == "debit" or 
                      "type = 'debit'" in sql_lower or 
                      "type=\"debit\"" in sql_lower)

    if is_debit_query:
        sql = re.sub(r'(?i)SUM\s*\(\s*amount\s*\)', 'SUM(ABS(amount))', sql)
        sql = re.sub(r'(?i)ORDER\s+BY\s+amount\s+DESC', 'ORDER BY ABS(amount) DESC', sql)
        sql = re.sub(r'(?i)ORDER\s+BY\s+amount\s+ASC', 'ORDER BY ABS(amount) ASC', sql)
        sql = re.sub(r'(?i)MAX\s*\(\s*amount\s*\)', 'MAX(ABS(amount))', sql)
        sql = re.sub(r'(?i)AVG\s*\(\s*amount\s*\)', 'AVG(ABS(amount))', sql)

    return sql


def _fix_date_filters(sql: str, question_lower: str) -> str:
    """CRITICAL: Fix date filters for rolling windows.

    Problem: LLM sometimes generates BOTH:
      strftime('%Y-%m', date) = strftime('%Y-%m', 'now', '-6 months')  -- WRONG (equality)
      AND date >= date('now', '-6 months')                                 -- CORRECT (range)

    The equality filter only matches ONE month (6 months ago), not the rolling window.
    """
    # Detect if this is a rolling window query
    is_rolling_window = any(phrase in question_lower for phrase in [
        "last 6 months", "past 6 months", "last six months", "past six months",
        "last 3 months", "past 3 months", "last three months", "past three months",
        "last year", "past year", "last 12 months", "past 12 months"
    ])

    if not is_rolling_window:
        return sql

    # Remove old-style strftime equality filters that compare to a computed month
    # Pattern: strftime('%Y-%m', date) = strftime('%Y-%m', 'now', '-N month')
    old_pattern = r"strftime\('%Y-%m',\s*date\)\s*=\s*strftime\('%Y-%m',\s*'now',\s*'-[\d\s]+month'\)"
    if re.search(old_pattern, sql, re.IGNORECASE):
        sql = re.sub(old_pattern, "1=1", sql, flags=re.IGNORECASE)
        print(f"[Generator] Removed old-style strftime equality filter for rolling window")

    # Also remove any strftime('%Y-%m', date) = strftime('%Y-%m', 'now') when rolling window
    current_month_pattern = r"strftime\('%Y-%m',\s*date\)\s*=\s*strftime\('%Y-%m',\s*'now'\)"
    if re.search(current_month_pattern, sql, re.IGNORECASE):
        sql = re.sub(current_month_pattern, "1=1", sql, flags=re.IGNORECASE)
        print(f"[Generator] Removed current month strftime filter for rolling window")

    # Clean up: remove 1=1 AND or AND 1=1
    sql = re.sub(r'\s+AND\s+1=1\b', '', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\b1=1\s+AND\s+', '', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\bWHERE\s+1=1\b', 'WHERE 1=1', sql, flags=re.IGNORECASE)

    # If WHERE is now empty or just 1=1, clean it up
    sql = re.sub(r'WHERE\s+1=1\s*$', '', sql, flags=re.IGNORECASE)
    sql = re.sub(r'WHERE\s+1=1\s+ORDER', 'ORDER', sql, flags=re.IGNORECASE)
    sql = re.sub(r'WHERE\s+1=1\s+GROUP', 'GROUP', sql, flags=re.IGNORECASE)

    return sql


def _fix_group_by(sql: str) -> str:
    """Fix GROUP BY to include all non-aggregated selected columns."""
    # Simple heuristic: if SELECT has date and GROUP BY doesn't, add it
    select_match = re.search(r'SELECT\s+(.*?)\s+FROM', sql, re.IGNORECASE | re.DOTALL)
    group_match = re.search(r'GROUP\s+BY\s+(.*?)(?:\s+ORDER|\s+LIMIT|$)', sql, re.IGNORECASE | re.DOTALL)

    if not select_match or not group_match:
        return sql

    select_cols = [c.strip().split()[0] for c in select_match.group(1).split(',')]
    group_cols = [c.strip() for c in group_match.group(1).split(',')]

    # Check if 'date' is in SELECT but not in GROUP BY
    if 'date' in select_cols and 'date' not in group_cols:
        # Replace date with strftime expression in GROUP BY if needed
        new_group = group_match.group(1) + ", date"
        sql = sql.replace(group_match.group(0), f"GROUP BY{new_group}{group_match.group(0)[len('GROUP BY' + group_match.group(1)):]})")

    return sql


def _post_process_sql(sql: str, intent_data: Dict[str, Any], retry_hint: str, dialect: str = "sqlite", question_lower: str = "") -> str:
    """Apply deterministic fixes based on retry hints and intent."""

    sql = _validate_and_fix_columns(sql)
    sql = _enforce_abs_for_debits(sql, intent_data)
    sql = _fix_date_filters(sql, question_lower)
    sql = _fix_group_by(sql)

    if retry_hint and "Remove type" in retry_hint:
        original = sql
        sql = re.sub(r"\s*AND\s+type\s*=\s*['\"](debit|credit)['\"]", "", sql, flags=re.IGNORECASE)
        sql = re.sub(r"type\s*=\s*['\"](debit|credit)['\"]\s*AND\s*", "", sql, flags=re.IGNORECASE)
        sql = re.sub(r"WHERE\s+type\s*=\s*['\"](debit|credit)['\"]", "WHERE 1=1", sql, flags=re.IGNORECASE)
        if sql != original:
            print(f"[Generator] Removed type filter based on retry_hint")

    type_filter = intent_data.get("type_filter")
    if type_filter is None and "type =" in sql.lower():
        original = sql
        sql = re.sub(r"\s*AND\s+type\s*=\s*['\"](debit|credit)['\"]", "", sql, flags=re.IGNORECASE)
        sql = re.sub(r"WHERE\s+type\s*=\s*['\"](debit|credit)['\"]\s*AND", "WHERE", sql, flags=re.IGNORECASE)
        sql = re.sub(r"WHERE\s+type\s*=\s*['\"](debit|credit)['\"]", "WHERE 1=1", sql, flags=re.IGNORECASE)
        if sql != original:
            print(f"[Generator] Removed hallucinated type filter (intent.type_filter is null)")

    if "LIMIT" not in sql.upper():
        sql = sql.rstrip(';') + " LIMIT 50"

    sql = re.sub(r'\s+', ' ', sql).strip()
    if sql.endswith(";"):
        sql = sql[:-1].strip()

    return sql


async def generator_node(state: Dict[str, Any]) -> Dict[str, Any]:
    llm = ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model_name=settings.LLM_MODEL,
        temperature=0.0,
    )

    dialect = state.get("dialect", "sqlite")
    date_examples = DIALECT_EXAMPLES.get(dialect, DIALECT_EXAMPLES["sqlite"])

    try:
        exact_schema = await _load_schema_from_db()
    except Exception as e:
        print(f"[Generator] Failed to load schema from DB: {e}")
        exact_schema = "-- Schema unavailable --"

    sample_data_parts = []
    try:
        schema = await db_manager.get_schema()
        tables = schema.get("tables", []) if isinstance(schema, dict) else schema
        for table in tables[:4]:
            table_name = table.get("name") if isinstance(table, dict) else table
            if not table_name:
                continue
            try:
                sample = await db_manager.execute_readonly(f"SELECT * FROM {table_name} LIMIT 2")
                rows = sample.get("rows", []) if isinstance(sample, dict) else []
                if rows:
                    cols = list(rows[0].keys()) if rows else []
                    sample_data_parts.append(
                        f"Table `{table_name}` (columns: {', '.join(cols)}):\n" +
                        "\n".join([str(r) for r in rows[:2]])
                    )
            except Exception as e:
                print(f"[Generator] Could not sample {table_name}: {e}")
    except Exception as e:
        print(f"[Generator] Could not get schema: {e}")

    sample_data_text = "\n\n".join(sample_data_parts) if sample_data_parts else "No sample data available."
    sample_data_section = f"SAMPLE DATA FROM TABLES:\n{sample_data_text}" if sample_data_text else ""

    intent = state.get("intent", {})
    question_lower = state["question"].lower()

    prompt = ChatPromptTemplate.from_template(GENERATOR_PROMPT)
    chain = prompt | llm

    response = await chain.ainvoke({
        "question": state["question"],
        "exact_schema": exact_schema,
        "sample_data": sample_data_section,
        "tags_rules": TAGS_COLUMN_RULES,
        "sign_rules": SIGN_CONVENTION_RULES,
        "date_rules": DATE_FILTER_RULES.format(
            date_this_month=date_examples["this_month"],
            date_last_month=date_examples["last_month"],
            date_last_3_months=date_examples["last_3_months"],
            date_last_6_months=date_examples["last_6_months"],
            date_last_year=date_examples["last_year"],
        ),
        "error": state.get("error", "None"),
        "retry_hint": state.get("retry_hint", "None"),
        "primary_intent": intent.get("primary_intent", "filter_lookup"),
        "type_filter": str(intent.get("type_filter", "null")),
        "time_dimension": str(intent.get("time_dimension", "null")),
        "aggregation_type": str(intent.get("aggregation_type", "null")),
        "dialect": dialect,
        "date_this_month": date_examples["this_month"],
        "date_last_month": date_examples["last_month"],
        "date_last_3_months": date_examples["last_3_months"],
        "date_last_6_months": date_examples["last_6_months"],
        "date_last_year": date_examples["last_year"],
    })

    sql = response.content
    if "```sql" in sql:
        sql = sql.split("```sql")[1].split("```")[0].strip()
    elif "```" in sql:
        sql = sql.split("```")[1].split("```")[0].strip()

    sql = _post_process_sql(sql, intent, state.get("retry_hint", ""), dialect, question_lower)

    return {
        **state,
        "generated_sql": sql,
        "error": None,
    }

